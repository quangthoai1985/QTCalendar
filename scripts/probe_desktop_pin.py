"""Probe thực nghiệm: ghim một cửa sổ Qt xuống Desktop bằng ``SetParent(Progman)``.

Script này là **công cụ kiểm chứng an toàn**, chỉ tạo MỘT cửa sổ test nhỏ màu
đỏ của chính nó, ghim xuống desktop, đo đạc bằng Win32 API rồi bỏ ghim và
đóng cửa sổ. Tuyệt đối **không** gửi ``Win + D``, không ẩn/đóng cửa sổ của
người dùng, không can thiệp vào cửa sổ nào khác.

Cách chạy (từ gốc dự án)::

    $env:PYTHONUTF8="1"; python -X utf8 scripts/probe_desktop_pin.py

Nội dung in ra:

0. Môi trường: Python/PySide6/Qt, màn hình, DPI, quyền (integrity level),
   handle ``Progman``.
1. **PHA 1 – ghim thật**: ``desktop_pin.pin()`` → so sánh parent với
   ``Progman``, ``IsWindowVisible``, ``GetWindowRect``, bit ``WS_CHILD``, còn
   trong ``EnumWindows`` không; thử ``QWidget.move()``/``resize()`` khi đang
   ghim; chụp màn hình; ``unpin()`` rồi kiểm tra khôi phục.
2. **PHA 2 – kiểm chứng giải thuật** (chỉ chạy như chẩn đoán): nếu môi trường
   đang chạy bị sandbox Low Integrity (UIPI chặn ``SetParent`` sang cửa sổ
   Explorer Medium IL), ghim thử vào một **host cùng tiến trình** để kiểm tra
   đầy đủ các bước style/``MapWindowPoints``/Qt toạ độ/``monitor()``. Pha này
   KHÔNG phải desktop thật và được ghi rõ trong output.
3. **PHA 3 – SetParent xuyên tiến trình**: tạo một tiến trình Python khác làm
   host (cùng integrity) rồi ghim vào đó. Nếu thành công nghĩa là ``SetParent``
   xuyên tiến trình được phép; rào chắn ở PHA 1 chỉ là UIPI do lệch integrity.
4. Chụp toàn màn hình (``QScreen.grabWindow(0)``) lưu vào ``%TEMP%``.

Kết thúc: luôn ``unpin`` + đóng các cửa sổ test, kể cả khi có lỗi giữa chừng.
"""

from __future__ import annotations

import ctypes
import sys
import tempfile
import time
import traceback
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Nạp gói qtcalendar từ src/ (chạy trực tiếp bằng python, không cần cài đặt)
# ---------------------------------------------------------------------------


def _bootstrap() -> Path:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return root


ROOT = _bootstrap()

from PySide6.QtCore import Qt, qVersion  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from qtcalendar.platform import IS_WINDOWS, desktop_pin, win32  # noqa: E402


# ---------------------------------------------------------------------------
# In ấn
# ---------------------------------------------------------------------------


def say(text: str = "") -> None:
    print(text, flush=True)


def hx(value) -> str:
    try:
        return f"0x{int(value):X}"
    except (TypeError, ValueError):
        return "0x0"


def rect_text(rect) -> str:
    if not rect:
        return "None"
    left, top, right, bottom = rect
    return f"({left}, {top}, {right}, {bottom}) → {right - left}x{bottom - top}"


def style_text(style: int) -> str:
    flags = []
    if style & win32.WS_CHILD:
        flags.append("WS_CHILD")
    if style & win32.WS_POPUP:
        flags.append("WS_POPUP")
    if style & win32.WS_VISIBLE:
        flags.append("WS_VISIBLE")
    return f"0x{style:08X} [{', '.join(flags) or '—'}]"


def exstyle_text(exstyle: int) -> str:
    flags = []
    if exstyle & win32.WS_EX_TOOLWINDOW:
        flags.append("WS_EX_TOOLWINDOW")
    if exstyle & win32.WS_EX_APPWINDOW:
        flags.append("WS_EX_APPWINDOW")
    if exstyle & win32.WS_EX_TOPMOST:
        flags.append("WS_EX_TOPMOST")
    if exstyle & win32.WS_EX_LAYERED:
        flags.append("WS_EX_LAYERED")
    if exstyle & win32.WS_EX_NOACTIVATE:
        flags.append("WS_EX_NOACTIVATE")
    return f"0x{exstyle:08X} [{', '.join(flags) or '—'}]"


def pump(app: QApplication, ms: int = 200) -> None:
    """Bơm event loop Qt trong ``ms`` mili-giây (không chặn UI)."""
    deadline = time.monotonic() + max(0, ms) / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


# ---------------------------------------------------------------------------
# Quyền của tiến trình (integrity level) – để giải thích vì sao pin bị chặn
# ---------------------------------------------------------------------------

_INTEGRITY_LABELS = {
    0x0000: "Untrusted",
    0x1000: "Low",
    0x2000: "Medium",
    0x3000: "High",
    0x4000: "System",
    0x5000: "Protected",
}


