# -*- coding: utf-8 -*-
"""Ghim cửa sổ xuống mặt bàn Desktop theo cơ chế Rainmeter (Top-Level Desktop Pin).

Nguyên lý Rainmeter (Top-Level Desktop Pin):
============================================
1. Widget giữ nguyên là Top-Level Window (KHÔNG dùng SetParent(Progman)).
   Nhờ vậy, Qt giữ nguyên WA_TranslucentBackground = True, hiệu ứng đổ bóng giấy ngà
   và bo tròn 4 góc trong suốt 100%, không bị bất kỳ quầng đen hay viền đen nào.
2. Cài đặt các cờ Win32:
   - WS_EX_TOOLWINDOW: Không xuất hiện trên thanh Taskbar và danh sách Alt+Tab.
   - WS_EX_NOACTIVATE: Khi click/tương tác chuột không cướp focus của ứng dụng khác.
3. Chống bị ẩn khi bấm Win + D (Show Desktop):
   - Rainmeter tạo một cửa sổ phụ vô hình (sentinel) ở đáy Z-order (HWND_BOTTOM).
   - Khi người dùng bấm Win + D, Explorer nâng lớp Desktop (Progman trên Win11 24H2+,
     hoặc WorkerW chứa SHELLDLL_DefView trên các bản cũ) lên trên.
   - Sentinel phát hiện lớp Desktop nhảy lên trên nó -> Nhận diện trạng thái Show Desktop!
   - Khi ở trạng thái Show Desktop, widget được nâng lên nằm ngay trên lớp Desktop
     (tầng HWND_TOPMOST, phía dưới Taskbar), nên không bị che khuất!
   - Khi thoát Show Desktop (người dùng mở lại ứng dụng hoặc click app), widget được
     hạ trở về HWND_BOTTOM, nằm dưới mọi ứng dụng nhưng trên hình nền.
4. Hook sự kiện WinEvent (EVENT_SYSTEM_FOREGROUND):
   - Bắt tức thì khi chuyển đổi qua lại giữa Desktop và các ứng dụng mà không cần chờ timer.
5. Timer dò thoát Show Desktop (Rainmeter: INTERVAL_RESTOREWINDOWS):
   - Khi khôi phục ứng dụng, sự kiện foreground đến TRƯỚC lúc Explorer hạ lớp Desktop
     (~100 ms) và sau đó không còn sự kiện nào. Vì vậy trong lúc Show Desktop, một
     timer Win32 hỏi lại mỗi RESTORE_POLL_MS để hạ widget ngay khi lớp Desktop xuống,
     thay vì để widget TOPMOST đè lên ứng dụng tới lượt watchdog kế tiếp.
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from . import IS_WINDOWS
from . import win32

__all__ = [
    "find_desktop_host",
    "get_desktop_icons_host",
    "pin",
    "unpin",
    "is_pinned",
    "desktop_host_alive",
    "monitor",
    "send_to_bottom",
    "update_z_order",
    "is_show_desktop_active",
    "handle_windowposchanging",
    "last_error",
]

log = logging.getLogger(__name__)

CLASS_PROGMAN = "Progman"
CLASS_WORKERW = "WorkerW"
CLASS_DEFVIEW = "SHELLDLL_DefView"
SENTINEL_CLASS = "STATIC"
SENTINEL_TITLE = "QTCalendarSystem"

# Cờ SetWindowPos của Rainmeter (không gửi WM_WINDOWPOSCHANGING khi nội bộ đổi Z-order)
ZPOS_FLAGS = (
    win32.SWP_NOMOVE
    | win32.SWP_NOSIZE
    | win32.SWP_NOOWNERZORDER
    | win32.SWP_NOACTIVATE
    | win32.SWP_NOSENDCHANGING
)

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

_WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    ctypes.c_long,
    ctypes.c_long,
    wintypes.DWORD,
    wintypes.DWORD,
)

# Chu kỳ (ms) dò thoát Show Desktop; chỉ chạy trong lúc đang Show Desktop.
RESTORE_POLL_MS = 50

_TIMERPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HWND,
    wintypes.UINT,
    ctypes.c_size_t,  # UINT_PTR idEvent
    wintypes.DWORD,
)


@dataclass
class _PinState:
    hwnd: int
    exstyle: int
    style: int


_pinned_hwnds: Set[int] = set()
_saved_states: Dict[int, _PinState] = {}
_sentinel_hwnd: int = 0
_win_event_hook = None
_hook_proc_ref = None  # giữ tham chiếu tránh GC thu hồi
_restore_timer: int = 0
_timer_proc_ref = None  # giữ tham chiếu tránh GC thu hồi
_show_desktop: bool = False
last_error: int = 0


def get_desktop_icons_host() -> int:
    """Xác định cửa sổ chứa Desktop Icons (SHELLDLL_DefView).

    Trên Windows 11 24H2+: Explorer tổ chức SHELLDLL_DefView là con của Progman.
    Trên Windows 10/11 cũ: SHELLDLL_DefView là con của WorkerW.
    """
    if not IS_WINDOWS:
        return 0

    shell_w = win32.get_shell_window() or win32.find_window(CLASS_PROGMAN)
    if not shell_w:
        return 0

    # Windows 11 24H2+ (hoặc trường hợp SHELLDLL_DefView nằm trực tiếp trong Progman)
    if win32.is_win11_24h2_or_newer() or win32.find_window_ex(shell_w, 0, CLASS_DEFVIEW):
        return shell_w

    # Các bản Windows trước 24H2: tìm WorkerW chứa SHELLDLL_DefView
    worker_w = 0
    while True:
        worker_w = win32.find_window_ex(0, worker_w, CLASS_WORKERW)
        if not worker_w:
            break
        if win32.is_window_visible(worker_w):
            _, shell_pid = win32.get_window_thread_process_id(shell_w)
            _, worker_pid = win32.get_window_thread_process_id(worker_w)
            if shell_pid == worker_pid and win32.find_window_ex(worker_w, 0, CLASS_DEFVIEW):
                return worker_w

    return shell_w


def find_desktop_host() -> Tuple[int, str]:
    """Tìm host desktop. Giữ lại tương thích API."""
    host = get_desktop_icons_host()
    if host:
        return (host, win32.get_class_name(host))
    return (0, "")


def desktop_host_alive() -> bool:
    """Kiểm tra môi trường Desktop còn hoạt động."""
    if not IS_WINDOWS:
        return False
    host = get_desktop_icons_host()
    return bool(host and win32.is_window(host))


def _ensure_sentinel() -> int:
    """Tạo hoặc lấy cửa sổ sentinel ở HWND_BOTTOM để phát hiện Show Desktop."""
    global _sentinel_hwnd
    if not IS_WINDOWS:
        return 0
    if _sentinel_hwnd and win32.is_window(_sentinel_hwnd):
        return _sentinel_hwnd

    try:
        if win32.user32 is None or win32.kernel32 is None:
            return 0
        hinst = win32.kernel32.GetModuleHandleW(None)
        win32.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        win32.user32.CreateWindowExW.restype = wintypes.HWND

        hwnd = win32.user32.CreateWindowExW(
            win32.WS_EX_TOOLWINDOW,
            SENTINEL_CLASS,
            SENTINEL_TITLE,
            win32.WS_POPUP,
            0,
            0,
            1,
            1,
            None,
            None,
            hinst,
            None,
        )
        if hwnd:
            _sentinel_hwnd = int(hwnd)
            win32.set_window_pos(_sentinel_hwnd, win32.HWND_BOTTOM, 0, 0, 0, 0, ZPOS_FLAGS)
            log.debug("Đã tạo sentinel window: %#x", _sentinel_hwnd)
        return _sentinel_hwnd
    except Exception as e:
        log.debug("Không tạo được sentinel window: %s", e)
        return 0


def _cleanup_sentinel() -> None:
    """Hủy sentinel window khi không còn cửa sổ nào ghim."""
    global _sentinel_hwnd
    if _sentinel_hwnd and win32.is_window(_sentinel_hwnd):
        try:
            if win32.user32 is not None:
                win32.user32.DestroyWindow(wintypes.HWND(_sentinel_hwnd))
        except Exception:
            pass
    _sentinel_hwnd = 0


def is_show_desktop_active() -> bool:
    """Kiểm tra hệ thống có đang ở trạng thái Show Desktop (Win + D) không."""
    if not IS_WINDOWS:
        return False

    host = get_desktop_icons_host()
    if not host or not win32.is_window_visible(host):
        return False

    # 1. Thuật toán Rainmeter: nếu sentinel window nằm SAU (bên dưới) host trong Z-order
    # thì nghĩa là host đã bị Windows nâng lên trên sentinel -> Show Desktop!
    sentinel = _ensure_sentinel()
    if sentinel and win32.is_window(sentinel):
        # find_window_ex tìm cửa sổ sau 'host' trong danh sách Z-order
        found = win32.find_window_ex(0, host, SENTINEL_CLASS, SENTINEL_TITLE)
        if found == sentinel:
            return True

    # 2. Bổ sung: Nếu foreground window chính là host (Progman/WorkerW)
    fg = win32.get_foreground_window()
    if fg and (fg == host or win32.get_ancestor(fg, 2) == host):
        return True

    return False


def _find_taskbar_window() -> int:
    """Tìm HWND của Taskbar chính (Shell_TrayWnd)."""
    return win32.find_window("Shell_TrayWnd")


def update_z_order(hwnd: int) -> None:
    """Cập nhật vị trí Z-order cho cửa sổ ghim theo trạng thái Desktop."""
    if not IS_WINDOWS or not hwnd or not win32.is_window(hwnd):
        return

    show_dt = is_show_desktop_active()

    if show_dt:
        # Đang Show Desktop (Win + D):
        # Nâng widget lên tầng HWND_TOPMOST để không bị lớp Desktop (Progman/WorkerW) che khuất.
        win32.set_window_pos(hwnd, win32.HWND_TOPMOST, 0, 0, 0, 0, ZPOS_FLAGS)

        # Chèn widget phía sau Taskbar để không che Taskbar hoặc Start Menu
        taskbar = _find_taskbar_window()
        if taskbar and win32.is_window(taskbar) and win32.is_window_visible(taskbar):
            win32.set_window_pos(hwnd, taskbar, 0, 0, 0, 0, ZPOS_FLAGS)

        _start_restore_poll()
    else:
        # Bình thường:
        # Đưa widget về HWND_BOTTOM để nằm dưới tất cả các ứng dụng thông thường
        win32.set_window_pos(hwnd, win32.HWND_BOTTOM, 0, 0, 0, 0, ZPOS_FLAGS)

        _stop_restore_poll()


def send_to_bottom(hwnd: int) -> None:
    """Đưa cửa sổ về vị trí chuẩn (tương thích API cũ)."""
    update_z_order(hwnd)


def _on_restore_poll(_hwnd, _msg, _id_event, _time):
    """Timer dò thoát Show Desktop: chỉ đổi Z-order khi lớp Desktop đã hạ xuống."""
    if is_show_desktop_active():
        return
    _stop_restore_poll()
    for p_hwnd in list(_pinned_hwnds):
        if win32.is_window(p_hwnd):
            update_z_order(p_hwnd)


def _start_restore_poll() -> None:
    """Bật timer Win32 dò thoát Show Desktop (gọi trên luồng GUI, đã chạy thì bỏ qua)."""
    global _restore_timer, _timer_proc_ref
    if not IS_WINDOWS or _restore_timer:
        return
    try:
        if win32.user32 is None:
            return
        win32.user32.SetTimer.argtypes = [
            wintypes.HWND,
            ctypes.c_size_t,
            wintypes.UINT,
            _TIMERPROC,
        ]
        win32.user32.SetTimer.restype = ctypes.c_size_t

        if _timer_proc_ref is None:
            _timer_proc_ref = _TIMERPROC(_on_restore_poll)
        # hWnd = NULL: timer của luồng, vòng lặp Qt DispatchMessage tới _TIMERPROC
        _restore_timer = int(win32.user32.SetTimer(None, 0, RESTORE_POLL_MS, _timer_proc_ref) or 0)
    except Exception as e:
        log.debug("Không bật được timer dò thoát Show Desktop: %s", e)


def _stop_restore_poll() -> None:
    """Tắt timer dò thoát Show Desktop."""
    global _restore_timer
    if not _restore_timer:
        return
    try:
        if win32.user32 is not None:
            win32.user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
            win32.user32.KillTimer.restype = wintypes.BOOL
            win32.user32.KillTimer(None, _restore_timer)
    except Exception:
        pass
    _restore_timer = 0


def handle_windowposchanging(lparam: int, allow_hide: bool = False) -> bool:
    """Xử lý thông điệp WM_WINDOWPOSCHANGING theo cơ chế Rainmeter.

    1. Ngăn cản click chuột làm nhảy Z-order lên đỉnh (SWP_NOZORDER).
    2. Chống dời toạ độ (-32000, -32000) và cờ ẩn SWP_HIDEWINDOW khi Win + D.

    ``allow_hide=True`` khi chính ứng dụng đang ẩn widget (khay/menu): giữ
    nguyên SWP_HIDEWINDOW, nếu không Qt coi cửa sổ đã ẩn (ngừng vẽ lại) trong
    khi Windows vẫn hiện nó.
    """
    if not IS_WINDOWS or not lparam:
        return False

    try:
        pos = win32.WINDOWPOS.from_address(lparam)
        modified = False

        # Nếu lệnh SetWindowPos nội bộ mang cờ SWP_NOSENDCHANGING thì cho phép
        if not (pos.flags & win32.SWP_NOSENDCHANGING):
            # Giữ nguyên Z-order khi người dùng click chuột hoặc kéo thả
            pos.flags |= win32.SWP_NOZORDER
            modified = True

        # Chống dời ra toạ độ ngoài màn hình khi Show Desktop
        if pos.x <= -30000 or pos.y <= -30000:
            pos.flags |= (win32.SWP_NOMOVE | win32.SWP_NOSIZE)
            modified = True

        # Chống bị giấu bởi SWP_HIDEWINDOW khi Show Desktop
        if pos.flags & win32.SWP_HIDEWINDOW and not allow_hide:
            pos.flags &= ~win32.SWP_HIDEWINDOW
            pos.flags |= win32.SWP_SHOWWINDOW
            modified = True

        return modified
    except Exception as e:
        log.debug("Lỗi handle_windowposchanging: %s", e)
        return False


def _on_win_event(_hook, event, hwnd, _id_obj, _id_child, _thread, _time):
    """Callback khi cửa sổ active thay đổi (người dùng bấm Win + D hoặc click app)."""
    if event == EVENT_SYSTEM_FOREGROUND:
        for p_hwnd in list(_pinned_hwnds):
            if win32.is_window(p_hwnd):
                update_z_order(p_hwnd)


def _setup_event_hook() -> None:
    """Đăng ký hook theo dõi sự kiện đổi cửa sổ active."""
    global _win_event_hook, _hook_proc_ref
    if not IS_WINDOWS or _win_event_hook:
        return
    try:
        if win32.user32 is None:
            return
        win32.user32.SetWinEventHook.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HMODULE,
            _WINEVENTPROC,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        win32.user32.SetWinEventHook.restype = wintypes.HANDLE

        _hook_proc_ref = _WINEVENTPROC(_on_win_event)
        _win_event_hook = win32.user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            None,
            _hook_proc_ref,
            0,
            0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        )
    except Exception as e:
        log.debug("Không đăng ký được WinEventHook: %s", e)


def _cleanup_event_hook() -> None:
    """Gỡ hook khi không còn cửa sổ ghim."""
    global _win_event_hook, _hook_proc_ref
    if _win_event_hook:
        try:
            if win32.user32 is not None:
                win32.user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
                win32.user32.UnhookWinEvent.restype = wintypes.BOOL
                win32.user32.UnhookWinEvent(_win_event_hook)
        except Exception:
            pass
        _win_event_hook = None
        _hook_proc_ref = None


def pin(hwnd: int) -> bool:
    """Ghim cửa sổ xuống Desktop theo cơ chế Rainmeter Top-Level."""
    global last_error
    if not IS_WINDOWS:
        return False
    if not hwnd or not win32.is_window(hwnd):
        return False

    try:
        exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
        style = win32.get_window_long(hwnd, win32.GWL_STYLE)
        _saved_states[hwnd] = _PinState(hwnd=hwnd, exstyle=exstyle, style=style)

        # Cài cờ WS_EX_TOOLWINDOW và WS_EX_NOACTIVATE, giữ nguyên WS_EX_LAYERED
        new_exstyle = exstyle | win32.WS_EX_TOOLWINDOW | win32.WS_EX_NOACTIVATE
        win32.set_window_long(hwnd, win32.GWL_EXSTYLE, new_exstyle)

        _ensure_sentinel()
        _setup_event_hook()

        update_z_order(hwnd)

        _pinned_hwnds.add(hwnd)
        last_error = 0
        log.info("Đã ghim cửa sổ %#x xuống Desktop (cơ chế Rainmeter Top-Level)", hwnd)
        return True
    except Exception as e:
        log.warning("Ghim cửa sổ %#x thất bại: %s", hwnd, e)
        last_error = 1
        return False


def unpin(hwnd: int) -> bool:
    """Bỏ ghim, khôi phục cửa sổ về trạng thái nổi bình thường."""
    if not IS_WINDOWS:
        return False
    if not hwnd:
        return False

    try:
        if hwnd in _saved_states:
            state = _saved_states.pop(hwnd)
            # Khôi phục exstyle ban đầu
            win32.set_window_long(hwnd, win32.GWL_EXSTYLE, state.exstyle)

        # Đặt lại Z-order thông thường (HWND_NOTOPMOST)
        win32.set_window_pos(
            hwnd,
            win32.HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            win32.SWP_NOMOVE | win32.SWP_NOSIZE | win32.SWP_NOACTIVATE | win32.SWP_NOSENDCHANGING,
        )

        _pinned_hwnds.discard(hwnd)

        if not _pinned_hwnds:
            _stop_restore_poll()
            _cleanup_event_hook()
            _cleanup_sentinel()

        log.info("Đã bỏ ghim cửa sổ %#x khỏi Desktop", hwnd)
        return True
    except Exception as e:
        log.warning("Bỏ ghim cửa sổ %#x thất bại: %s", hwnd, e)
        return False


def is_pinned(hwnd: int) -> bool:
    """Kiểm tra cửa sổ có đang ở chế độ ghim Desktop hay không."""
    return hwnd in _pinned_hwnds


def monitor() -> bool:
    """Watchdog định kỳ: duy trì Z-order và hiển thị cho các cửa sổ đã ghim."""
    if not IS_WINDOWS:
        return True

    alive = True
    for hwnd in list(_pinned_hwnds):
        if not win32.is_window(hwnd):
            _pinned_hwnds.discard(hwnd)
            _saved_states.pop(hwnd, None)
            alive = False
            continue

        if not win32.is_window_visible(hwnd):
            win32.show_window(hwnd, win32.SW_SHOWNOACTIVATE)

        update_z_order(hwnd)

    if not _pinned_hwnds:
        _stop_restore_poll()
        _cleanup_event_hook()
        _cleanup_sentinel()

    return alive
