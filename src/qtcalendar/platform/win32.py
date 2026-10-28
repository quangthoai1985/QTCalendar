"""Khai báo ``ctypes`` cho Win32 API và các hàm tiện ích.

Hợp đồng API (phải giữ đúng tên và chữ ký để ``desktop_pin``/``app`` dùng):

Hằng số
-------
``GWL_STYLE``, ``GWL_EXSTYLE``, ``WS_CHILD``, ``WS_POPUP``, ``WS_VISIBLE``,
``WS_EX_TOOLWINDOW``, ``WS_EX_NOACTIVATE``, ``HWND_TOP``, ``SW_HIDE``,
``SW_SHOW``, ``SW_SHOWNOACTIVATE``, ``HWND_NOTOPMOST``, ``SMTO_ABORTIFHUNG``

Hàm
---
``get_hwnd(widget_or_int) -> int``
    Lấy HWND từ ``QWidget`` (gọi ``int(widget.winId())``).

``find_window(class_name: str, title: str | None = None) -> int``
    ``FindWindowW``; trả 0 nếu không thấy.

``find_window_ex(parent: int, after: int, class_name: str, title=None) -> int``

``enum_windows() -> list[int]``
    Liệt kê toàn bộ cửa sổ cấp cao nhất.

``get_class_name(hwnd: int) -> str``
    Tên lớp cửa sổ, ví dụ ``"Progman"``, ``"WorkerW"``.

``get_parent(hwnd) -> int`` / ``set_parent(hwnd, parent) -> int``
    Trả về parent cũ.

``get_window_long(hwnd, index) -> int`` / ``set_window_long(hwnd, index, value) -> int``

``get_window_rect(hwnd) -> tuple[int, int, int, int] | None``
    ``(left, top, right, bottom)`` theo toạ độ màn hình vật lý.

``get_client_rect(hwnd) -> tuple[int, int, int, int] | None``

``is_window(hwnd) -> bool`` / ``is_window_visible(hwnd) -> bool``

``show_window(hwnd, cmd) -> bool``

``set_window_pos(hwnd, insert_after, x, y, w, h, flags=0) -> bool``

``map_window_points(hwnd_from, hwnd_to, x, y) -> tuple[int, int]``
    Đổi toạ độ giữa hai cửa sổ (dùng khi SetParent làm đổi gốc toạ độ).

``send_message_timeout(hwnd, msg, wparam, lparam, timeout_ms=1000) -> int | None``

``screen_rect() -> tuple[int, int, int, int]``
    Toạ độ màn hình ảo (``SM_XVIRTUALSCREEN``…).

Yêu cầu: chỉ dùng ``ctypes`` thuần (không thêm thư viện), mọi hàm bọc
``try/except`` trả giá trị "không làm gì" khi lỗi.

Ghi chú triển khai
------------------
* Toàn bộ con trỏ cửa sổ dùng ``ctypes.c_void_p`` nên an toàn trên cả
  tiến trình 32-bit lẫn 64-bit.
* Các index ``GWL_STYLE`` / ``GWL_EXSTYLE`` là số 32-bit nên dùng
  ``GetWindowLongW``/``SetWindowLongW``; giá trị trả về được che về
  ``0xFFFFFFFF`` để tránh bit dấu của ``WS_POPUP`` (0x80000000).
* Trên hệ điều hành không phải Windows module vẫn import được: mọi hàm
  trả giá trị rỗng thay vì ném ``AttributeError``/``OSError``.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

__all__ = [
    # hằng số
    "GWL_STYLE",
    "GWL_EXSTYLE",
    "WS_CHILD",
    "WS_POPUP",
    "WS_VISIBLE",
    "WS_EX_TOOLWINDOW",
    "WS_EX_NOACTIVATE",
    "HWND_TOP",
    "SW_HIDE",
    "SW_SHOW",
    "SW_SHOWNOACTIVATE",
    "HWND_NOTOPMOST",
    "SMTO_ABORTIFHUNG",
    # hàm
    "get_hwnd",
    "find_window",
    "find_window_ex",
    "enum_windows",
    "get_class_name",
    "get_parent",
    "set_parent",
    "get_window_long",
    "set_window_long",
    "get_window_long_ptr",
    "set_window_long_ptr",
    "get_owner",
    "get_last_error",
    "get_window_rect",
    "get_client_rect",
    "is_window",
    "is_window_visible",
    "show_window",
    "set_window_pos",
    "map_window_points",
    "send_message_timeout",
    "screen_rect",
]

log = logging.getLogger(__name__)

IS_WINDOWS: bool = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Hằng số Win32
# ---------------------------------------------------------------------------

GWL_STYLE = -16
GWL_EXSTYLE = -20
GWL_HWNDPARENT = -8  #: đặt owner cho top-level / parent cho cửa sổ con

WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000

#: Hằng số GetWindow() để duyệt z-order
GW_HWNDPREV = 3
GW_HWNDNEXT = 2

#: Hằng số cho SetLayeredWindowAttributes
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002
HWND_TOP = 0
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080
SWP_NOOWNERZORDER = 0x0200

SMTO_NORMAL = 0x0000
SMTO_BLOCK = 0x0001
SMTO_ABORTIFHUNG = 0x0002

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

GW_OWNER = 4
GW_CHILD = 5

# ---------------------------------------------------------------------------
# Nạp DLL (chỉ trên Windows; nơi khác để ``None``)
# ---------------------------------------------------------------------------

user32: "ctypes.WinDLL | None" = None
shell32: "ctypes.WinDLL | None" = None
kernel32: "ctypes.WinDLL | None" = None
gdi32: "ctypes.WinDLL | None" = None

_WNDENUMPROC = None
if IS_WINDOWS:
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    except OSError:  # pragma: no cover - chỉ xảy ra trên Windows hỏng
        log.warning("Không nạp được user32/shell32/kernel32", exc_info=True)


def _configure_prototypes() -> None:
    """Khai báo argtypes/restype một lần cho toàn bộ API dùng ở đây."""
    if user32 is None:
        return
    try:
        u = user32
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND

        u.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
        u.SetParent.restype = wintypes.HWND

        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindow.restype = wintypes.HWND

        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long

        u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        u.SetWindowLongW.restype = ctypes.c_long

        u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t

        u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        u.SetWindowLongPtrW.restype = ctypes.c_ssize_t

        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL

        u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetClientRect.restype = wintypes.BOOL

        u.IsWindow.argtypes = [wintypes.HWND]
        u.IsWindow.restype = wintypes.BOOL

        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsWindowVisible.restype = wintypes.BOOL

        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.ShowWindow.restype = wintypes.BOOL

        u.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        u.SetWindowPos.restype = wintypes.BOOL

        u.MapWindowPoints.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.POINTER(wintypes.POINT),
            wintypes.UINT,
        ]
        u.MapWindowPoints.restype = ctypes.c_int

        u.SendMessageTimeoutW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        u.SendMessageTimeoutW.restype = ctypes.c_ssize_t

        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowW.restype = wintypes.HWND

        u.FindWindowExW.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
        ]
        u.FindWindowExW.restype = wintypes.HWND

        u.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL

        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int

        u.GetSystemMetrics.argtypes = [ctypes.c_int]
        u.GetSystemMetrics.restype = ctypes.c_int
    except (AttributeError, TypeError):  # pragma: no cover - Windows lạ
        log.warning("Không khai báo được đầy đủ prototype Win32", exc_info=True)


_configure_prototypes()


# ---------------------------------------------------------------------------
# Tiện ích nội bộ
# ---------------------------------------------------------------------------


def _to_hwnd(value) -> int:
    """Chuẩn hoá bất kỳ handle nào về ``int`` (0 = không có)."""
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _mask32(value) -> int:
    """Che giá trị về 32-bit không dấu (style/exstyle)."""
    try:
        return int(value) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return 0


def _signed32(value) -> int:
    """Đổi số 32-bit không dấu sang ``LONG`` có dấu để truyền vào API."""
    v = _mask32(value)
    if v & 0x80000000:
        v -= 0x100000000
    return v


def get_last_error() -> int:
    """Mã lỗi Win32 gần nhất (``ctypes.get_last_error``); 0 nếu không có."""
    try:
        return int(ctypes.get_last_error())
    except Exception:  # pragma: no cover
        return 0


# ---------------------------------------------------------------------------
# Hàm công khai
# ---------------------------------------------------------------------------


def get_hwnd(widget_or_int) -> int:
    """Lấy HWND từ ``QWidget`` (hoặc trả nguyên ``int`` nếu đã là HWND)."""
    try:
        if widget_or_int is None:
            return 0
        if isinstance(widget_or_int, int):
            return widget_or_int
        win_id = widget_or_int.winId()
        return _to_hwnd(win_id)
    except Exception:  # pragma: no cover - Qt object lạ
        log.debug("get_hwnd thất bại", exc_info=True)
        return 0


def find_window(class_name: str, title: str | None = None) -> int:
    """``FindWindowW`` – trả 0 nếu không tìm thấy hoặc lỗi."""
    try:
        if user32 is None:
            return 0
        hwnd = user32.FindWindowW(class_name if class_name else None, title)
        return _to_hwnd(hwnd)
    except Exception:
        log.debug("find_window(%r) thất bại", class_name, exc_info=True)
        return 0


def find_window_ex(
    parent: int,
    after: int,
    class_name: str,
    title: str | None = None,
) -> int:
    """``FindWindowExW`` – tìm cửa sổ con/anh em cùng lớp."""
    try:
        if user32 is None:
            return 0
        hwnd = user32.FindWindowExW(
            wintypes.HWND(parent or 0),
            wintypes.HWND(after or 0),
            class_name if class_name else None,
            title,
        )
        return _to_hwnd(hwnd)
    except Exception:
        log.debug("find_window_ex(%r) thất bại", class_name, exc_info=True)
        return 0


def enum_windows() -> list[int]:
    """Liệt kê toàn bộ cửa sổ cấp cao nhất (top-level)."""
    result: list[int] = []
    if user32 is None or _WNDENUMPROC is None:
        return result

    def _callback(hwnd, _lparam):  # noqa: ANN001 - do Win32 gọi
        try:
            value = _to_hwnd(hwnd)
            if value:
                result.append(value)
        except Exception:  # pragma: no cover
            pass
        return True

    try:
        callback = _WNDENUMPROC(_callback)
        user32.EnumWindows(callback, 0)
    except Exception:
        log.debug("enum_windows thất bại", exc_info=True)
        return []
    return result


def get_class_name(hwnd: int) -> str:
    """Tên lớp cửa sổ (``"Progman"``, ``"WorkerW"``…); lỗi trả ``""``."""
    try:
        if user32 is None or not hwnd:
            return ""
        buffer = ctypes.create_unicode_buffer(256)
        length = user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
        if length <= 0:
            return ""
        return buffer.value
    except Exception:
        log.debug("get_class_name thất bại", exc_info=True)
        return ""


def get_parent(hwnd: int) -> int:
    """Handle cửa sổ cha (0 nếu top-level hoặc lỗi)."""
    try:
        if user32 is None or not hwnd:
            return 0
        return _to_hwnd(user32.GetParent(wintypes.HWND(hwnd)))
    except Exception:
        log.debug("get_parent thất bại", exc_info=True)
        return 0


def set_parent(hwnd: int, parent: int) -> int:
    """``SetParent`` – trả parent **cũ** (0 nếu trước đó là top-level hoặc lỗi)."""
    try:
        if user32 is None or not hwnd:
            return 0
        ctypes.set_last_error(0)
        old = user32.SetParent(wintypes.HWND(hwnd), wintypes.HWND(parent or 0))
        if not old:
            error = ctypes.get_last_error()
            if error:
                log.debug("SetParent lỗi Win32 %s", error)
        return _to_hwnd(old)
    except Exception:
        log.debug("set_parent thất bại", exc_info=True)
        return 0


def get_window_long(hwnd: int, index: int) -> int:
    """Đọc ``GWLP_*`` 32-bit (style/exstyle) – trả số không dấu."""
    try:
        if user32 is None or not hwnd:
            return 0
        value = user32.GetWindowLongW(wintypes.HWND(hwnd), int(index))
        return _mask32(value)
    except Exception:
        log.debug("get_window_long thất bại", exc_info=True)
        return 0


def set_window_long(hwnd: int, index: int, value: int) -> int:
    """Ghi ``GWLP_*`` 32-bit – trả giá trị **cũ** (0 nếu lỗi)."""
    try:
        if user32 is None or not hwnd:
            return 0
        ctypes.set_last_error(0)
        old = user32.SetWindowLongW(wintypes.HWND(hwnd), int(index), ctypes.c_long(_signed32(value)))
        if not old:
            error = ctypes.get_last_error()
            if error:
                log.debug("SetWindowLongW lỗi Win32 %s", error)
        return _mask32(old)
    except Exception:
        log.debug("set_window_long thất bại", exc_info=True)
        return 0


def get_window_long_ptr(hwnd: int, index: int) -> int:
    """Đọc ``GWLP_*`` cỡ con trỏ (dùng cho ``GWLP_HWNDPARENT``/owner)."""
    try:
        if user32 is None or not hwnd:
            return 0
        ctypes.set_last_error(0)
        value = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), int(index))
        if not value:
            error = ctypes.get_last_error()
            if error:
                log.debug("GetWindowLongPtrW lỗi Win32 %s", error)
        return _to_hwnd(value)
    except Exception:
        log.debug("get_window_long_ptr thất bại", exc_info=True)
        return 0


def set_window_long_ptr(hwnd: int, index: int, value: int) -> int:
    """Ghi ``GWLP_*`` cỡ con trỏ – trả giá trị **cũ** (0 nếu lỗi)."""
    try:
        if user32 is None or not hwnd:
            return 0
        ctypes.set_last_error(0)
        old = user32.SetWindowLongPtrW(wintypes.HWND(hwnd), int(index), ctypes.c_ssize_t(int(value)))
        if not old:
            error = ctypes.get_last_error()
            if error:
                log.debug("SetWindowLongPtrW lỗi Win32 %s", error)
        return _to_hwnd(old)
    except Exception:
        log.debug("set_window_long_ptr thất bại", exc_info=True)
        return 0


def get_owner(hwnd: int) -> int:
    """Handle cửa sổ sở hữu (owner) của một top-level window."""
    try:
        if user32 is None or not hwnd:
            return 0
        return _to_hwnd(user32.GetWindow(wintypes.HWND(hwnd), GW_OWNER))
    except Exception:
        log.debug("get_owner thất bại", exc_info=True)
        return 0


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """``(left, top, right, bottom)`` theo toạ độ màn hình vật lý."""
    try:
        if user32 is None or not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        log.debug("get_window_rect thất bại", exc_info=True)
        return None


def get_client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """``(left, top, right, bottom)`` của vùng client (left/top thường = 0)."""
    try:
        if user32 is None or not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        log.debug("get_client_rect thất bại", exc_info=True)
        return None


def is_window(hwnd: int) -> bool:
    """Cửa sổ còn tồn tại và handle còn hợp lệ."""
    try:
        if user32 is None or not hwnd:
            return False
        return bool(user32.IsWindow(wintypes.HWND(hwnd)))
    except Exception:
        return False


def is_window_visible(hwnd: int) -> bool:
    """Cửa sổ đang được hiển thị (``IsWindowVisible``)."""
    try:
        if user32 is None or not hwnd:
            return False
        return bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))
    except Exception:
        return False


def set_layered_alpha(hwnd: int, alpha: float) -> bool:
    """Bật ``WS_EX_LAYERED`` và đặt độ mờ **toàn cửa sổ** (``LWA_ALPHA``).

    Đây là cách làm trong suốt duy nhất còn đúng khi cửa sổ đã trở thành
    **cửa sổ con** (``SetParent`` xuống Progman): Windows không ghép kênh alpha
    theo từng điểm ảnh cho cửa sổ con, nhưng ``LWA_ALPHA`` thì vẫn chạy từ
    Windows 8 trở lên. Trả ``False`` nếu không áp được.
    """
    try:
        if user32 is None or not hwnd or not is_window(hwnd):
            return False
        exstyle = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, exstyle | WS_EX_LAYERED)
        value = max(0, min(255, int(round(max(0.0, min(1.0, float(alpha))) * 255))))
        ok = bool(
            user32.SetLayeredWindowAttributes(
                wintypes.HWND(hwnd), 0, value, LWA_ALPHA
            )
        )
        if not ok:
            log.debug("SetLayeredWindowAttributes lỗi Win32 %s", get_last_error())
        return ok
    except Exception:
        log.debug("set_layered_alpha thất bại", exc_info=True)
        return False


def clear_layered(hwnd: int) -> bool:
    """Gỡ ``WS_EX_LAYERED`` để cửa sổ vẽ thường (dùng khi bỏ ghim)."""
    try:
        if user32 is None or not hwnd or not is_window(hwnd):
            return False
        exstyle = get_window_long(hwnd, GWL_EXSTYLE)
        if exstyle & WS_EX_LAYERED:
            set_window_long(hwnd, GWL_EXSTYLE, exstyle & ~WS_EX_LAYERED)
        return True
    except Exception:
        log.debug("clear_layered thất bại", exc_info=True)
        return False


def get_pixel(x: int, y: int) -> tuple[int, int, int] | None:
    """Đọc màu điểm ảnh trên màn hình tại toạ độ màn hình ``(x, y)``.

    Dùng cho bước tự kiểm tra "cửa sổ ghim có thật sự nhìn thấy không".
    Trả ``None`` nếu không đọc được.
    """
    try:
        if user32 is None or gdi32 is None:
            return None
        hdc = user32.GetDC(0)
        if not hdc:
            return None
        try:
            value = gdi32.GetPixel(hdc, int(x), int(y))
        finally:
            user32.ReleaseDC(0, hdc)
        if value is None or int(value) < 0:
            return None
        color = int(value)
        return (color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF)
    except Exception:
        log.debug("get_pixel thất bại", exc_info=True)
        return None


def get_window(hwnd: int, cmd: int) -> int:
    """Lấy cửa sổ liên quan theo ``cmd`` (``GW_HWNDPREV``/``GW_HWNDNEXT``…)."""
    try:
        if user32 is None or not hwnd:
            return 0
        return _to_hwnd(user32.GetWindow(wintypes.HWND(hwnd), int(cmd)))
    except Exception:
        log.debug("get_window thất bại", exc_info=True)
        return 0


def show_window(hwnd: int, cmd: int) -> bool:
    """``ShowWindow`` – trả ``True`` nếu cửa sổ vẫn hợp lệ sau lời gọi."""
    try:
        if user32 is None or not hwnd:
            return False
        user32.ShowWindow(wintypes.HWND(hwnd), int(cmd))
        return is_window(hwnd)
    except Exception:
        log.debug("show_window thất bại", exc_info=True)
        return False


def set_window_pos(
    hwnd: int,
    insert_after: int,
    x: int,
    y: int,
    w: int,
    h: int,
    flags: int = 0,
) -> bool:
    """``SetWindowPos`` – trả ``True`` khi thành công."""
    try:
        if user32 is None or not hwnd:
            return False
        ok = user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(int(insert_after or 0)),
            int(x),
            int(y),
            int(w),
            int(h),
            int(flags) & 0xFFFFFFFF,
        )
        return bool(ok)
    except Exception:
        log.debug("set_window_pos thất bại", exc_info=True)
        return False


def map_window_points(hwnd_from: int, hwnd_to: int, x: int, y: int) -> tuple[int, int]:
    """Đổi ``(x, y)`` từ hệ toạ độ ``hwnd_from`` sang ``hwnd_to``.

    ``hwnd_from = 0`` nghĩa là toạ độ màn hình (desktop). Trường hợp API trả 0
    nhưng ``GetLastError() == 0`` (phép biến đổi đồng nhất), vẫn dùng kết quả
    đã ghi vào ``POINT``.
    """
    try:
        if user32 is None:
            return (int(x), int(y))
        point = wintypes.POINT(int(x), int(y))
        ctypes.set_last_error(0)
        result = user32.MapWindowPoints(
            wintypes.HWND(hwnd_from or 0),
            wintypes.HWND(hwnd_to or 0),
            ctypes.byref(point),
            1,
        )
        if result == 0 and ctypes.get_last_error():
            log.debug("MapWindowPoints thất bại")
            return (int(x), int(y))
        return (int(point.x), int(point.y))
    except Exception:
        log.debug("map_window_points thất bại", exc_info=True)
        return (int(x), int(y))


def send_message_timeout(
    hwnd: int,
    msg: int,
    wparam: int,
    lparam: int,
    timeout_ms: int = 1000,
    flags: int = SMTO_ABORTIFHUNG,
) -> int | None:
    """``SendMessageTimeoutW`` – trả kết quả thông điệp, ``None`` nếu timeout/lỗi."""
    try:
        if user32 is None or not hwnd:
            return None
        result = ctypes.c_size_t(0)
        ok = user32.SendMessageTimeoutW(
            wintypes.HWND(hwnd),
            int(msg) & 0xFFFFFFFF,
            wintypes.WPARAM(int(wparam)),
            wintypes.LPARAM(int(lparam)),
            int(flags) & 0xFFFFFFFF,
            int(timeout_ms),
            ctypes.byref(result),
        )
        if not ok:
            log.debug("SendMessageTimeoutW timeout/lỗi (msg=0x%X)", int(msg))
            return None
        return int(result.value)
    except Exception:
        log.debug("send_message_timeout thất bại", exc_info=True)
        return None


def screen_rect() -> tuple[int, int, int, int]:
    """``(x, y, width, height)`` của toàn bộ màn hình ảo."""
    try:
        if user32 is None:
            return (0, 0, 0, 0)
        x = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
        y = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
        width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        if width <= 0 or height <= 0:
            width = int(user32.GetSystemMetrics(SM_CXSCREEN))
            height = int(user32.GetSystemMetrics(SM_CYSCREEN))
        return (x, y, width, height)
    except Exception:
        log.debug("screen_rect thất bại", exc_info=True)
        return (0, 0, 0, 0)