def process_integrity() -> tuple[str, str]:
    """Trả ``(nhãn, SID)`` mức toàn vẹn của tiến trình, ví dụ ``("Low", "S-1-16-4096")``."""
    try:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        advapi.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi.OpenProcessToken.restype = wintypes.BOOL
        advapi.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.GetTokenInformation.restype = wintypes.BOOL
        advapi.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        advapi.ConvertSidToStringSidW.restype = wintypes.BOOL

        token = wintypes.HANDLE()
        if not advapi.OpenProcessToken(
            kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        ):  # TOKEN_QUERY
            return ("?", "?")
        need = wintypes.DWORD(0)
        advapi.GetTokenInformation(token, 25, None, 0, ctypes.byref(need))  # TokenIntegrityLevel
        buf = ctypes.create_string_buffer(need.value)
        if not advapi.GetTokenInformation(
            token, 25, buf, need.value, ctypes.byref(need)
        ):
            return ("?", "?")
        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        sid_text = ctypes.c_wchar_p()
        if not advapi.ConvertSidToStringSidW(sid_ptr, ctypes.byref(sid_text)):
            return ("?", "?")
        sid = sid_text.value or "?"
        try:
            rid = int(sid.rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            rid = -1
        return (_INTEGRITY_LABELS.get(rid, f"RID {rid}"), sid)
    except Exception:
        return ("?", "?")


# ---------------------------------------------------------------------------
# Đo đạc / chụp màn hình
# ---------------------------------------------------------------------------


def snapshot(tag: str, widget: QWidget, hwnd: int) -> dict:
    """In + trả về trạng thái hiện tại của cửa sổ test."""
    say(f"--- {tag} ---")
    parent = win32.get_parent(hwnd)
    visible = win32.is_window_visible(hwnd)
    rect = win32.get_window_rect(hwnd)
    style = win32.get_window_long(hwnd, win32.GWL_STYLE)
    exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
    cls = win32.get_class_name(hwnd)

    say(f"HWND              : {hx(hwnd)}  (lớp {cls!r})")
    say(f"GetParent         : {hx(parent)}")
    say(f"IsWindowVisible   : {visible}")
    say(f"GetWindowRect     : {rect_text(rect)}")
    say(f"GWL_STYLE         : {style_text(style)}")
    say(f"GWL_EXSTYLE       : {exstyle_text(exstyle)}")
    try:
        pos = widget.pos()
        geom = widget.geometry()
        frame = widget.frameGeometry()
        say(
            "Qt pos/geometry   : "
            f"pos=({pos.x()}, {pos.y()}) "
            f"geometry=({geom.x()}, {geom.y()}, {geom.width()}, {geom.height()}) "
            f"frameGeometry=({frame.x()}, {frame.y()}, "
            f"{frame.width()}, {frame.height()})"
        )
        say(
            f"Qt size/isWindow  : size={widget.width()}x{widget.height()} "
            f"isVisible={widget.isVisible()} "
            f"devicePixelRatio={widget.devicePixelRatioF():.3f}"
        )
    except Exception:
        say("Qt pos/geometry   : <lỗi đọc thuộc tính Qt>")
    say("")
    return {
        "parent": parent,
        "visible": visible,
        "rect": rect,
        "style": style,
        "exstyle": exstyle,
    }


def capture_screen(app: QApplication, tag: str) -> Path | None:
    """Chụp toàn màn hình vào ``%TEMP%\\QTCalendar\\…png`` và in đường dẫn."""
    try:
        out_dir = Path(tempfile.gettempdir()) / "QTCalendar"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = out_dir / f"probe_desktop_pin_{tag}_{stamp}.png"
        screen = app.primaryScreen()
        if screen is None:
            say(f"Ảnh chụp màn hình ({tag}) : <không có QScreen>")
            return None
        shot = screen.grabWindow(0)
        saved = shot.save(str(path), "PNG")
        size = path.stat().st_size if path.is_file() else 0
        if saved and size:
            say(f"Ảnh chụp màn hình ({tag}) : {path}")
            say(f"  kích thước ảnh          : {shot.width()}x{shot.height()} px, {size} bytes")
            return path
        say(f"Ảnh chụp màn hình ({tag}) : lưu thất bại ({path}, saved={saved})")
        return None
    except Exception:
        say("Ảnh chụp màn hình: lỗi")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Các pha kiểm chứng
# ---------------------------------------------------------------------------


def _verify_pinned(tag: str, widget: QWidget, hwnd: int, host: int, host_label: str) -> dict:
    """In bảng kiểm tra khi cửa sổ đang được ghim vào ``host``."""
    post = snapshot(tag, widget, hwnd)
    say("KIỂM TRA GHIM:")
    say(f"  GetParent == host ({host_label})?      : {post['parent'] == host}")
    say(f"  GetParent                       : {hx(post['parent'])}  host={hx(host)}")
    say(f"  Có bit WS_CHILD?                    : {bool(post['style'] & win32.WS_CHILD)}")
    say(f"  Còn bit WS_POPUP?                   : {bool(post['style'] & win32.WS_POPUP)}")
    say(f"  IsWindowVisible?                    : {post['visible']}")
    say(f"  desktop_pin.is_pinned(hwnd)         : {desktop_pin.is_pinned(hwnd)}")
    say(f"  HWND còn trong EnumWindows?         : {hwnd in win32.enum_windows()}")
    return post


def _qt_move_test(app: QApplication, widget: QWidget, hwnd: int, target: tuple[int, int]) -> dict:
    """Đo hiện tượng ``QWidget.move()`` khi cửa sổ đang là cửa sổ con."""
    before = win32.get_window_rect(hwnd)
    widget.move(target[0], target[1])
    pump(app, 300)
    after = win32.get_window_rect(hwnd)
    pos = widget.pos()
    say("THỬ Qt.move() KHI ĐANG GHIM:")
    say(f"  Qt.move({target[0]}, {target[1]})")
    say(f"  rect trước move : {rect_text(before)}")
    say(f"  rect sau  move  : {rect_text(after)}")
    say(f"  rect có đổi?    : {after != before}")
    say(f"  Qt.pos() sau move: ({pos.x()}, {pos.y()})")
    if after:
        say(
            "  GetWindowRect khớp toạ độ Qt.move?: "
            f"{(after[0], after[1]) == tuple(target)}"
        )
    say("")
    return {"before": before, "after": after}


def _qt_resize_test(app: QApplication, widget: QWidget, hwnd: int) -> dict:
    widget.resize(360, 240)
    pump(app, 250)
    rect = win32.get_window_rect(hwnd)
    say("THỬ Qt.resize() KHI ĐANG GHIM:")
    say(f"  Qt.resize(360, 240) → rect: {rect_text(rect)}")
    if rect:
        say(
            "  kích thước Win32 khớp 360x240?: "
            f"{rect[2] - rect[0]}x{rect[3] - rect[1]}"
            f" (Qt size {widget.width()}x{widget.height()})"
        )
    say("")
    return {"rect": rect}


def phase1_desktop(app: QApplication, widget: QWidget, hwnd: int) -> dict:
    """Ghim thật xuống Desktop (Progman) – pha chính của probe."""
    say("#" * 78)
    say("# PHA 1 – GHIM XUỐNG DESKTOP THẬT (Progman)")
    say("#" * 78)
    progman = win32.find_window("Progman")
    say(f"Progman HWND: {hx(progman)} (class={win32.get_class_name(progman)!r})")

    host, host_class = desktop_pin.find_desktop_host()
    say(f"Host desktop: {hx(host)} (class={host_class!r}) | trùng Progman={host == progman}")
    say(f"desktop_host_alive(): {desktop_pin.desktop_host_alive()}")
    if host:
        say(f"Gốc client của host trên màn hình: {win32.map_window_points(host, 0, 0, 0)}")
    say("")

    pre = snapshot("TRƯỚC KHI GHIM (pha 1)", widget, hwnd)
    t0 = time.perf_counter()
    pin_ok = desktop_pin.pin(hwnd)
    pin_error = desktop_pin.last_error
    elapsed = (time.perf_counter() - t0) * 1000.0
    pump(app, 250)
    say(f"desktop_pin.pin({hx(hwnd)}) -> {pin_ok}  ({elapsed:.1f} ms)")
    say(f"desktop_pin.last_error       -> {pin_error}")
    say("")
    post = _verify_pinned("SAU KHI GHIM (pha 1)", widget, hwnd, host, "host desktop")

    result = {
        "pin_ok": pin_ok,
        "pin_error": pin_error,
        "pre": pre,
        "post": post,
        "host": host,
        "progman": progman,
    }
    if pre["rect"] and post["rect"]:
        say(f"  Rect giữ nguyên sau khi ghim?         : {post['rect'] == pre['rect']} (lệch="
            f"{(post['rect'][0] - pre['rect'][0], post['rect'][1] - pre['rect'][1])})")
    say("")

    if pin_ok:
        say("==> GHIM THẬT THÀNH CÔNG. Đo hiện tượng toạ độ Qt:")
        say("")
        result["move"] = _qt_move_test(app, widget, hwnd, (520, 340))
        result["resize"] = _qt_resize_test(app, widget, hwnd)
        result["shot"] = capture_screen(app, "pinned_desktop")
        say("")

    # Bỏ ghim (dù thành công hay không, để chắc chắn cửa sổ về top-level).
    if pin_ok or desktop_pin.is_pinned(hwnd):
        unpin_ok = desktop_pin.unpin(hwnd)
        pump(app, 250)
        say(f"desktop_pin.unpin({hx(hwnd)}) -> {unpin_ok}")
        say("")
        result["unpin_ok"] = unpin_ok
        result["post_unpin"] = snapshot("SAU KHI BỎ GHIM (pha 1)", widget, hwnd)
    else:
        say("(pin thất bại – không có gì để unpin)")
        say("")

    # Chụp màn hình trạng thái sau pha 1 (cửa sổ test vẫn hiện, top-level).
    result["shot_after"] = capture_screen(app, "phase1_after")
    say("")
    return result


# ---------------------------------------------------------------------------
# Script con tạo host xuyên tiến trình (cùng integrity) cho PHA 3
# ---------------------------------------------------------------------------

_CROSS_PROCESS_HOST_SCRIPT = r'''
import ctypes, time
from ctypes import wintypes

u = ctypes.WinDLL("user32", use_last_error=True)
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.GetModuleHandleW.restype = wintypes.HMODULE
u.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
u.CreateWindowExW.restype = wintypes.HWND
u.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
    wintypes.UINT, wintypes.UINT,
]
u.PeekMessageW.restype = wintypes.BOOL
u.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
u.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
u.IsWindow.argtypes = [wintypes.HWND]
u.IsWindow.restype = wintypes.BOOL

hinst = k.GetModuleHandleW(None)
w = u.CreateWindowExW(
    0, "STATIC", "QT Calendar - host xuyen tien trinh",
    0x00CF0000 | 0x10000000, 260, 130, 520, 380,
    None, None, hinst, None,
)
print("%X" % (w or 0), flush=True)
end = time.time() + 60
msg = wintypes.MSG()
while time.time() < end and u.IsWindow(w):
    while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))
    time.sleep(0.02)
'''


def phase3_cross_process(app: QApplication, widget: QWidget, hwnd: int) -> dict:
    """PHA 3: kiểm tra ``SetParent`` xuyên tiến trình khi hai bên cùng integrity.

    Mục đích: chứng minh ``SetParent`` **được phép** xuyên tiến trình; rào cản
    duy nhất khi ghim vào ``Progman`` là UIPI (khác integrity level), không
    phải giới hạn "không thể đổi parent sang cửa sổ tiến trình khác".
    """
    import subprocess

    say("#" * 78)
    say("# PHA 3 – SETPARENT XUYÊN TIẾN TRÌNH (host cùng integrity)")
    say("#" * 78)
    say("Host là cửa sổ của một tiến trình Python KHÁC (cùng Low IL trong môi")
    say("trường này). Nếu SetParent xuyên tiến trình thành công ⇒ rào chắn ở PHA 1")
    say("đúng là UIPI do lệch integrity, không phải hạn chế xuyên tiến trình.")
    say("")

    result: dict = {}
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", _CROSS_PROCESS_HOST_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        line = (proc.stdout.readline() if proc.stdout else "").strip()
        if not line:
            say("Không tạo được host xuyên tiến trình – bỏ qua PHA 3.")
            return result
        host = int(line, 16)
        say(f"Host xuyên tiến trình: {hx(host)} (class={win32.get_class_name(host)!r})")
        say(f"  visible={win32.is_window_visible(host)} "
            f"rect={rect_text(win32.get_window_rect(host))}")
        say("")

        # Đảm bảo cửa sổ test đang top-level + hiện trước khi ghim.
        widget.show()
        pump(app, 250)
        hwnd = win32.get_hwnd(widget)
        pre = snapshot("TRƯỚC KHI GHIM (host xuyên tiến trình)", widget, hwnd)

        original_find = desktop_pin.find_desktop_host
        original_locate = desktop_pin._locate_host
        try:
            desktop_pin.find_desktop_host = lambda: (host, "CrossProcessHost")  # type: ignore[assignment]
            desktop_pin._locate_host = lambda: (host, "CrossProcessHost")  # type: ignore[assignment]
            pin_ok = desktop_pin.pin(hwnd)
            pump(app, 250)
            say(f"desktop_pin.pin({hx(hwnd)}) -> {pin_ok}")
            say(f"desktop_pin.last_error       -> {desktop_pin.last_error}")
            say("")
            post = _verify_pinned(
                "SAU KHI GHIM (host xuyên tiến trình)", widget, hwnd, host,
                "host tiến trình khác",
            )
            result.update({"pin_ok": pin_ok, "pre": pre, "post": post, "host": host})
            if pre["rect"] and post["rect"]:
                say(f"  Rect giữ nguyên sau khi ghim?         : {post['rect'] == pre['rect']} "
                    f"(lệch={(post['rect'][0] - pre['rect'][0], post['rect'][1] - pre['rect'][1])})")
            say("")
            unpin_ok = desktop_pin.unpin(hwnd)
            pump(app, 250)
            say(f"desktop_pin.unpin({hx(hwnd)}) -> {unpin_ok}")
            post_unpin = snapshot("SAU KHI BỎ GHIM (host xuyên tiến trình)", widget, hwnd)
            result["unpin_ok"] = unpin_ok
            result["post_unpin"] = post_unpin
            say("KIỂM TRA BỎ GHIM:")
            say(f"  GetParent == 0?                     : {post_unpin['parent'] == 0}")
            say(f"  Còn bit WS_CHILD?                   : {bool(post_unpin['style'] & win32.WS_CHILD)}")
            say(f"  Rect khôi phục == rect ban đầu?     : {post_unpin['rect'] == pre['rect']}")
            say("")
        finally:
            desktop_pin.find_desktop_host = original_find  # type: ignore[assignment]
            desktop_pin._locate_host = original_locate  # type: ignore[assignment]
    except Exception:
        say("PHA 3 thất bại:")
        traceback.print_exc()
    finally:
        try:
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                say(f"Đã kết thúc tiến trình host xuyên tiến trình (exit={proc.returncode}).")
                say("")
        except Exception:
            pass
    return result


def _diagnose_pin_failure(error: int, integrity_label: str) -> None:
    """In chẩn đoán vì sao pin thất bại dựa trên mã lỗi Win32."""
    error = int(error or 0)
    say("CHẨN ĐOÁN VÌ SAO PIN THẤT BẠI:")
    say(f"  Mã lỗi Win32 (SetParent)      : {error}")
    if error == 5:  # ERROR_ACCESS_DENIED
        say("  → ERROR_ACCESS_DENIED: Windows UIPI chặn SetParent sang cửa sổ")
        say("    của tiến trình có integrity cao hơn.")
        say(f"  → Tiến trình probe đang chạy ở integrity: {integrity_label}")
        say("    Explorer/Progman chạy ở Medium; nếu probe chạy Low (sandbox của")
        say("    môi trường chạy lệnh) thì việc ghim bị chặn – KHÔNG phải lỗi code.")
        say("    Chạy cùng script từ terminal thường (Medium) sẽ ghim được.")
    elif error == 87:  # ERROR_INVALID_PARAMETER
        say("  → ERROR_INVALID_PARAMETER: handle/host không hợp lệ (Explorer đổi")
        say("    trạng thái?).")
    elif error:
        say(f"  → Lỗi Win32 {error} (xem System Error Codes).")
    else:
        say("  → Không có lỗi Win32 trực tiếp (có thể không tìm thấy host desktop).")
    say("")


def _qt_behavior_tests(app: QApplication, widget: QWidget, hwnd: int, host_hwnd: int) -> dict:
    """Đo ảnh hưởng của các thao tác Qt thường dùng lên trạng thái ghim."""
    result: dict = {}
    say("THỬ CÁC THAO TÁC Qt KHÁC KHI ĐANG GHIM (opacity/hide/show/đổi cờ):")

    # a) setWindowOpacity – app dùng menu độ trong suốt
    try:
        widget.setWindowOpacity(0.8)
        pump(app, 200)
        st = win32.get_window_long(hwnd, win32.GWL_STYLE)
        ex = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
        say(
            "  setWindowOpacity(0.8): "
            f"parent={hx(win32.get_parent(hwnd))} "
            f"WS_CHILD={bool(st & win32.WS_CHILD)} "
            f"exstyle={exstyle_text(ex)} "
            f"is_pinned={desktop_pin.is_pinned(hwnd)}"
        )
        widget.setWindowOpacity(1.0)
        pump(app, 150)
    except Exception:
        say("  setWindowOpacity: lỗi")
        traceback.print_exc()

    # b) hide()/show() – app ẩn/hiện widget từ tray
    try:
        widget.hide()
        pump(app, 200)
        st = win32.get_window_long(hwnd, win32.GWL_STYLE)
        say(
            "  hide(): "
            f"visible={win32.is_window_visible(hwnd)} "
            f"parent={hx(win32.get_parent(hwnd))} "
            f"WS_CHILD={bool(st & win32.WS_CHILD)} "
            f"is_pinned={desktop_pin.is_pinned(hwnd)}"
        )
        widget.show()
        pump(app, 250)
        st = win32.get_window_long(hwnd, win32.GWL_STYLE)
        say(
            "  show(): "
            f"visible={win32.is_window_visible(hwnd)} "
            f"parent={hx(win32.get_parent(hwnd))} "
            f"WS_CHILD={bool(st & win32.WS_CHILD)} "
            f"is_pinned={desktop_pin.is_pinned(hwnd)}"
        )
    except Exception:
        say("  hide/show: lỗi")
        traceback.print_exc()

    # c) đổi cờ cửa sổ (app có thể bật/tắt "luôn nổi trên cùng")
    try:
        before = win32.get_hwnd(widget)
        widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        pump(app, 300)
        after = win32.get_hwnd(widget)
        st = win32.get_window_long(after, win32.GWL_STYLE)
        say(
            "  setWindowFlag(WindowStaysOnTopHint, True): "
            f"HWND {hx(before)} → {hx(after)} (đổi={after != before})"
        )
        say(
            "    parent="
            f"{hx(win32.get_parent(after))} WS_CHILD={bool(st & win32.WS_CHILD)} "
            f"is_pinned={desktop_pin.is_pinned(after)}"
        )
        if after != before:
            say("    → Qt ĐÃ TẠO LẠI cửa sổ native (HWND mới): mọi cấu trúc ghim cũ")
            say("      gắn với HWND cũ; app phải đo lại HWND rồi pin() lại.")
        else:
            say("    → Cùng HWND; kiểm tra xem quan hệ con có còn không.")
            monitor_ok = desktop_pin.monitor()
            pump(app, 250)
            say(f"    monitor() sau đổi cờ -> {monitor_ok}; parent="
                f"{hx(win32.get_parent(after))}; is_pinned={desktop_pin.is_pinned(after)}")
            result["monitor_after_flag"] = monitor_ok
        # Bỏ cờ để dọn dẹp
        widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        pump(app, 300)
        result["hwnd_after_flag"] = win32.get_hwnd(widget)
        say(
            f"  bỏ cờ: HWND cuối = {hx(result['hwnd_after_flag'])} "
            f"(is_pinned={desktop_pin.is_pinned(result['hwnd_after_flag'])})"
        )
    except Exception:
        say("  đổi cờ cửa sổ: lỗi")
        traceback.print_exc()

    say("")
    return result


def phase2_diagnostic_host(app: QApplication, widget: QWidget, hwnd: int) -> dict:
    """Kiểm chứng đầy đủ giải thuật bằng host cùng tiến trình (chỉ để chẩn đoán)."""
    say("#" * 78)
    say("# PHA 2 – KIỂM CHỨNG GIẢI THUẬT VỚI HOST CÙNG TIẾN TRÌNH (chẩn đoán)")
    say("#" * 78)
    say("Host này KHÔNG phải desktop thật. Mục đích: nếu UIPI chặn SetParent sang")
    say("Progman, vẫn kiểm tra được các bước style/MapWindowPoints/Qt/monitor().")
    say("")

    host_widget = QWidget()
    host_widget.setWindowTitle("QTCalendar – host chẩn đoán (cùng tiến trình)")
    host_widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
    host_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    host_widget.setStyleSheet("background-color: #1F3A5F;")
    host_widget.resize(900, 620)
    host_widget.move(320, 150)
    host_widget.show()
    pump(app, 350)
    host_hwnd = win32.get_hwnd(host_widget)
    say(f"Host chẩn đoán: {hx(host_hwnd)} rect={rect_text(win32.get_window_rect(host_hwnd))}")
    say(f"  client origin (screen): {win32.map_window_points(host_hwnd, 0, 0, 0)}")
    say("")

    original_find = desktop_pin.find_desktop_host
    original_locate = desktop_pin._locate_host
    result: dict = {"host_hwnd": host_hwnd}
    widget.move(120, 120)  # vị trí ban đầu trước khi ghim (đã biết từ pha 1)
    pump(app, 150)

    try:
        desktop_pin.find_desktop_host = lambda: (host_hwnd, "DiagnosticHost")  # type: ignore[assignment]
        desktop_pin._locate_host = lambda: (host_hwnd, "DiagnosticHost")  # type: ignore[assignment]

        pre = snapshot("TRƯỚC KHI GHIM (host chẩn đoán)", widget, hwnd)
        pin_ok = desktop_pin.pin(hwnd)
        pump(app, 250)
        say(f"desktop_pin.pin({hx(hwnd)}) -> {pin_ok}")
        say(f"desktop_pin.last_error       -> {desktop_pin.last_error}")
        say("")
        post = _verify_pinned(
            "SAU KHI GHIM (host chẩn đoán)", widget, hwnd, host_hwnd, "host chẩn đoán"
        )
        result.update({"pin_ok": pin_ok, "pre": pre, "post": post})
        if pre["rect"] and post["rect"]:
            say(f"  Rect giữ nguyên sau khi ghim?         : {post['rect'] == pre['rect']} (lệch="
                f"{(post['rect'][0] - pre['rect'][0], post['rect'][1] - pre['rect'][1])})")
        say("")

        if pin_ok:
            # Qt.move: Qt vẫn tưởng cửa sổ là top-level nên gửi toạ độ màn hình;
            # Win32 hiểu là toạ độ client của host ⇒ lệch đúng bằng gốc client.
            host_client_origin = win32.map_window_points(host_hwnd, 0, 0, 0)
            say(f"Gốc client của host trên màn hình: {host_client_origin}")
            target = (520, 340)
            result["move"] = _qt_move_test(app, widget, hwnd, target)
            after = result["move"]["after"]
            if after:
                expected = (
                    host_client_origin[0] + target[0],
                    host_client_origin[1] + target[1],
                )
                say(f"  DỰ ĐOÁN nếu Qt dùng toạ độ màn hình: rect=({expected[0]}, {expected[1]})")
                say(f"  THỰC TẾ GetWindowRect              : ({after[0]}, {after[1]})")
                say(f"  Khớp dự đoán (lệch gốc host)?      : {(after[0], after[1]) == expected}")
                say("  → Qt.move() KHÔNG sai trên desktop thật (Progman có gốc client")
                say("    (0,0)), nhưng SAI nếu host có gốc khác (0,0). Vì vậy app phải")
                say("    dịch toạ độ bằng MapWindowPoints hoặc unpin→move→pin lại.")
                say("")
            result["resize"] = _qt_resize_test(app, widget, hwnd)
            result["shot"] = capture_screen(app, "diagnostic_pinned")
            say("")

            # Kiểm tra monitor(): mô phỏng mất ghim bằng cách gỡ parent.
            say("THỬ desktop_pin.monitor() KHI MẤT GHIM:")
            win32.set_parent(hwnd, 0)
            pump(app, 150)
            lost_parent = win32.get_parent(hwnd)
            say(f"  Sau khi gỡ parent thủ công: parent={hx(lost_parent)}")
            say(f"  is_pinned() = {desktop_pin.is_pinned(hwnd)}")
            monitor_ok = desktop_pin.monitor()
            pump(app, 250)
            say(f"  desktop_pin.monitor() -> {monitor_ok}")
            say(f"  parent sau monitor: {hx(win32.get_parent(hwnd))} (host={hx(host_hwnd)})")
            say(f"  đã ghim lại? {win32.get_parent(hwnd) == host_hwnd}")
            say("")
            result["monitor_ok"] = monitor_ok

            # Các thao tác Qt thường dùng (opacity/hide/show/đổi cờ).
            result["behaviors"] = _qt_behavior_tests(app, widget, hwnd, host_hwnd)
            original_hwnd = hwnd
            hwnd = win32.get_hwnd(widget)  # có thể đã bị Qt tạo lại khi đổi cờ
            say(f"HWND hiện tại sau các thao tác Qt: {hx(hwnd)} "
                f"(ban đầu {hx(original_hwnd)}, đổi={hwnd != original_hwnd})")
            if not desktop_pin.is_pinned(hwnd):
                repin_ok = desktop_pin.pin(hwnd)
                pump(app, 200)
                say(f"  chưa ghim sau đổi cờ → pin() lại bằng HWND mới -> {repin_ok}")
                result["repin_ok"] = repin_ok
            say("")

            unpin_ok = desktop_pin.unpin(hwnd)
            pump(app, 250)
            say(f"desktop_pin.unpin({hx(hwnd)}) -> {unpin_ok}")
            say("")
            result["unpin_ok"] = unpin_ok
            post_unpin = snapshot("SAU KHI BỎ GHIM (host chẩn đoán)", widget, hwnd)
            result["post_unpin"] = post_unpin
            say("KIỂM TRA BỎ GHIM:")
            say(f"  GetParent == 0 (top-level trở lại)? : {post_unpin['parent'] == 0}")
            say(f"  Còn bit WS_CHILD?                   : {bool(post_unpin['style'] & win32.WS_CHILD)}")
            say(f"  Có bit WS_POPUP?                    : {bool(post_unpin['style'] & win32.WS_POPUP)}")
            say(f"  IsWindowVisible?                    : {post_unpin['visible']}")
            say(f"  is_pinned() bây giờ                 : {desktop_pin.is_pinned(hwnd)}")
            say(f"  HWND trở lại EnumWindows?           : {hwnd in win32.enum_windows()}")
            if pre["rect"] and post_unpin["rect"] and hwnd == original_hwnd:
                say(f"  Rect khôi phục == rect ban đầu?     : {post_unpin['rect'] == pre['rect']}")
                say(f"    ban đầu : {rect_text(pre['rect'])}")
                say(f"    sau bỏ  : {rect_text(post_unpin['rect'])}")
            elif hwnd != original_hwnd:
                say("  (HWND đã đổi do đổi cờ nên không so rect với cửa sổ cũ)")
            say("")
    finally:
        # Luôn khôi phục hàm thật + dọn cửa sổ.
        try:
            desktop_pin.find_desktop_host = original_find  # type: ignore[assignment]
            desktop_pin._locate_host = original_locate  # type: ignore[assignment]
        except Exception:
            pass
        try:
            for tracked in list(getattr(desktop_pin, "_states", {}).keys()):
                try:
                    if win32.is_window(tracked):
                        desktop_pin.unpin(tracked)
                    else:
                        desktop_pin._states.pop(tracked, None)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            host_widget.close()
            host_widget.deleteLater()
            pump(app, 150)
        except Exception:
            pass
        say(f"Đã đóng host chẩn đoán. is_window(host)={win32.is_window(host_hwnd)}")
        say("")
    return result


# ---------------------------------------------------------------------------
# Chương trình chính
# ---------------------------------------------------------------------------


def run() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    say("=" * 78)
    say("QT Calendar – PROBE GHIM DESKTOP (SetParent → Progman)")
    say("=" * 78)
    say(f"Python        : {sys.version.split()[0]} ({sys.executable})")
    say(f"PySide6/Qt    : {qVersion()}")
    say(f"Hệ điều hành  : {sys.platform} | IS_WINDOWS={IS_WINDOWS}")
    say(f"TEMP          : {tempfile.gettempdir()}")
    if not IS_WINDOWS:
        say("Không phải Windows – không thể probe. Kết thúc.")
        return 2

    integrity_label, integrity_sid = process_integrity()
    say(f"Integrity level: {integrity_label} ({integrity_sid})")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    screen = app.primaryScreen()
    if screen is not None:
        geom = screen.geometry()
        dpr = screen.devicePixelRatio()
        say(
            f"Màn hình      : {screen.name()!r} geometry=({geom.x()}, {geom.y()}, "
            f"{geom.width()}, {geom.height()}) devicePixelRatio={dpr:.3f} "
            f"logicalDpi={screen.logicalDotsPerInch():.1f}"
        )
    say(f"Virtual screen : {win32.screen_rect()} (GetSystemMetrics)")
    progman = win32.find_window("Progman")
    say(f"Progman HWND   : {hx(progman)} (class={win32.get_class_name(progman)!r})")
    say("")

    # --- Cửa sổ test -------------------------------------------------------
    widget = QWidget()
    widget.setWindowTitle("QTCalendar – cửa sổ test ghim desktop")
    widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setStyleSheet("background-color: #C81E1E; border: 3px solid #FFD8D8;")
    widget.setWindowIcon(QIcon())
    widget.resize(320, 200)
    widget.move(120, 120)

    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 12, 16, 12)
    label = QLabel("QT Calendar\nCỬA SỔ TEST GHIM DESKTOP\n(không dùng Win+D)", widget)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        "color: #FFFFFF; background: transparent;"
        " font-size: 15px; font-weight: 600;"
    )
    layout.addWidget(label)
    widget.show()
    pump(app, 400)

    hwnd = win32.get_hwnd(widget)
    say("== CỬA SỔ TEST ĐÃ HIỆN ==")
    say(f"HWND    : {hx(hwnd)}")
    say(f"Qt pos  : ({widget.x()}, {widget.y()}) kích thước {widget.width()}x{widget.height()}")
    say("")

    phase1: dict = {}
    phase2: dict = {}
    try:
        phase1 = phase1_desktop(app, widget, hwnd)
        if not phase1.get("pin_ok"):
            _diagnose_pin_failure(phase1.get("pin_error", 0), integrity_label)
        phase2 = phase2_diagnostic_host(app, widget, hwnd)
        phase3 = phase3_cross_process(app, widget, hwnd)

        # --- Kết luận ------------------------------------------------------
        say("=" * 78)
        say("KẾT LUẬN PROBE")
        say("=" * 78)
        say(f"PHA 1 (desktop thật)  : pin={phase1.get('pin_ok')} "
            f"last_error={phase1.get('pin_error')} integrity={integrity_label}")
        if phase1.get("pin_ok"):
            post = phase1["post"]
            say(f"  parent = Progman? {post['parent'] == phase1['progman']} "
                f"| WS_CHILD={bool(post['style'] & win32.WS_CHILD)} "
                f"| visible={post['visible']} "
                f"| còn top-level={hwnd in win32.enum_windows()}")
            say("  ==> GHIM DESKTOP THẬT HOẠT ĐỘNG trên môi trường này.")
        else:
            say("  ==> KHÔNG ghim được trong môi trường chạy hiện tại (xem chẩn đoán).")
            if int(phase1.get("pin_error") or 0) == 5:
                say("      Nguyên nhân: UIPI + integrity level thấp (sandbox môi trường),")
                say("      không phải lỗi của desktop_pin. Chạy script ở terminal thường")
                say("      (Medium integrity) để có kết quả cuối.")
        p2 = phase2.get("post") or {}
        if phase2.get("pin_ok"):
            say(f"PHA 2 (host chẩn đoán): pin=True | parent==host={p2.get('parent') == phase2.get('host_hwnd')} "
                f"| WS_CHILD={bool((p2.get('style') or 0) & win32.WS_CHILD)} "
                f"| monitor()={phase2.get('monitor_ok')} "
                f"| unpin={phase2.get('unpin_ok')}")
            say("  ==> Giải thuật SetParent/style/MapWindowPoints/unpin chạy ĐÚNG;")
            say("      chỉ bị chặn bởi rào integrity khi host là Progman (Medium).")
        else:
            say("PHA 2 (host chẩn đoán): pin=False – cần xem chi tiết phía trên.")
        p3 = phase3.get("post") or {}
        if phase3.get("pin_ok"):
            say(f"PHA 3 (xuyên tiến trình): pin=True | "
                f"parent==host={p3.get('parent') == phase3.get('host')} "
                f"| WS_CHILD={bool((p3.get('style') or 0) & win32.WS_CHILD)} "
                f"| unpin={phase3.get('unpin_ok')}")
            say("  ==> SetParent XUYÊN TIẾN TRÌNH thành công khi cùng integrity.")
            say("      Khẳng định: rào chắn ở PHA 1 chỉ là UIPI do lệch integrity;")
            say("      khi app chạy bình thường (Medium IL) như Explorer, pin sẽ chạy.")
        elif phase3:
            say("PHA 3 (xuyên tiến trình): pin=False – cần xem chi tiết phía trên.")
        say("")
        say("GHI CHÚ: probe KHÔNG gửi Win+D (theo yêu cầu an toàn). Việc sống sót qua")
        say("Show Desktop được suy ra từ cấu trúc: cửa sổ là con của host desktop,")
        say("không còn là top-level ⇒ Show Desktop không duyệt tới nó.")
        say("=" * 78)
        return 0
    finally:
        # --- Dọn dẹp: LUÔN bỏ ghim + đóng đúng cửa sổ test -----------------
        say("")
        say("== DỌN DẸP ==")
        try:
            current_hwnd = win32.get_hwnd(widget)
        except Exception:
            current_hwnd = hwnd
        for candidate in {current_hwnd, hwnd}:
            try:
                if candidate and win32.is_window(candidate) and desktop_pin.is_pinned(candidate):
                    ok = desktop_pin.unpin(candidate)
                    say(f"unpin khẩn cấp {hx(candidate)} -> {ok}")
                    pump(app, 150)
            except Exception:
                say("unpin khẩn cấp: lỗi")
                traceback.print_exc()
        try:
            if current_hwnd and win32.is_window(current_hwnd) and win32.get_parent(current_hwnd) != 0:
                old_parent = win32.get_parent(current_hwnd)
                style = win32.get_window_long(current_hwnd, win32.GWL_STYLE)
                win32.set_parent(current_hwnd, 0)
                if style & win32.WS_CHILD:
                    # fallback: trả style top-level tối thiểu nếu chưa có state
                    win32.set_window_long(
                        current_hwnd,
                        win32.GWL_STYLE,
                        (style | win32.WS_POPUP) & ~win32.WS_CHILD,
                    )
                say(f"gỡ parent khẩn cấp (parent cũ {hx(old_parent)})")
                pump(app, 100)
        except Exception:
            say("gỡ parent khẩn cấp: lỗi")
        try:
            widget.close()
            widget.deleteLater()
            pump(app, 150)
            app.processEvents()
            say(f"Cửa sổ test đã đóng. is_window(hwnd) = {win32.is_window(hwnd)}")
        except Exception:
            say("Đóng cửa sổ test: lỗi")
            traceback.print_exc()
        try:
            app.quit()
        except Exception:
            pass


def main() -> int:
    try:
        return run()
    except Exception:
        say("")
        say("PROBE THẤT BẠI – traceback:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
