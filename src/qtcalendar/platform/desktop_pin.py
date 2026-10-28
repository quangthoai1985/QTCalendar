# -*- coding: utf-8 -*-
"""Ghim cửa sổ xuống mặt bàn Desktop theo cơ chế Rainmeter (Top-Level Desktop Pin).

Nguyên lý (Kiểu Rainmeter / Top-Level Pin)
=========================================

Thay vì gọi ``SetParent(hwnd, Progman)`` (vốn bị lớp hình nền DWM WorkerW của
Windows 10/11 nuốt chửng, làm mất bóng đổ và gây lỗi viền đen), cơ chế Rainmeter
giữ cửa sổ là **Top-Level Window** độc lập:

1. **Vị trí Z-Order**: Cửa sổ được xếp ở đáy ngăn xếp hiển thị (``HWND_BOTTOM``)
   – nằm ngay sát trên lớp Desktop và nằm dưới mọi cửa sổ ứng dụng thông thường
   khác.
2. **Ẩn khỏi Taskbar & Alt+Tab**: Cài đặt cờ ``WS_EX_TOOLWINDOW`` (kết hợp
   ``WS_EX_NOACTIVATE`` để không cướp focus của ứng dụng khác khi click).
3. **Chống bị ẩn khi nhấn ``Win + D`` (Show Desktop)**:
   - Khi Windows thực hiện "Show Desktop", hệ thống gửi thông điệp
     ``WM_WINDOWPOSCHANGING`` yêu cầu di chuyển cửa sổ ra toạ độ ngoài màn hình
     (``x = -32000, y = -32000``) hoặc bật cờ ``SWP_HIDEWINDOW``.
   - Ứng dụng can thiệp qua ``handle_windowposchanging()``: loại bỏ cờ
     ``SWP_HIDEWINDOW``, bật ``SWP_SHOWWINDOW`` và cố định Z-order ở ``HWND_BOTTOM``.
   - Kết quả: Khi người dùng bấm ``Win + D``, toàn bộ các ứng dụng khác thu nhỏ,
     riêng widget lịch vẫn hiển thị sờ sờ trên Desktop!
4. **Giữ nguyên 100% vẻ đẹp đồ hoạ**:
   - Do vẫn là Top-Level Window, công nghệ trong suốt của Qt
     (``WA_TranslucentBackground``), hiệu ứng đổ bóng giấy ngà và bo tròn góc
     hoạt động trơn tru 100% mà không bị viền đen hay crash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Set, Tuple

from . import IS_WINDOWS
from . import win32

__all__ = [
    "find_desktop_host",
    "pin",
    "unpin",
    "is_pinned",
    "desktop_host_alive",
    "monitor",
    "send_to_bottom",
    "handle_windowposchanging",
    "last_error",
]

log = logging.getLogger(__name__)

CLASS_PROGMAN = "Progman"
CLASS_WORKERW = "WorkerW"
CLASS_DEFVIEW = "SHELLDLL_DefView"


@dataclass
class _PinState:
    """Trạng thái ban đầu của cửa sổ trước khi ghim để khôi phục khi unpin."""

    hwnd: int
    exstyle: int
    style: int


#: Tập hợp các HWND đang ở trạng thái ghim Desktop
_pinned_hwnds: Set[int] = set()
_saved_states: Dict[int, _PinState] = {}

last_error: int = 0


def find_desktop_host() -> Tuple[int, str]:
    """Tìm host desktop (Progman hoặc WorkerW). Giữ lại cho tương thích."""
    try:
        if not IS_WINDOWS:
            return (0, "")
        progman = win32.find_window(CLASS_PROGMAN)
        if progman:
            return (progman, CLASS_PROGMAN)
        return (0, "")
    except Exception:
        return (0, "")


def desktop_host_alive() -> bool:
    """Kiểm tra môi trường Desktop còn hoạt động."""
    if not IS_WINDOWS:
        return False
    return True


def send_to_bottom(hwnd: int) -> None:
    """Đưa cửa sổ xuống đáy Z-order (HWND_BOTTOM) nhưng vẫn hiển thị trên Desktop."""
    if not IS_WINDOWS or not hwnd or not win32.is_window(hwnd):
        return
    win32.set_window_pos(
        hwnd,
        win32.HWND_BOTTOM,
        0,
        0,
        0,
        0,
        win32.SWP_NOMOVE
        | win32.SWP_NOSIZE
        | win32.SWP_NOACTIVATE
        | win32.SWP_SHOWWINDOW
        | win32.SWP_NOOWNERZORDER,
    )


def handle_windowposchanging(lparam: int) -> bool:
    """Xử lý thông điệp WM_WINDOWPOSCHANGING để chống bị ẩn bởi Win + D.

    Trả về True nếu có can thiệp sửa đổi struct WINDOWPOS.
    """
    if not IS_WINDOWS or not lparam:
        return False

    try:
        pos = win32.WINDOWPOS.from_address(lparam)
        modified = False

        # Win + D di chuyển cửa sổ ra toạ độ ngoài màn hình (-32000, -32000)
        if pos.x <= -30000 or pos.y <= -30000:
            pos.flags |= (win32.SWP_NOMOVE | win32.SWP_NOSIZE)
            modified = True

        # Win + D bật cờ SWP_HIDEWINDOW để giấu cửa sổ
        if pos.flags & win32.SWP_HIDEWINDOW:
            pos.flags &= ~win32.SWP_HIDEWINDOW
            pos.flags |= win32.SWP_SHOWWINDOW
            modified = True

        # Luôn duy trì ở đáy (HWND_BOTTOM)
        pos.hwndInsertAfter = win32.HWND_BOTTOM
        return modified
    except Exception as e:
        log.debug("Lỗi handle_windowposchanging: %s", e)
        return False


def pin(hwnd: int) -> bool:
    """Ghim cửa sổ xuống Desktop theo phong cách Rainmeter (Top-Level HWND_BOTTOM)."""
    global last_error
    if not IS_WINDOWS:
        return False
    if not hwnd or not win32.is_window(hwnd):
        return False

    try:
        # Lưu lại exstyle gốc để khôi phục khi unpin
        exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
        style = win32.get_window_long(hwnd, win32.GWL_STYLE)
        _saved_states[hwnd] = _PinState(hwnd=hwnd, exstyle=exstyle, style=style)

        # Cài đặt cờ: WS_EX_TOOLWINDOW để không hiện trên Taskbar/Alt+Tab,
        # WS_EX_NOACTIVATE để click vào không cướp focus
        new_exstyle = exstyle | win32.WS_EX_TOOLWINDOW | win32.WS_EX_NOACTIVATE
        win32.set_window_long(hwnd, win32.GWL_EXSTYLE, new_exstyle)

        # Đặt Z-order ở HWND_BOTTOM
        send_to_bottom(hwnd)

        _pinned_hwnds.add(hwnd)
        last_error = 0
        log.info("Đã ghim cửa sổ %#x xuống Desktop (cơ chế Rainmeter Top-Level)", hwnd)
        return True
    except Exception as e:
        log.warning("Ghim cửa sổ %#x thất bại: %s", hwnd, e)
        last_error = 1
        return False


def unpin(hwnd: int) -> bool:
    """Bỏ ghim, khôi phục cửa sổ về trạng thái bình thường."""
    if not IS_WINDOWS:
        return False
    if not hwnd:
        return False

    try:
        if hwnd in _saved_states:
            state = _saved_states.pop(hwnd)
            win32.set_window_long(hwnd, win32.GWL_EXSTYLE, state.exstyle)

        # Đặt lại Z-order thông thường
        win32.set_window_pos(
            hwnd,
            win32.HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            win32.SWP_NOMOVE | win32.SWP_NOSIZE | win32.SWP_NOACTIVATE,
        )

        _pinned_hwnds.discard(hwnd)
        log.info("Đã bỏ ghim cửa sổ %#x khỏi Desktop", hwnd)
        return True
    except Exception as e:
        log.warning("Bỏ ghim cửa sổ %#x thất bại: %s", hwnd, e)
        return False


def is_pinned(hwnd: int) -> bool:
    """Kiểm tra cửa sổ có đang ở chế độ ghim Desktop hay không."""
    return hwnd in _pinned_hwnds


def monitor() -> bool:
    """Bộ kiểm tra định kỳ (watchdog): duy trì vị trí HWND_BOTTOM cho các cửa sổ đã ghim."""
    if not IS_WINDOWS:
        return True

    alive = True
    for hwnd in list(_pinned_hwnds):
        if not win32.is_window(hwnd):
            _pinned_hwnds.discard(hwnd)
            _saved_states.pop(hwnd, None)
            alive = False
            continue

        # Nếu bị ẩn, kích hoạt lại
        if not win32.is_window_visible(hwnd):
            win32.show_window(hwnd, win32.SW_SHOWNOACTIVATE)

        # Đưa về HWND_BOTTOM
        send_to_bottom(hwnd)

    return alive
