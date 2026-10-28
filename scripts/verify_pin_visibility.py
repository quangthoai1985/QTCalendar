"""Kiểm chứng tự động: widget Ở CHẾ ĐỘ GHIM phải hiện rõ (không đen/vô hình).

Đây là bài kiểm chứng hồi quy cho lỗi người dùng báo:
"ghim sát Desktop thì lịch bị ẩn mất nhưng vẫn click được menu".

Không ghim vào Progman (có thể bị UIPI chặn trong môi trường sandbox) mà dùng
một cửa sổ host cùng tiến trình: cơ chế vẽ của cửa sổ con GIỐNG HỆT khi ghim
thật. Script đo tỉ lệ điểm ảnh màu giấy trên màn hình trong vùng host.

Chạy:  python -X utf8 scripts\\verify_pin_visibility.py
Exit code 0 = widget hiện rõ; 1 = vẫn bị ẩn (lỗi).
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from qtcalendar.core.config import Settings  # noqa: E402
from qtcalendar.platform import desktop_pin, win32  # noqa: E402
from qtcalendar.ui import widget_window as ww  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class _Host(QWidget):
    """Cửa sổ cha trắng đục (đóng vai "desktop") để đo điểm ảnh."""

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        painter.end()


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _sample_pixels(hwnd: int, step: int = 2) -> dict[str, float]:
    """Đếm tỉ lệ điểm ảnh "giấy" / "chữ đậm" / "trắng" trong vùng cửa sổ."""
    rect = win32.get_window_rect(hwnd)
    if not rect:
        return {}
    x1, y1, x2, y2 = rect
    width, height = x2 - x1, y2 - y1
    if width <= 0 or height <= 0:
        return {}

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    bitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    gdi32.SelectObject(hdc_mem, bitmap)
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x1, y1, 0x00CC0020)

    header = _BitmapInfoHeader()
    header.biSize = ctypes.sizeof(_BitmapInfoHeader)
    header.biWidth = width
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    buffer = ctypes.create_string_buffer(width * height * 4)
    lines = gdi32.GetDIBits(
        hdc_mem, bitmap, 0, height, buffer, ctypes.byref(header), 0
    )

    counts = {"giay": 0, "chu_dam": 0, "trang": 0, "den": 0, "tong": 0}
    if lines:
        data = buffer.raw
        for index in range(0, len(data), 4 * step):
            b, g, r = data[index], data[index + 1], data[index + 2]
            counts["tong"] += 1
            if r > 250 and g > 250 and b > 250:
                counts["trang"] += 1
            elif r > 232 and g > 218 and b > 190:
                counts["giay"] += 1
            elif r < 90 and g < 90 and b < 90:
                counts["chu_dam"] += 1
            elif r < 40 and g < 40 and b < 40:
                counts["den"] += 1

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)

    total = max(1, counts["tong"])
    return {k: round(v / total, 3) for k, v in counts.items() if k != "tong"}


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])

    host = _Host()
    host.resize(420, 560)
    host.move(60, 480)
    host.setWindowFlags(
        Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    )
    host.show()
    QApplication.processEvents()
    time.sleep(0.3)

    settings = Settings()
    settings.opacity = 0.65
    settings.placement = "desktop"
    settings.width, settings.height = 344, 468
    widget = ww.CalendarWidget(settings)
    widget.resize(344, 468)
    widget.move(80, 500)
    widget.show()
    QApplication.processEvents()

    host_hwnd = int(host.winId())
    desktop_pin.find_desktop_host = lambda: (host_hwnd, "HostThuNghiem")
    desktop_pin.is_pinned = lambda hwnd: bool(win32.get_parent(hwnd))
    desktop_pin._states.clear()

    widget._apply_placement()
    widget.repaint()
    QApplication.processEvents()
    time.sleep(0.5)
    QApplication.processEvents()

    widget_hwnd = int(widget.winId())
    stats = _sample_pixels(host_hwnd)
    exstyle = win32.get_window_long(widget_hwnd, win32.GWL_EXSTYLE)
    print(f"parent={win32.get_parent(widget_hwnd):#x} pinned={widget._pinned} "
          f"pin_look={widget._pin_look}")
    print(f"rect={win32.get_window_rect(widget_hwnd)} "
          f"layered={bool(exstyle & win32.WS_EX_LAYERED)}")
    print(f"điểm ảnh trong vùng host: {stats}")

    visible = stats.get("giay", 0) + stats.get("chu_dam", 0) >= 0.10

    settings.placement = "floating"
    widget.apply_settings()
    QApplication.processEvents()
    time.sleep(0.2)
    widget.close()
    host.close()
    QApplication.processEvents()

    if visible:
        print("\nKẾT LUẬN: LỊCH HIỆN RÕ khi ở chế độ ghim ✔")
        return 0
    print("\nKẾT LUẬN: KHÔNG thấy lịch khi ghim ✘ (lỗi vẫn còn)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
