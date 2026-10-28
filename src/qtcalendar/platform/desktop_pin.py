"""Ghim cửa sổ xuống mặt bàn Desktop (sống sót qua ``Win + D``).

Nguyên lý
=========

``Win + D`` (Show Desktop) chỉ thu nhỏ **cửa sổ cấp cao nhất** (top-level).
Nếu cửa sổ của ta trở thành **cửa sổ con của ``Progman``** – cửa sổ nền của
Windows Explorer – thì nó không còn là top-level nữa, không bị liệt kê bởi
``EnumWindows``, và do đó **không bị ẩn**. Nó cũng không xuất hiện trong
Alt+Tab và không tranh focus.

Các bước triển khai (đã kiểm chứng trên Windows 10/11):

1. ``SendMessageTimeout(Progman, 0x052C, 0, 0, SMTO_ABORTIFHUNG, 1000)`` để
   Explorer tạo (nếu chưa có) cửa sổ ``WorkerW`` phục vụ hình nền.
2. Tìm host: ưu tiên ``Progman``; nếu ``Progman`` không có con
   ``SHELLDLL_DefView`` thì tìm top-level ``WorkerW`` có con
   ``SHELLDLL_DefView`` (một số bản Windows đặt icon ở ``WorkerW``).
3. Ghi nhớ style/owner hiện tại, ``SetParent(hwnd, host)``, thêm ``WS_CHILD``
   và bỏ ``WS_POPUP``; giữ nguyên vị trí màn hình bằng cách dùng
   ``MapWindowPoints`` để đổi sang toạ độ client của host.
4. ``SetWindowPos(hwnd, HWND_TOP, …)`` để nằm trên lớp icon.
5. Khi bỏ ghim: ``SetParent(hwnd, 0)``, khôi phục style cũ và vị trí màn
   hình đã lưu.

Hợp đồng API
------------

``find_desktop_host() -> tuple[int, str]``
    ``(hwnd, tên_lớp)``; ``hwnd`` = 0 nếu không tìm thấy.

``pin(hwnd: int) -> bool``
    Ghim; ``False`` nếu thất bại (không có Explorer, API lỗi…).

``unpin(hwnd: int) -> bool``

``is_pinned(hwnd: int) -> bool``
    ``True`` khi parent hiện tại là host desktop còn sống.

``desktop_host_alive() -> bool``
    Explorer còn sống và host vẫn tồn tại (dùng cho watchdog).

``monitor()``
    Bộ theo dõi: nếu cửa sổ bị mất ghim (Explorer khởi động lại) thì ghim
    lại. Thiết kế để app gọi mỗi 2 giây từ một ``QTimer``.

Lưu ý an toàn: mọi hàm trả ``False`` thay vì ném lỗi; tuyệt đối không làm
treo Explorer hay thay đổi cửa sổ nào khác ngoài ``hwnd`` được truyền vào.

Ghi chú triển khai
------------------
* Mỗi HWND được ghim lưu một bản :class:`_PinState` (style, exstyle, owner,
  rect màn hình gốc). Nhờ vậy ``unpin`` khôi phục đúng trạng thái trước khi
  ghim, kể cả khi cửa sổ đã bị đổi kích thước trong lúc ghim.
* ``monitor()`` ghim lại theo **rect hiện tại** (không theo rect gốc) để
  không làm cửa sổ nhảy vị trí nếu người dùng đã kéo nó trước đó.
* :func:`monitor` trả ``bool`` (dù hợp đồng không bắt buộc): ``True`` khi
  mọi cửa sổ đã theo dõi vẫn được ghim. Khi Explorer restart, cửa sổ con của
  ``Progman`` có thể **đã bị huỷ** – lúc đó hàm trả ``False`` và bỏ HWND đó
  khỏi danh sách; app phải tạo lại cửa sổ (rồi gọi :func:`pin` lần nữa).

Ghi chú tích hợp cho ``app.py`` (quan trọng)
--------------------------------------------

1. **Thứ tự gọi**: ``widget.show()`` → lấy ``hwnd = win32.get_hwnd(widget)``
   → ``if desktop_pin.pin(hwnd): ...``. Chỉ ghim sau khi cửa sổ đã có HWND
   thật (``winId()`` buộc Qt tạo native window).
2. **Theo dõi**: tạo ``QTimer`` chu kỳ ~2 giây gọi ``desktop_pin.monitor()``.
   ``monitor()`` chỉ tái ghim các HWND **đã đăng ký qua** :func:`pin`; nó
   không tự tìm HWND mới.
3. **Qt có thể tạo lại HWND**: các lệnh như ``setWindowFlags()`` /
   ``setWindowFlag()`` (đổi "luôn nổi trên cùng", frameless…) có thể khiến
   Qt huỷ và tạo lại native window. Khi đó HWND đổi, mối quan hệ con mất và
   ``monitor()`` không cứu được HWND cũ. Cách đúng: **unpin trước → đổi cờ →
   lấy HWND mới → pin lại**. Đổi ``setWindowOpacity()``/``hide()``/``show()``
   thì an toàn (đã kiểm chứng: vẫn giữ ``WS_CHILD`` + parent).
4. **Toạ độ khi đang ghim**: cửa sổ con dùng toạ độ **client của host**.
   Trên một màn hình chính, ``Progman`` có gốc client ``(0, 0)`` nên
   ``QWidget.move(x, y)`` tình cờ vẫn đúng (Qt vẫn tưởng cửa sổ là top-level
   và gửi toạ độ màn hình). Nhưng nếu host có gốc khác ``(0, 0)`` (đa màn
   hình, host khác) thì ``Qt.move()`` sẽ lệch đúng bằng gốc client của host
   (đã đo trong ``scripts/probe_desktop_pin.py``: lệch ``(320, 150)``).
   ⇒ Khi ghim, muốn đặt vị trí chính xác hãy: (a) ``unpin → widget.move →
   pin``, hoặc (b) tự dịch toạ độ bằng
   ``win32.map_window_points(0, host, x, y)`` rồi dùng
   ``win32.set_window_pos``; hoặc (c) **lưu Settings.x/y lấy từ
   ``GetWindowRect``** thay vì ``QWidget.pos()``.
5. **Quyền (integrity)**: ``SetParent`` sang ``Progman`` (Explorer, Medium
   IL) yêu cầu tiến trình gọi có integrity **≥ Medium**. Nếu app bị chạy
   trong sandbox/restricted token Low IL, ``pin()`` trả ``False`` và
   ``desktop_pin.last_error == 5`` (``ERROR_ACCESS_DENIED``) – đây là rào
   UIPI của Windows, không phải lỗi logic.
6. **Explorer restart**: cửa sổ con của ``Progman`` bị huỷ theo Explorer;
   app cần bắt ``TaskbarCreated`` (hoặc kiểm tra ``monitor() is False`` rồi
   tạo lại cửa sổ/ví dụ ``widget.winId()`` để Qt tạo native window mới) và
   gọi ``pin()`` lại. Kiểu cửa sổ ``Qt.Tool``/``WindowStaysOnTopHint`` không
   cần thiết khi đã ghim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import IS_WINDOWS
from . import win32

__all__ = [
    "find_desktop_host",
    "pin",
    "unpin",
    "is_pinned",
    "desktop_host_alive",
    "monitor",
    "last_error",
]

log = logging.getLogger(__name__)

#: Thông điệp "private" gửi Progman để Explorer sinh cửa sổ WorkerW.
WM_SPAWN_WORKERW = 0x052C

CLASS_PROGMAN = "Progman"
CLASS_WORKERW = "WorkerW"
CLASS_DEFVIEW = "SHELLDLL_DefView"

_SPAWN_TIMEOUT_MS = 1000


@dataclass
class _PinState:
    """Trạng thái một cửa sổ trước khi ghim (để khôi phục khi bỏ ghim)."""

    hwnd: int
    host: int
    host_class: str
    parent: int
    style: int
    exstyle: int
    rect: tuple[int, int, int, int] | None
    owner: int


#: HWND → trạng thái gốc. Chỉ chứa các cửa sổ do app này ghim.
_states: dict[int, _PinState] = {}

#: Mã lỗi Win32 của lần ``pin()`` thất bại gần nhất (0 = không lỗi).
#: Dùng cho ``probe``/log chẩn đoán; app không bắt buộc phải đọc.
last_error: int = 0


# ---------------------------------------------------------------------------
# Tìm host desktop
# ---------------------------------------------------------------------------


def _locate_host() -> tuple[int, str]:
    """Tìm host mà **không** gửi thông điệp sinh WorkerW (an toàn để gọi thường)."""
    try:
        progman = win32.find_window(CLASS_PROGMAN)
        if progman and win32.find_window_ex(progman, 0, CLASS_DEFVIEW):
            return (progman, CLASS_PROGMAN)

        # Một số bản Windows đặt SHELLDLL_DefView trong WorkerW.
        worker = win32.find_window_ex(0, 0, CLASS_WORKERW)
        while worker:
            if win32.find_window_ex(worker, 0, CLASS_DEFVIEW):
                return (worker, CLASS_WORKERW)
            worker = win32.find_window_ex(0, worker, CLASS_WORKERW)

        # Progman vẫn là host dùng được dù không thấy DefView (ví dụ Explorer
        # đang khởi động lại).
        if progman:
            return (progman, CLASS_PROGMAN)
        return (0, "")
    except Exception:
        log.debug("_locate_host thất bại", exc_info=True)
        return (0, "")


def find_desktop_host() -> tuple[int, str]:
    """Tìm cửa sổ nền Desktop: ưu tiên ``Progman``, fallback ``WorkerW``."""
    try:
        if not IS_WINDOWS:
            return (0, "")
        progman = win32.find_window(CLASS_PROGMAN)
        if progman:
            # Bước 1: bảo Explorer sinh WorkerW nếu cần (an toàn, chỉ gửi 1 lần
            # mỗi lần gọi và Explorer bỏ qua nếu đã có).
            win32.send_message_timeout(
                progman,
                WM_SPAWN_WORKERW,
                0,
                0,
                _SPAWN_TIMEOUT_MS,
                win32.SMTO_ABORTIFHUNG,
            )
        host, host_class = _locate_host()
        if not host:
            log.debug("Không tìm thấy host desktop (Explorer đã tắt?)")
        return (host, host_class)
    except Exception:
        log.warning("find_desktop_host thất bại", exc_info=True)
        return (0, "")


def desktop_host_alive() -> bool:
    """Explorer còn sống và cửa sổ host vẫn tồn tại."""
    try:
        if not IS_WINDOWS:
            return False
        host, _ = _locate_host()
        return bool(host) and win32.is_window(host)
    except Exception:
        log.debug("desktop_host_alive thất bại", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Ghim / bỏ ghim
# ---------------------------------------------------------------------------


def _screen_rect_of(hwnd: int) -> tuple[int, int, int, int] | None:
    """Rect màn hình hiện tại của cửa sổ (dùng làm fallback)."""
    rect = win32.get_window_rect(hwnd)
    if rect:
        return rect
    return None


def _apply_pin(state: _PinState, rect: tuple[int, int, int, int] | None = None) -> bool:
    """Áp dụng trạng thái "con của host" cho ``state.hwnd``.

    ``rect`` là rect **màn hình** muốn giữ; ``None`` = dùng rect gốc đã lưu.
    """
    global last_error
    hwnd = state.hwnd
    host = state.host
    if not win32.is_window(hwnd) or not win32.is_window(host):
        return False

    target = rect or state.rect

    # 1) Đổi parent. Với cửa sổ top-level, SetParent trả 0 cho parent cũ (NULL)
    #    nên không thể phân biệt thành công/thất bại chỉ qua giá trị trả về:
    #    phải kiểm tra GetLastError (SetParent thất bại → ERROR_ACCESS_DENIED
    #    hoặc ERROR_INVALID_PARAMETER).
    old_parent = win32.set_parent(hwnd, host)
    error = win32.get_last_error()
    if old_parent == 0 and error:
        last_error = error
        log.warning(
            "SetParent(%#x → %#x) thất bại: Win32 error %s",
            hwnd,
            host,
            error,
        )
        return False

    # 2) Thêm WS_CHILD, bỏ WS_POPUP (SetParent không tự đổi style).
    style = int(state.style)
    was_visible = bool(style & win32.WS_VISIBLE)
    new_style = (style | win32.WS_CHILD) & ~win32.WS_POPUP
    if not was_visible:
        new_style &= ~win32.WS_VISIBLE
    win32.set_window_long(hwnd, win32.GWL_STYLE, new_style)

    # Bỏ WS_EX_APPWINDOW (nếu có) để không bao giờ xuất hiện trên taskbar;
    # exstyle gốc vẫn được lưu để khôi phục khi unpin.
    exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE) or int(state.exstyle)
    new_exstyle = exstyle & ~win32.WS_EX_APPWINDOW
    if new_exstyle != exstyle:
        win32.set_window_long(hwnd, win32.GWL_EXSTYLE, new_exstyle)
    # Windows 11 24H2+: Progman có WS_EX_NOREDIRECTIONBITMAP nên cửa sổ con
    # chỉ được DWM trình chiếu khi là WS_EX_LAYERED (nếu không: vô hình nhưng
    # vẫn nhận chuột). Nếu cửa sổ chưa layered thì bật kèm alpha 255.
    if not (new_exstyle & win32.WS_EX_LAYERED):
        win32.set_layered_alpha(hwnd, 1.0)

    # 3) GetParent chỉ trả về parent khi cửa sổ đã có WS_CHILD.
    if win32.get_parent(hwnd) != host:
        last_error = win32.get_last_error()
        log.warning(
            "Sau SetParent, GetParent(%#x) không phải host %#x (error %s)",
            hwnd,
            host,
            last_error,
        )
        return False

    if target:
        left, top, right, bottom = target
        width = max(1, right - left)
        height = max(1, bottom - top)
        # Toạ độ màn hình → toạ độ client của host (SetParent đổi gốc toạ độ).
        x, y = win32.map_window_points(0, host, left, top)
    else:
        width, height = 1, 1
        x, y = 0, 0

    flags = win32.SWP_NOACTIVATE | win32.SWP_FRAMECHANGED
    if was_visible:
        flags |= win32.SWP_SHOWWINDOW
    win32.set_window_pos(hwnd, win32.HWND_TOP, x, y, width, height, flags)

    # Đảm bảo cửa sổ vẫn nằm trên lớp icon của desktop.
    if was_visible:
        win32.show_window(hwnd, win32.SW_SHOWNOACTIVATE)

    if win32.get_parent(hwnd) != host:
        last_error = win32.get_last_error()
        return False
    return True


def _restore(hwnd: int, state: _PinState) -> bool:
    """Trả cửa sổ về top-level với style/vị trí/owner gốc."""
    try:
        if not win32.is_window(hwnd):
            return False

        win32.set_parent(hwnd, 0)
        style = int(state.style)
        was_visible = bool(style & win32.WS_VISIBLE)
        win32.set_window_long(hwnd, win32.GWL_STYLE, style)
        win32.set_window_long(hwnd, win32.GWL_EXSTYLE, int(state.exstyle))
        if state.owner:
            win32.set_window_long_ptr(hwnd, win32.GWL_HWNDPARENT, int(state.owner))

        if state.rect:
            left, top, right, bottom = state.rect
            width = max(1, right - left)
            height = max(1, bottom - top)
            flags = win32.SWP_NOACTIVATE | win32.SWP_FRAMECHANGED
            if was_visible:
                flags |= win32.SWP_SHOWWINDOW
            win32.set_window_pos(
                hwnd, win32.HWND_NOTOPMOST, left, top, width, height, flags
            )
        if was_visible:
            win32.show_window(hwnd, win32.SW_SHOWNOACTIVATE)
        return win32.get_parent(hwnd) == 0
    except Exception:
        log.warning("_restore(%#x) thất bại", hwnd, exc_info=True)
        return False


def pin(hwnd: int) -> bool:
    """Ghim cửa sổ xuống Desktop; ``False`` nếu không thể (không ném lỗi)."""
    global last_error
    try:
        if not IS_WINDOWS:
            return False
        hwnd = int(hwnd or 0)
        if not hwnd or not win32.is_window(hwnd):
            return False

        state = _states.get(hwnd)
        if state is not None and is_pinned(hwnd):
            last_error = 0
            return True

        last_error = 0
        host, host_class = find_desktop_host()
        if not host:
            log.warning("pin(%#x): không tìm thấy host desktop", hwnd)
            return False

        is_new = state is None
        if state is None:
            state = _PinState(
                hwnd=hwnd,
                host=host,
                host_class=host_class,
                parent=win32.get_parent(hwnd),
                style=win32.get_window_long(hwnd, win32.GWL_STYLE),
                exstyle=win32.get_window_long(hwnd, win32.GWL_EXSTYLE),
                rect=_screen_rect_of(hwnd),
                owner=win32.get_owner(hwnd),
            )
        else:
            # Ghim lại sau khi mất ghim: dùng rect hiện tại để không nhảy vị trí.
            state.host = host
            state.host_class = host_class

        if not _apply_pin(state, rect=state.rect if is_new else _screen_rect_of(hwnd)):
            _restore(hwnd, state)
            return False

        _states[hwnd] = state
        if is_pinned(hwnd):
            last_error = 0
            return True
        return False
    except Exception:
        log.warning("pin(%r) thất bại", hwnd, exc_info=True)
        return False


def unpin(hwnd: int) -> bool:
    """Bỏ ghim, khôi phục style/vị trí cũ; ``False`` nếu không thể."""
    try:
        if not IS_WINDOWS:
            return False
        hwnd = int(hwnd or 0)
        if not hwnd or not win32.is_window(hwnd):
            return False

        state = _states.pop(hwnd, None)
        if state is None:
            style = win32.get_window_long(hwnd, win32.GWL_STYLE)
            # Chưa từng ghim qua module này: không phải cửa sổ con thì no-op.
            if win32.get_parent(hwnd) == 0 and not (style & win32.WS_CHILD):
                return True
            state = _PinState(
                hwnd=hwnd,
                host=0,
                host_class="",
                parent=win32.get_parent(hwnd),
                style=style,
                exstyle=win32.get_window_long(hwnd, win32.GWL_EXSTYLE),
                rect=_screen_rect_of(hwnd),
                owner=win32.get_owner(hwnd),
            )
        return _restore(hwnd, state)
    except Exception:
        log.warning("unpin(%r) thất bại", hwnd, exc_info=True)
        return False


def is_pinned(hwnd: int) -> bool:
    """Cửa sổ hiện là con của host desktop và host còn sống."""
    try:
        if not IS_WINDOWS:
            return False
        hwnd = int(hwnd or 0)
        if not hwnd or not win32.is_window(hwnd):
            return False
        host, _ = _locate_host()
        if not host:
            return False
        if win32.get_parent(hwnd) != host:
            return False
        style = win32.get_window_long(hwnd, win32.GWL_STYLE)
        return bool(style & win32.WS_CHILD)
    except Exception:
        log.debug("is_pinned thất bại", exc_info=True)
        return False


def monitor() -> bool:
    """Ghim lại các cửa sổ đã mất ghim (Explorer restart).

    Gọi mỗi ~2 giây từ ``QTimer``. Trả ``False`` nếu có cửa sổ không thể giữ
    ghim (đã bị huỷ) hoặc không tìm thấy host.
    """
    try:
        if not IS_WINDOWS:
            return False
        if not _states:
            # Không có cửa sổ nào cần theo dõi: coi như "không có gì phải làm".
            return True

        host, host_class = _locate_host()
        if not host:
            return False

        ok = True
        for hwnd, state in list(_states.items()):
            try:
                if not win32.is_window(hwnd):
                    log.warning(
                        "monitor: cửa sổ %#x đã bị huỷ (Explorer restart?) – bỏ theo dõi",
                        hwnd,
                    )
                    _states.pop(hwnd, None)
                    ok = False
                    continue
                if win32.get_parent(hwnd) == host:
                    continue
                state.host = host
                state.host_class = host_class
                current = _screen_rect_of(hwnd)
                if not _apply_pin(state, rect=current):
                    log.warning("monitor: ghim lại %#x thất bại", hwnd)
                    ok = False
            except Exception:
                log.warning("monitor: lỗi khi xử lý %#x", hwnd, exc_info=True)
                ok = False
        return ok
    except Exception:
        log.warning("monitor thất bại", exc_info=True)
        return False
