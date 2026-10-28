"""Render ảnh minh hoạ độ trong suốt của nền và màu nền tuỳ chọn.

Mục đích: chứng minh hai yêu cầu của người dùng bằng ảnh thật:

1. **Chỉ nền trong đi, chữ giữ nguyên độ đục** – ảnh được dựng trên một nền
   "hình nền desktop" giả lập để thấy rõ phần giấy trong suốt, còn chữ, chip
   giờ hoàng đạo, badge… vẫn đặc ruột.
2. **Đổi màu nền** – cùng một ngày, cùng bộ chữ, nhưng nền giấy khác màu.

Chạy: ``python -X utf8 scripts/preview_paper.py``
Ảnh xuất ra ``preview/opacity_demo.png`` và ``preview/bg_color_demo.png``.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtcalendar.core import calendar_service  # noqa: E402
from qtcalendar.core.config import Settings  # noqa: E402
from qtcalendar.core.quotes import quote_of_day  # noqa: E402
from qtcalendar.core.theme import BACKGROUND_PRESETS  # noqa: E402
from qtcalendar.ui.widget_window import CalendarWidget  # noqa: E402

W, H = 344, 468
OUT = ROOT / "preview"


def _desktop_background(width: int, height: int) -> QImage:
    """Nền giả lập: gradient xanh đêm + vài khối sáng để thấy độ trong suốt."""
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(img)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor("#1E3A5F"))
    grad.setColorAt(0.5, QColor("#2F6F8F"))
    grad.setColorAt(1.0, QColor("#8A4C6B"))
    painter.fillRect(0, 0, width, height, grad)
    painter.setOpacity(0.35)
    painter.setBrush(QColor("#FFFFFF"))
    for i in range(14):
        painter.drawEllipse(40 + i * 90, 80 + (i % 5) * 120, 160, 160)
    painter.setOpacity(1.0)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 13)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        QRect(18, 16, width - 36, 60),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        "Ảnh chỉ để kiểm tra độ trong suốt\n(nền giả lập giống hình nền desktop)",
    )
    painter.end()
    return img


def _render_widget(opacity: float, bg_color: str = "", theme: str = "giay_do") -> QImage:
    """Dựng widget với cấu hình cho trước và trả về ảnh RGBA (alpha giữ nguyên)."""
    settings = Settings()
    settings.width, settings.height = W, H
    settings.opacity = opacity
    settings.bg_color = bg_color
    settings.theme = theme
    widget = CalendarWidget(settings)
    widget.resize(W, H)
    widget.show()
    QApplication.processEvents()
    day = date(2026, 10, 28)
    widget._selected = day
    widget._refresh_content()
    widget._apply_content_scale()
    QApplication.processEvents()
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    widget.hide()
    widget.deleteLater()
    QApplication.processEvents()
    return image


def _compose(canvas: QImage, image: QImage, x: int, y: int, label: str) -> None:
    """Dán widget lên nền và ghi nhãn phía dưới."""
    painter = QPainter(canvas)
    painter.drawImage(x, y, image)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 11)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        QRect(x, y + image.height() + 10, image.width(), 40),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        label,
    )
    painter.end()


def make_opacity_demo() -> Path:
    pads, gap = 26, 26
    canvas_w = pads * 2 + W * 3 + gap * 2
    canvas_h = pads * 2 + H + 56
    canvas = _desktop_background(canvas_w, canvas_h)
    for index, (opacity, label) in enumerate(
        (
            (1.0, "Độ mờ 100 % — nền đặc, chữ đặc"),
            (0.6, "Độ mờ 60 % — chỉ NỀN trong, chữ vẫn đặc"),
            (0.3, "Độ mờ 30 % — nền rất trong, chữ vẫn đặc"),
        )
    ):
        image = _render_widget(opacity)
        x = pads + index * (W + gap)
        _compose(canvas, image, x, pads, label)
    path = OUT / "opacity_demo.png"
    canvas.save(str(path), "PNG")
    return path


def make_bg_demo() -> Path:
    picks = [
        ("", "Theo giao diện (Giấy đỏ)", "giay_do"),
        (BACKGROUND_PRESETS[3][1], f"Nền {BACKGROUND_PRESETS[3][0]} ({BACKGROUND_PRESETS[3][1]})", "giay_do"),
        ("#141A22", "Nền tuỳ chọn tối #141A22", "giay_do"),
    ]
    pads, gap = 26, 26
    canvas_w = pads * 2 + W * len(picks) + gap * (len(picks) - 1)
    canvas_h = pads * 2 + H + 56
    canvas = _desktop_background(canvas_w, canvas_h)
    for index, (bg, label, theme) in enumerate(picks):
        image = _render_widget(1.0, bg, theme)
        _compose(canvas, image, pads + index * (W + gap), pads, label)
    path = OUT / "bg_color_demo.png"
    canvas.save(str(path), "PNG")
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    _app = QApplication.instance() or QApplication(sys.argv[:1])
    for path in (make_opacity_demo(), make_bg_demo()):
        print(f"đã ghi: {path} ({path.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
