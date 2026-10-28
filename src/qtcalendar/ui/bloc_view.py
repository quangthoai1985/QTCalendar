"""Lịch ngày – mặt trước "tờ lịch bloc" truyền thống Việt Nam (Bố cục 3 cột An Hảo).

Thiết kế kiến trúc (từ trên xuống):
====================================
1. Đỉnh lịch (_TopArtBanner):
   - Hoa văn nghệ thuật vector mây cuộn sóng lượn Á Đông truyền thống.
   - Câu châm ngôn cuộc sống / triết lý thanh nhã ở tâm điểm.
   - Chiều cao vừa vặn (≈ 8-10% chiều cao), không chiếm diện tích như ảnh chụp lớn.

2. Thân giữa (Dương lịch & Danh ngôn):
   - Số ngày Dương lịch SIÊU LỚN ở tâm điểm (cực đại hóa không gian).
   - Câu danh ngôn / tục ngữ chiêm nghiệm sống ngay dưới số ngày dương.
   - Clickable để đổi câu khác.

3. Chân lịch 3 CỘT KINH ĐIỂN (An Hảo / Lịch bloc đại truyền thống):
   - Cột Trái (Dương lịch & Hoàng đạo):
     * Năm + Tháng tiếng Anh (2026 · OCTOBER)
     * Tháng tiếng Việt (THÁNG MƯỜI)
     * Trực / Ngày Hoàng Đạo
     * Giờ Hoàng Đạo (danh sách giờ chi tiết)
     * Tuần & Ngày trong năm (Tuần 44 · Ngày 301/365)
   - Cột Giữa (Thứ & Âm lịch):
     * Thứ tiếng Việt in hoa đậm (THỨ TƯ)
     * Thứ tiếng Anh (WEDNESDAY)
     * SỐ NGÀY ÂM LỊCH CỠ LỚN SIÊU NỔI BẬT (ví dụ 19, 20)
   - Cột Phải (Âm lịch & Can Chi):
     * Tháng âm lịch kèm trạng thái Đủ/Thiếu (THÁNG CHÍN (Đ))
     * 4 dòng Can Chi rõ nét: Tháng, Ngày, Giờ Tý, Năm
     * Tiết khí (Tiết Sương Giáng)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ..core.canchi_constants import LUNAR_MONTH_NAMES, WEEKDAY_UPPER
from ..core.theme import Theme, alpha_of, get_theme
from ..core.types import DayInfo, Quote
from .styles import build_stylesheet, px, qcolor

__all__ = ["BlocView"]

_DESIGN_W = 344
_DESIGN_H = 468

_TOPIC_CREDIT = {
    "ca-dao": "Ca dao",
    "tuc-ngu": "Tục ngữ",
    "danh-ngon": "Danh ngôn",
}

_WEIGHT_NORMAL = QFont.Weight.Normal
_WEIGHT_MEDIUM = QFont.Weight.Medium
_WEIGHT_DEMI = QFont.Weight.DemiBold
_WEIGHT_BOLD = QFont.Weight.Bold
_WEIGHT_BLACK = QFont.Weight.Black


def _resolve_family(name: str, fallback: str) -> str:
    families = set(QFontDatabase.families())
    if name in families:
        return name
    base = name.rsplit(" ", 1)[0] if " " in name else ""
    if base and base in families:
        return base
    if fallback in families:
        return fallback
    return QFontDatabase.families()[0] if QFontDatabase.families() else "Segoe UI"


def _mix(color_a: QColor, color_b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(round(color_a.red() * (1 - t) + color_b.red() * t)),
        int(round(color_a.green() * (1 - t) + color_b.green() * t)),
        int(round(color_a.blue() * (1 - t) + color_b.blue() * t)),
        int(round(color_a.alpha() * (1 - t) + color_b.alpha() * t)),
    )


def _with_alpha(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(max(0.0, min(1.0, alpha)))
    return out


def _solid(color: QColor) -> QColor:
    out = QColor(color)
    out.setAlpha(255)
    return out


def _make_day_font(family: str, pixel_size: int) -> QFont:
    font = QFont(family)
    font.setPixelSize(max(6, int(pixel_size)))
    font.setWeight(_WEIGHT_BLACK)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setLetterSpacing(
        QFont.SpacingType.AbsoluteSpacing, -max(0.4, pixel_size * 0.012)
    )
    return font


def _wrap_elided(text: str, metrics: QFontMetricsF, width: float, max_lines: int) -> list[str]:
    words = text.split()
    if not words or max_lines <= 0 or width <= 1:
        return []
    lines: list[str] = []
    current = ""
    index = 0
    while index < len(words):
        word = words[index]
        candidate = f"{current} {word}" if current else word
        if metrics.horizontalAdvance(candidate) <= width or not current:
            current = candidate
            index += 1
            continue
        lines.append(current)
        current = ""
        if len(lines) >= max_lines:
            rest = " ".join(words[index:])
            lines[-1] = metrics.elidedText(
                f"{lines[-1]} {rest}", Qt.TextElideMode.ElideRight, int(width)
            )
            return lines
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


# ---------------------------------------------------------------------------
# Widget con
# ---------------------------------------------------------------------------

class _ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _DayNumber(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SolarDayLabel")
        self.setText("")
        self._family = get_theme(None).font_display
        self._pixel_size = 120
        self._ink = qcolor(get_theme(None).ink)

    def configure(self, family: str, pixel_size: int, ink: QColor) -> None:
        self._family = family
        self._pixel_size = max(8, int(pixel_size))
        self._ink = QColor(ink)
        self.update()

    def font_for_paint(self) -> QFont:
        return _make_day_font(self._family, self._pixel_size)

    def paintEvent(self, event) -> None:
        text = self.text()
        if not text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = self.font_for_paint()
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        tight = metrics.tightBoundingRect(text)
        if tight.width() <= 0 or tight.height() <= 0:
            return
        x = (self.width() - tight.width()) / 2.0 - tight.x()
        y = self.height() / 2.0 - (tight.y() + tight.height() / 2.0)
        ghost = _with_alpha(self._ink, 0.10)
        painter.setPen(ghost)
        bleed = max(0.8, self._pixel_size * 0.008)
        painter.drawText(QPointF(x + bleed, y + bleed), text)
        painter.setPen(self._ink)
        painter.drawText(QPointF(x, y), text)


class _TopArtBanner(QWidget):
    """Dải hoa văn nghệ thuật truyền thống ở đỉnh lịch (thay cho ảnh chụp lớn)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopArtBanner")
        self._motto = "Gia đình hạnh phúc là nền tảng của xã hội thịnh vượng"
        self._accent = QColor("#A83232")
        self._accent_2 = QColor("#C9975B")
        self._line = QColor("#E2D7C5")
        self._ink_soft = QColor("#6E645A")
        self._font = QFont("Georgia", 10)
        self._font.setItalic(True)

    def configure(
        self,
        motto: str,
        *,
        accent: QColor,
        accent_2: QColor,
        line: QColor,
        ink_soft: QColor,
        font: QFont,
    ) -> None:
        if motto:
            self._motto = motto
        self._accent = QColor(accent)
        self._accent_2 = QColor(accent_2)
        self._line = QColor(line)
        self._ink_soft = QColor(ink_soft)
        self._font = QFont(font)
        self.update()

    def paintEvent(self, event) -> None:
        w = float(self.width())
        h = float(self.height())
        if w < 20 or h < 10:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Đường chỉ chân dải hoa văn
        pen_line = QPen(_with_alpha(self._accent_2, 0.70), 1.0)
        painter.setPen(pen_line)
        painter.drawLine(QPointF(12.0, h - 2.0), QPointF(w - 12.0, h - 2.0))

        # Hoa văn mây cuộn sóng lượn Á Đông hai bên
        def draw_swirl(cx: float, cy: float, s: float, flip: bool = False) -> None:
            painter.save()
            painter.translate(cx, cy)
            if flip:
                painter.scale(-s, s)
            else:
                painter.scale(s, s)
            p_pen = QPen(self._accent_2, 1.25)
            painter.setPen(p_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            path = QPainterPath()
            path.moveTo(0, 0)
            path.cubicTo(8, -12, 20, -12, 28, -4)
            path.cubicTo(36, 4, 32, 16, 22, 18)
            path.cubicTo(12, 20, 8, 10, 16, 4)

            path.moveTo(28, -4)
            path.cubicTo(40, -15, 60, -12, 68, 0)
            path.cubicTo(74, 10, 68, 20, 56, 21)

            path.moveTo(68, 0)
            path.cubicTo(80, -6, 95, -4, 108, 6)

            painter.drawPath(path)
            painter.restore()

        swirl_scale = max(0.30, min(0.55, h / 80.0))
        draw_swirl(10.0, h * 0.48, swirl_scale, False)
        draw_swirl(w - 10.0, h * 0.48, swirl_scale, True)

        # Châm ngôn cuộc sống ở giữa
        if w > 140:
            painter.setFont(self._font)
            painter.setPen(self._ink_soft)
            text_rect = QRectF(46.0, 2.0, w - 92.0, h - 6.0)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._motto,
            )
        painter.end()


class _LunarPill(QWidget):
    """Số ngày âm lịch cỡ lớn siêu nổi bật ở trung tâm Cột 2."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Col2LunarPill")
        self._text = ""
        self._font = QFont(get_theme(None).font_display)
        self._ink = QColor("#1E7E34")
        self._line_color = qcolor(get_theme(None).line)
        self._ornament_color = qcolor(get_theme(None).accent_2)

    def configure(
        self,
        text: str,
        font: QFont,
        *,
        ink: QColor,
        line_color: QColor | None = None,
        ornament_color: QColor | None = None,
    ) -> None:
        self._text = text
        self._font = QFont(font)
        self._ink = QColor(ink)
        if line_color is not None:
            self._line_color = QColor(line_color)
        if ornament_color is not None:
            self._ornament_color = QColor(ornament_color)
        self.update()

    def text(self) -> str:
        return self._text

    def font_for_paint(self) -> QFont:
        return QFont(self._font)

    def paintEvent(self, event) -> None:
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        font = self._font
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        tight = metrics.tightBoundingRect(self._text)
        if tight.width() <= 0 or tight.height() <= 0:
            return

        x = (w - tight.width()) / 2.0 - tight.x()
        y = h / 2.0 - (tight.y() + tight.height() / 2.0)

        # Mực thấm nhẹ
        ghost = _with_alpha(self._ink, 0.12)
        painter.setPen(ghost)
        painter.drawText(QPointF(x + 1.0, y + 1.0), self._text)

        # Vẽ số ngày âm chính
        painter.setPen(self._ink)
        painter.drawText(QPointF(x, y), self._text)

        # Họa tiết đối xứng hai bên nếu còn chỗ
        text_left = (w - tight.width()) / 2.0
        text_right = text_left + tight.width()
        margin = max(4.0, w * 0.04)
        gap = 8.0
        ornament_size = 4.0
        cy = h / 2.0

        if text_left - margin > gap + ornament_size + 10.0:
            pen = QPen(self._line_color, 1.0)
            painter.setPen(pen)
            painter.drawLine(QPointF(margin, cy), QPointF(text_left - gap - ornament_size - 2.0, cy))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._ornament_color)
            p_left = QPainterPath()
            p_left.moveTo(text_left - gap - ornament_size / 2.0, cy - ornament_size / 2.0)
            p_left.lineTo(text_left - gap, cy)
            p_left.lineTo(text_left - gap - ornament_size / 2.0, cy + ornament_size / 2.0)
            p_left.lineTo(text_left - gap - ornament_size, cy)
            p_left.closeSubpath()
            painter.drawPath(p_left)

            painter.setPen(pen)
            painter.drawLine(QPointF(text_right + gap + ornament_size + 2.0, cy), QPointF(w - margin, cy))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._ornament_color)
            p_right = QPainterPath()
            p_right.moveTo(text_right + gap + ornament_size / 2.0, cy - ornament_size / 2.0)
            p_right.lineTo(text_right + gap + ornament_size, cy)
            p_right.lineTo(text_right + gap + ornament_size / 2.0, cy + ornament_size / 2.0)
            p_right.lineTo(text_right + gap, cy)
            p_right.closeSubpath()
            painter.drawPath(p_right)

        painter.end()


class _DividerOrnament(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DividerOrnament")
        self._color = qcolor(get_theme(None).accent_2)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def sizeHint(self) -> QSize:
        side = max(4, int(round(self.height() or 8)))
        return QSize(side, side)

    def paintEvent(self, event) -> None:
        side = min(self.width(), self.height())
        if side <= 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = side / 2.0
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.lineTo(cx + r, cy)
        path.lineTo(cx, cy + r)
        path.lineTo(cx - r, cy)
        path.closeSubpath()
        painter.drawPath(path)


class _DividerRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DividerRow")
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self.left = QFrame(self)
        self.left.setObjectName("Divider")
        self.left.setFixedHeight(1)
        self.ornament = _DividerOrnament(self)
        self.right = QFrame(self)
        self.right.setObjectName("Divider")
        self.right.setFixedHeight(1)
        box.addWidget(self.left, 1)
        box.addWidget(self.ornament, 0, Qt.AlignmentFlag.AlignVCenter)
        box.addWidget(self.right, 1)
        self._spacing = 8

    def configure(self, spacing: int, ornament_size: int, color: QColor) -> None:
        spacing = max(2, int(spacing))
        if spacing != self._spacing:
            self.layout().setSpacing(spacing)
            self._spacing = spacing
        self.ornament.setFixedSize(ornament_size, ornament_size)
        self.ornament.set_color(color)


# ---------------------------------------------------------------------------
# BlocView chính
# ---------------------------------------------------------------------------

class BlocView(QWidget):
    """Mặt trước lịch bloc truyền thống 3 cột Việt Nam."""

    quote_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BlocRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._theme: Theme = get_theme(None)
        self._scale: float = 1.0
        self._eff: float = 1.0
        self._info: DayInfo | None = None
        self._quote: Quote | None = None
        self._show_auspicious: bool = True
        self._show_tiet_khi: bool = True
        self._quote_visible: bool = False
        self._credit_visible: bool = False
        self._qss_scale: float = 0.0

        # Tọa độ phân cách cột chân lịch (vẽ trong paintEvent)
        self._col_sep_1_x = 0.0
        self._col_sep_2_x = 0.0
        self._footer_top_y = 0.0
        self._footer_bottom_y = 0.0

        # ---- font gia đình ----
        self._ui_family = _resolve_family(self._theme.font_ui, "Tahoma")
        self._display_family = _resolve_family(self._theme.font_display, self._ui_family)
        self._quote_family = _resolve_family(self._theme.font_quote, "Times New Roman")

        # ==================== CÁC THÀNH PHẦN GIAO DIỆN ====================
        # 1. Đỉnh lịch: Hoa văn nghệ thuật + Châm ngôn
        self._top_banner = _TopArtBanner(self)

        # 2. Thân giữa: Số ngày Dương siêu lớn + Danh ngôn
        self._day = _DayNumber(self)
        self._quote_label = _ClickableLabel(self)
        self._quote_label.setObjectName("QuoteLabel")
        self._quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quote_label.setToolTip("Bấm để đổi câu ca dao khác")
        self._quote_label.clicked.connect(self.quote_clicked)

        self._credit = QLabel("", self)
        self._credit.setObjectName("CreditLabel")
        self._credit.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 3. Phân cách chân lịch
        self._div_footer = _DividerRow(self)

        # 4. Chân lịch - Cột 1 (Dương lịch & Hoàng đạo)
        self._col1_month_en = QLabel("", self)
        self._col1_month_en.setObjectName("Col1MonthEn")
        self._col1_month_en.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col1_month_vn = QLabel("", self)
        self._col1_month_vn.setObjectName("Col1MonthVn")
        self._col1_month_vn.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col1_zodiac = QLabel("", self)
        self._col1_zodiac.setObjectName("Col1Zodiac")
        self._col1_zodiac.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col1_hours_title = QLabel("Giờ Hoàng Đạo:", self)
        self._col1_hours_title.setObjectName("Col1HoursTitle")
        self._col1_hours_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col1_hours = QLabel("", self)
        self._col1_hours.setObjectName("Col1Hours")
        self._col1_hours.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col1_footer = QLabel("", self)
        self._col1_footer.setObjectName("Col1Footer")
        self._col1_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 5. Chân lịch - Cột 2 (Thứ & Âm lịch)
        self._col2_weekday = QLabel("", self)
        self._col2_weekday.setObjectName("Col2Weekday")
        self._col2_weekday.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col2_weekday_en = QLabel("", self)
        self._col2_weekday_en.setObjectName("Col2WeekdayEn")
        self._col2_weekday_en.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lunar_pill = _LunarPill(self)

        # 6. Chân lịch - Cột 3 (Âm lịch & Can Chi)
        self._col3_lunar_month = QLabel("", self)
        self._col3_lunar_month.setObjectName("Col3LunarMonth")
        self._col3_lunar_month.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._col3_canchi_month = QLabel("", self)
        self._col3_canchi_month.setObjectName("Col3CanChi")
        self._col3_canchi_month.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._col3_canchi_day = QLabel("", self)
        self._col3_canchi_day.setObjectName("Col3CanChi")
        self._col3_canchi_day.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._col3_canchi_hour = QLabel("", self)
        self._col3_canchi_hour.setObjectName("Col3CanChi")
        self._col3_canchi_hour.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._col3_canchi_year = QLabel("", self)
        self._col3_canchi_year.setObjectName("Col3CanChi")
        self._col3_canchi_year.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._col3_tiet_khi = QLabel("", self)
        self._col3_tiet_khi.setObjectName("Col3TietKhi")
        self._col3_tiet_khi.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Bí danh tương thích ngược
        self._weekday = self._col2_weekday
        self._month = self._col1_month_vn
        self._lunar_month = self._col3_lunar_month
        self._canchi = self._col3_canchi_day
        self._badge_tiet = self._col3_tiet_khi
        self._hours_caption = self._col1_hours_title
        self._div1 = self._div_footer
        self._div2 = self._div_footer

        self._all_widgets = (
            self._top_banner,
            self._day,
            self._quote_label,
            self._credit,
            self._div_footer,
            self._col1_month_en,
            self._col1_month_vn,
            self._col1_zodiac,
            self._col1_hours_title,
            self._col1_hours,
            self._col1_footer,
            self._col2_weekday,
            self._col2_weekday_en,
            self._lunar_pill,
            self._col3_lunar_month,
            self._col3_canchi_month,
            self._col3_canchi_day,
            self._col3_canchi_hour,
            self._col3_canchi_year,
            self._col3_tiet_khi,
        )
        for w in self._all_widgets:
            w.hide()

        self._apply_fonts()
        self._apply_theme_colors()

    # ------------------------------------------------------------------
    # API công khai
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(px(_DESIGN_W, self._scale), px(_DESIGN_H, self._scale))

    def minimumSizeHint(self) -> QSize:
        return QSize(px(236, 1.0), px(300, 1.0))

    def apply_theme(self, theme: Theme, scale: float = 1.0) -> None:
        self._theme = theme if theme is not None else get_theme(None)
        try:
            self._scale = float(scale)
        except (TypeError, ValueError):
            self._scale = 1.0
        self._scale = max(0.5, min(3.0, self._scale))
        self.setStyleSheet(build_stylesheet(self._theme, self._scale))
        self._qss_scale = self._scale
        self._apply_theme_colors()
        self.refresh()

    def set_day(self, info: DayInfo) -> None:
        self._info = info
        self._sync_content()
        self.refresh()

    def set_quote(self, quote: Quote | None) -> None:
        self._quote = quote
        self._sync_quote()
        self.refresh()

    def set_show_auspicious(self, flag: bool) -> None:
        self._show_auspicious = bool(flag)
        self.refresh()

    def set_show_tiet_khi(self, flag: bool) -> None:
        self._show_tiet_khi = bool(flag)
        self.refresh()

    def refresh(self) -> None:
        self._bg_layer = None
        self._relayout()
        self.update()

    @property
    def current_day(self) -> DayInfo | None:
        return self._info

    def set_embedded(self, flag: bool | None) -> None:
        self._embedded_override = flag
        self._bg_layer = None
        self.update()

    # ------------------------------------------------------------------
    # Nội bộ: màu / font
    # ------------------------------------------------------------------

    def _apply_theme_colors(self) -> None:
        t = self._theme
        e = self._eff
        ink_color = qcolor(t.ink)
        if self._info and (self._info.is_sunday or self._info.holiday):
            ink_color = qcolor(t.accent)
        self._day.configure(self._display_family, px(120, e), ink_color)

        self._div_footer.configure(
            spacing=max(4, px(9, e)),
            ornament_size=max(4, px(7, e)),
            color=_with_alpha(qcolor(t.accent_2), 0.92),
        )

        self._top_banner.configure(
            motto="",
            accent=qcolor(t.accent),
            accent_2=qcolor(t.accent_2),
            line=qcolor(t.line),
            ink_soft=qcolor(t.ink_soft),
            font=QFont(self._quote_family, max(8, int(round(px(9.5, e))))),
        )

    def _apply_fonts(self) -> None:
        e = self._eff
        t = self._theme
        self._ui_family = _resolve_family(t.font_ui, "Tahoma")
        self._display_family = _resolve_family(t.font_display, self._ui_family)
        self._quote_family = _resolve_family(t.font_quote, "Times New Roman")

        def make(family: str, size: float, weight: QFont.Weight = _WEIGHT_NORMAL, *, italic: bool = False, spacing: float | None = None) -> QFont:
            f = QFont(family)
            f.setPixelSize(max(6, int(round(size))))
            f.setWeight(weight)
            f.setItalic(italic)
            f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            if spacing is not None:
                f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(spacing))
            return f

        self._col1_month_en.setFont(make(self._ui_family, max(px(10.5, e), 8), _WEIGHT_BOLD, spacing=px(1.0, e)))
        self._col1_month_vn.setFont(make(self._ui_family, max(px(13.2, e), 10), _WEIGHT_BOLD))
        self._col1_zodiac.setFont(make(self._ui_family, max(px(9.5, e), 8), _WEIGHT_DEMI))
        self._col1_hours_title.setFont(make(self._ui_family, max(px(8.8, e), 7.5), _WEIGHT_BOLD, spacing=px(0.8, e)))
        self._col1_hours.setFont(make(self._ui_family, max(px(9.2, e), 7.5), _WEIGHT_MEDIUM))
        self._col1_footer.setFont(make(self._ui_family, max(px(8.8, e), 7.5), _WEIGHT_DEMI))

        self._col2_weekday.setFont(make(self._ui_family, max(px(19.0, e), 13), _WEIGHT_BLACK, spacing=px(1.8, e)))
        self._col2_weekday_en.setFont(make(self._ui_family, max(px(10.2, e), 8), _WEIGHT_DEMI, spacing=px(1.4, e)))

        self._col3_lunar_month.setFont(make(self._ui_family, max(px(12.0, e), 9.0), _WEIGHT_BOLD))
        f_canchi = make(self._ui_family, max(px(10.2, e), 8), _WEIGHT_MEDIUM)
        self._col3_canchi_month.setFont(f_canchi)
        self._col3_canchi_day.setFont(f_canchi)
        self._col3_canchi_hour.setFont(f_canchi)
        self._col3_canchi_year.setFont(f_canchi)
        self._col3_tiet_khi.setFont(make(self._ui_family, max(px(9.5, e), 7.5), _WEIGHT_NORMAL, italic=True))

        self._quote_label.setFont(make(self._quote_family, max(px(11.8, e), 9), _WEIGHT_NORMAL, italic=True))
        self._credit.setFont(make(self._ui_family, max(px(8.8, e), 7.5), _WEIGHT_MEDIUM))

    # ------------------------------------------------------------------
    # Nội bộ: nạp nội dung
    # ------------------------------------------------------------------

    def _sync_content(self) -> None:
        info = self._info
        if info is None:
            for w in self._all_widgets:
                w.hide()
            return

        e = self._eff
        t = self._theme

        # 1. Thân giữa
        self._day.setText(str(info.solar.day))
        ink_col = qcolor(t.accent) if (info.is_sunday or info.holiday) else qcolor(t.ink)
        self._day.configure(self._display_family, px(120, e), ink_col)

        # 2. Chân lịch - Cột 1
        self._col1_month_en.setText(f"{info.solar.year} · {info.solar_month_en}")
        self._col1_month_vn.setText(info.solar_month_vn)
        zodiac_txt = "Ngày Hoàng Đạo" if info.is_auspicious_day else "Ngày Hắc Đạo"
        self._col1_zodiac.setText(f"✦ {zodiac_txt}")
        self._col1_hours_title.setText("GIỜ HOÀNG ĐẠO")

        hours = info.auspicious_hours
        if self._show_auspicious and hours:
            # Hiển thị dạng gọn 2 dòng: Sửu · Thìn · Ngọ / Mùi · Tuất · Hợi
            chis = [h.chi for h in hours]
            l1 = " · ".join(chis[:3])
            l2 = " · ".join(chis[3:6])
            self._col1_hours.setText(f"{l1}\n{l2}")
            tt_lines = [f"Giờ {h.chi} ({h.time_text}) · {h.god}" for h in hours]
            self._col1_hours.setToolTip("\n".join(tt_lines))
            self._col1_hours.setVisible(True)
            self._col1_hours_title.setVisible(True)
        else:
            self._col1_hours.setText("")
            self._col1_hours.setVisible(False)
            self._col1_hours_title.setVisible(False)

        self._col1_footer.setText(f"Tuần {info.week_of_year} · Ngày {info.day_of_year}")

        # 3. Chân lịch - Cột 2
        self._col2_weekday.setText(WEEKDAY_UPPER[info.weekday_index])
        self._col2_weekday_en.setText(info.weekday_en)

        lunar = info.lunar
        if lunar.day == 1:
            pill_text = "MÙNG 1"
            pill_word = True
        elif lunar.day == 15:
            pill_text = "RẰM"
            pill_word = True
        else:
            pill_text = str(lunar.day)
            pill_word = False

        lunar_font_family = self._ui_family if pill_word else self._display_family
        lunar_weight = _WEIGHT_BOLD if pill_word else _WEIGHT_BLACK
        lunar_size = max(18, int(round(px(24 if pill_word else 48, e))))
        l_font = QFont(lunar_font_family)
        l_font.setPixelSize(lunar_size)
        l_font.setWeight(lunar_weight)
        l_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        # Màu số âm lịch: xanh lục ngọc truyền thống sang trọng
        lunar_color = QColor("#1E7E34") if not (info.is_sunday or info.holiday) else qcolor(t.accent)
        self._lunar_pill.configure(
            pill_text,
            l_font,
            ink=lunar_color,
            line_color=_with_alpha(qcolor(t.line), 0.75),
            ornament_color=qcolor(t.accent_2),
        )

        # 4. Chân lịch - Cột 3
        m_name = LUNAR_MONTH_NAMES[lunar.month - 1].upper()
        leap = " (N)" if lunar.leap else ""
        self._col3_lunar_month.setText(f"THÁNG {m_name}{leap} ({info.lunar_month_char})")

        self._col3_canchi_month.setText(f"✦ Tháng {info.month_can_chi.text}")
        self._col3_canchi_day.setText(f"✦ Ngày {info.day_can_chi.text}")
        self._col3_canchi_hour.setText(f"✦ Giờ {info.hour_ty_can_chi.text}")
        self._col3_canchi_year.setText(f"✦ Năm {info.year_can_chi.text}")

        tiet = (info.tiet_khi or "").strip()
        if self._show_tiet_khi and tiet:
            self._col3_tiet_khi.setText(f"Tiết {tiet}")
            self._col3_tiet_khi.setVisible(True)
        else:
            self._col3_tiet_khi.setText("")
            self._col3_tiet_khi.setVisible(False)

        # Banner châm ngôn
        motto = "Gia đình hạnh phúc là nền tảng của xã hội thịnh vượng"
        if info.holiday:
            motto = f"Chúc mừng {info.holiday}"
        self._top_banner.configure(
            motto=motto,
            accent=qcolor(t.accent),
            accent_2=qcolor(t.accent_2),
            line=qcolor(t.line),
            ink_soft=qcolor(t.ink_soft),
            font=QFont(self._quote_family, max(8, int(round(px(9.5, e))))),
        )

    def _sync_quote(self) -> None:
        quote = self._quote
        if quote is None or not quote.text.strip():
            self._quote_label.setText("")
            self._credit.setText("")
            self._quote_visible = False
            self._credit_visible = False
            self._quote_label.setVisible(False)
            self._credit.setVisible(False)
            return

        self._quote_visible = True
        author = (quote.credit or "").strip()
        if not author:
            author = _TOPIC_CREDIT.get(quote.topic, "Ca dao")
        self._credit.setText(f"— {author} —")
        self._quote_label.setToolTip(f"{quote.text.strip()}\n\nBấm để đổi câu danh ngôn khác")

    # ------------------------------------------------------------------
    # Nội bộ: hình học & bố cục
    # ------------------------------------------------------------------

    def _compute_eff(self, width: float, height: float) -> float:
        w = float(width) if width > 0 else _DESIGN_W * self._scale
        h = float(height) if height > 0 else _DESIGN_H * self._scale
        fit = min(w / _DESIGN_W, h / _DESIGN_H)
        return max(0.45, min(self._scale, fit, 3.2))

    def _is_embedded(self) -> bool:
        override = getattr(self, "_embedded_override", None)
        if override is not None:
            return bool(override)
        host = self.window()
        return host is not self and host.testAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

    def _paper_radius(self) -> float:
        if self._is_embedded():
            return float(max(4, self._theme.radius))
        return float(px(self._theme.radius, self._eff))

    def _paper_rect(self) -> QRectF:
        e = self._eff
        width = float(self.width())
        height = float(self.height())
        if self._is_embedded():
            return QRectF(0.5, 0.5, max(8.0, width - 1.0), max(8.0, height - 1.0))
        left = px(2, e)
        top = px(1, e)
        right = px(3, e)
        bottom = px(18, e)
        return QRectF(
            float(left),
            float(top),
            max(8.0, width - left - right),
            max(8.0, height - top - bottom),
        )

    def _paper_path(self, rect: QRectF | None = None) -> QPainterPath:
        paper = self._paper_rect() if rect is None else rect
        radius = self._paper_radius()
        path = QPainterPath()
        path.addRoundedRect(paper, radius, radius)
        return path

    def _content_rect(self) -> QRectF:
        paper = self._paper_rect()
        e = self._eff
        band_h = px(26, e)
        top_gap = px(5, e)
        side = max(float(px(10, e)), float(self.width()) * 0.045)
        left = paper.left() + side
        right = paper.right() - side
        top = paper.top() + band_h + top_gap
        bottom = paper.bottom() - px(8, e)
        return QRectF(left, top, max(24.0, right - left), max(24.0, bottom - top))

    def _relayout(self) -> None:
        if self.width() < 20 or self.height() < 20:
            return
        self._eff = self._compute_eff(self.width(), self.height())
        if abs(self._eff - self._qss_scale) > 0.10:
            self.setStyleSheet(build_stylesheet(self._theme, max(0.45, self._eff)))
            self._qss_scale = self._eff

        self._apply_fonts()
        self._sync_content()
        self._sync_quote()

        e = self._eff
        t = self._theme
        content = self._content_rect()
        cw = content.width()
        avail_h = content.height()

        has_info = self._info is not None
        if not has_info:
            for w in self._all_widgets:
                w.hide()
            return

        # -------------------------------------------------------------
        # 1. PHÂN CHIA KHÔNG GIAN DỌC
        # -------------------------------------------------------------
        # Đỉnh: banner hoa văn (khoảng 8-10% chiều cao)
        h_top = max(30, int(round(px(40, e))))
        gap_top_mid = max(2, px(4, e))

        # Chân lịch 3 cột: chiếm khoảng 38-42% chiều cao
        h_footer = max(int(round(px(130, e))), int(round(avail_h * 0.40)))
        h_footer = min(h_footer, int(avail_h * 0.48))
        gap_mid_footer = max(3, px(5, e))
        h_div = max(4, px(5, e))

        # Thân giữa: nhận trọn phần còn lại
        h_mid = avail_h - h_top - gap_top_mid - h_footer - gap_mid_footer - h_div
        h_mid = max(px(60, e), h_mid)

        # -------------------------------------------------------------
        # 2. BỐ TRÍ ĐỈNH LỊCH (_TopArtBanner)
        # -------------------------------------------------------------
        y = content.top()
        self._top_banner.setGeometry(int(content.left()), int(round(y)), int(cw), h_top)
        self._top_banner.setVisible(True)
        y += h_top + gap_top_mid

        # -------------------------------------------------------------
        # 3. BỐ TRÍ THÂN GIỮA (Số ngày Dương lớn + Ca dao)
        # -------------------------------------------------------------
        mid_top = y
        fm_quote = QFontMetricsF(self._quote_label.font())
        fm_credit = QFontMetricsF(self._credit.font())
        h_credit = int(math.ceil(fm_credit.height()))
        line_h_quote = int(math.ceil(fm_quote.height()))

        quote_text = self._quote.text.strip() if (self._quote_visible and self._quote) else ""
        credit_visible = self._quote_visible and self.height() >= 340 and bool(quote_text)
        self._credit_visible = credit_visible

        h_quote_total = 0
        quote_lines: list[str] = []
        if quote_text:
            max_q_lines = 2 if self.height() >= 360 else 1
            quote_lines = _wrap_elided(quote_text, fm_quote, cw * 0.92, max_q_lines)
            h_quote_total = len(quote_lines) * line_h_quote
            self._quote_label.setText("\n".join(quote_lines))
        else:
            self._quote_label.setText("")

        h_quote_block = h_quote_total + (h_credit + px(3, e) if credit_visible else 0)
        gap_day_quote = max(2, px(4, e)) if h_quote_block > 0 else 0

        day_h = int(h_mid - h_quote_block - gap_day_quote)
        day_h = max(px(45, e), day_h)

        # Số ngày dương
        day_px = self._fit_day_font(self._day.text(), cw, day_h)
        ink_col = qcolor(t.accent) if (self._info.is_sunday or self._info.holiday) else qcolor(t.ink)
        self._day.configure(self._display_family, day_px, ink_col)
        self._day.setGeometry(int(content.left()), int(round(mid_top)), int(cw), day_h)
        self._day.setVisible(True)

        # Ca dao & nguồn
        q_y = mid_top + day_h + gap_day_quote
        if h_quote_total > 0:
            self._quote_label.setGeometry(int(content.left()), int(round(q_y)), int(cw), h_quote_total)
            self._quote_label.setVisible(True)
            q_y += h_quote_total + px(2, e)
        else:
            self._quote_label.setVisible(False)

        if credit_visible:
            self._credit.setGeometry(int(content.left()), int(round(q_y)), int(cw), h_credit)
            self._credit.setVisible(True)
        else:
            self._credit.setVisible(False)

        # -------------------------------------------------------------
        # 4. PHÂN CÁCH CHÂN LỊCH
        # -------------------------------------------------------------
        y_div = content.top() + avail_h - h_footer - h_div - px(2, e)
        self._div_footer.setGeometry(int(content.left()), int(round(y_div)), int(cw), h_div)
        self._div_footer.configure(
            spacing=max(4, px(8, e)),
            ornament_size=max(4, px(6, e)),
            color=_with_alpha(qcolor(t.accent_2), 0.90),
        )
        self._div_footer.setVisible(True)

        # -------------------------------------------------------------
        # 5. BỐ TRÍ CHÂN LỊCH 3 CỘT
        # -------------------------------------------------------------
        footer_top = y_div + h_div + px(2, e)
        footer_h = int(content.bottom() - footer_top)
        self._footer_top_y = footer_top
        self._footer_bottom_y = content.bottom()

        # Chiều rộng 3 cột: Cột 1 và Cột 3 rộng 32%, Cột 2 rộng 36%
        w1 = int(round(cw * 0.32))
        w2 = int(round(cw * 0.36))
        w3 = int(cw - w1 - w2)

        x1 = content.left()
        x2 = content.left() + w1
        x3 = content.left() + w1 + w2

        self._col_sep_1_x = x2
        self._col_sep_2_x = x3

        # ---- Cột 1 (Trái: Dương lịch & Hoàng đạo) ----
        pad1 = 2
        col1_w = w1 - 2 * pad1
        f_m_en = self._fit_label_font(self._col1_month_en.text(), self._ui_family, px(10.5, e), col1_w, 7, _WEIGHT_BOLD, spacing=px(1.0, e))
        self._col1_month_en.setFont(f_m_en)
        f_m_vn = self._fit_label_font(self._col1_month_vn.text(), self._ui_family, px(13.2, e), col1_w, 8, _WEIGHT_BOLD)
        self._col1_month_vn.setFont(f_m_vn)

        fm_m_en = QFontMetricsF(self._col1_month_en.font())
        fm_m_vn = QFontMetricsF(self._col1_month_vn.font())
        fm_zodiac = QFontMetricsF(self._col1_zodiac.font())
        fm_htitle = QFontMetricsF(self._col1_hours_title.font())
        fm_hours = QFontMetricsF(self._col1_hours.font())
        fm_footer = QFontMetricsF(self._col1_footer.font())

        h_m_en = int(math.ceil(fm_m_en.height()))
        h_m_vn = int(math.ceil(fm_m_vn.height()))
        h_zodiac = int(math.ceil(fm_zodiac.height()))
        h_htitle = int(math.ceil(fm_htitle.height()))
        h_hours = int(math.ceil(fm_hours.height())) * 2 if not self._col1_hours.isHidden() else 0
        h_col1_footer = int(math.ceil(fm_footer.height()))

        cy1 = footer_top
        self._col1_month_en.setGeometry(int(x1 + pad1), int(round(cy1)), col1_w, h_m_en)
        cy1 += h_m_en + px(1, e)

        self._col1_month_vn.setGeometry(int(x1 + pad1), int(round(cy1)), col1_w, h_m_vn)
        cy1 += h_m_vn + px(2, e)

        self._col1_zodiac.setGeometry(int(x1 + pad1), int(round(cy1)), col1_w, h_zodiac)
        cy1 += h_zodiac + px(3, e)

        if not self._col1_hours_title.isHidden():
            self._col1_hours_title.setGeometry(int(x1 + pad1), int(round(cy1)), col1_w, h_htitle)
            cy1 += h_htitle + px(1, e)

            # Giới hạn chiều cao danh sách giờ
            avail_hours_h = int(self._footer_bottom_y - cy1 - h_col1_footer - px(3, e))
            actual_hours_h = min(h_hours, max(12, avail_hours_h))
            self._col1_hours.setGeometry(int(x1 + pad1), int(round(cy1)), col1_w, actual_hours_h)
            cy1 += actual_hours_h + px(2, e)
        else:
            self._col1_hours_title.setGeometry(0, 0, 0, 0)
            self._col1_hours.setGeometry(0, 0, 0, 0)

        self._col1_footer.setGeometry(int(x1 + pad1), int(round(self._footer_bottom_y - h_col1_footer)), col1_w, h_col1_footer)

        self._col1_month_en.setVisible(True)
        self._col1_month_vn.setVisible(True)
        self._col1_zodiac.setVisible(True)
        self._col1_footer.setVisible(True)

        # ---- Cột 2 (Giữa: Thứ & Số ngày Âm cực lớn) ----
        pad2 = 3
        col2_w = w2 - 2 * pad2
        f_wd = self._fit_label_font(self._col2_weekday.text(), self._ui_family, px(19.0, e), col2_w, 10, _WEIGHT_BLACK, spacing=px(1.8, e))
        self._col2_weekday.setFont(f_wd)
        f_wden = self._fit_label_font(self._col2_weekday_en.text(), self._ui_family, px(10.2, e), col2_w, 7, _WEIGHT_DEMI, spacing=px(1.4, e))
        self._col2_weekday_en.setFont(f_wden)

        fm_wd = QFontMetricsF(self._col2_weekday.font())
        fm_wden = QFontMetricsF(self._col2_weekday_en.font())
        h_wd = int(math.ceil(fm_wd.height()))
        h_wden = int(math.ceil(fm_wden.height()))

        cy2 = footer_top
        self._col2_weekday.setGeometry(int(x2 + pad2), int(round(cy2)), col2_w, h_wd)
        cy2 += h_wd + px(1, e)

        self._col2_weekday_en.setGeometry(int(x2 + pad2), int(round(cy2)), col2_w, h_wden)
        cy2 += h_wden + px(3, e)

        lunar_h = int(self._footer_bottom_y - cy2 - px(2, e))
        lunar_h = max(24, lunar_h)
        self._lunar_pill.setGeometry(int(x2 + pad2), int(round(cy2)), col2_w, lunar_h)

        self._col2_weekday.setVisible(True)
        self._col2_weekday_en.setVisible(True)
        self._lunar_pill.setVisible(True)

        # ---- Cột 3 (Phải: Tháng âm & 4 Can Chi) ----
        pad3 = 2
        col3_w = w3 - 2 * pad3
        f_lm = self._fit_label_font(self._col3_lunar_month.text(), self._ui_family, px(12.0, e), col3_w, 7, _WEIGHT_BOLD)
        self._col3_lunar_month.setFont(f_lm)

        fm_lm = QFontMetricsF(self._col3_lunar_month.font())
        fm_cc = QFontMetricsF(self._col3_canchi_month.font())
        fm_tk = QFontMetricsF(self._col3_tiet_khi.font())

        h_lm = int(math.ceil(fm_lm.height()))
        h_cc = int(math.ceil(fm_cc.height()))
        h_tk = int(math.ceil(fm_tk.height()))

        cy3 = footer_top
        self._col3_lunar_month.setGeometry(int(x3 + pad3), int(round(cy3)), col3_w, h_lm)
        cy3 += h_lm + px(3, e)

        cc_gap = max(1, px(2, e))
        for cc_lbl in (self._col3_canchi_month, self._col3_canchi_day, self._col3_canchi_hour, self._col3_canchi_year):
            cc_lbl.setGeometry(int(x3 + pad3 + 1), int(round(cy3)), col3_w - 1, h_cc)
            cc_lbl.setVisible(True)
            cy3 += h_cc + cc_gap

        if not self._col3_tiet_khi.isHidden():
            self._col3_tiet_khi.setGeometry(int(x3 + pad3), int(round(self._footer_bottom_y - h_tk)), col3_w, h_tk)
        else:
            self._col3_tiet_khi.setGeometry(0, 0, 0, 0)

        self._col3_lunar_month.setVisible(True)

    def _fit_label_font(
        self,
        text: str,
        family: str,
        base_px: float,
        max_width: float,
        min_px: int = 7,
        weight: QFont.Weight = _WEIGHT_NORMAL,
        spacing: float | None = None,
    ) -> QFont:
        """Tự động thu nhỏ cỡ chữ để không bao giờ bị cắt hoặc tràn ngang."""
        font = QFont(family)
        font.setPixelSize(max(min_px, int(round(base_px))))
        font.setWeight(weight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        if spacing is not None:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(spacing))
        if not text or max_width <= 1:
            return font
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text)
        if width <= max_width:
            return font
        ratio = max_width / width
        new_size = max(min_px, int(math.floor(base_px * ratio)))
        font.setPixelSize(new_size)
        return font

    def _fit_day_font(self, text: str, avail_w: float, avail_h: int) -> int:
        text = text or ""
        if not text:
            return px(120, self._eff)
        e = self._eff
        base = px(165, e)
        font = _make_day_font(self._display_family, base)
        metrics = QFontMetricsF(font)
        advance = metrics.horizontalAdvance(text)
        tight_h = metrics.tightBoundingRect(text).height()
        size = float(base)
        if advance > 0:
            size = min(size, base * (avail_w * 0.94) / advance)
        if tight_h > 0:
            size = min(size, base * max(0.4, (avail_h - px(8, e)) / tight_h))
        size = max(float(px(40, e)), min(size, float(px(220, e))))
        return max(8, int(round(size)))

    # ------------------------------------------------------------------
    # Sự kiện & Vẽ nền
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._bg_layer = None
        self._relayout()

    def paintEvent(self, event) -> None:
        if self.width() < 12 or self.height() < 12:
            return
        self._eff = self._compute_eff(self.width(), self.height())
        t = self._theme
        painter = QPainter(self)
        paper_alpha = alpha_of(t.paper)
        if paper_alpha < 0.999:
            painter.setOpacity(paper_alpha)
            painter.drawPixmap(0, 0, self._background_layer())
            self._paint_column_separators(painter)
            painter.end()
            return
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self._paint_background(painter)
        self._paint_column_separators(painter)
        painter.end()

    def _paint_column_separators(self, painter: QPainter) -> None:
        """Vẽ 2 đường phân cách dọc mảnh mờ giữa 3 cột chân lịch."""
        if not (self._col_sep_1_x > 0 and self._footer_bottom_y > self._footer_top_y):
            return
        pen = QPen(_with_alpha(qcolor(self._theme.line), 0.65))
        pen.setWidthF(max(0.7, px(0.85, self._eff)))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        y1 = self._footer_top_y + px(3, self._eff)
        y2 = self._footer_bottom_y - px(3, self._eff)
        painter.drawLine(QPointF(self._col_sep_1_x, y1), QPointF(self._col_sep_1_x, y2))
        painter.drawLine(QPointF(self._col_sep_2_x, y1), QPointF(self._col_sep_2_x, y2))

    def _background_layer(self) -> QPixmap:
        cache = getattr(self, "_bg_layer", None)
        if cache is not None and cache.size() == self.size() and not cache.isNull():
            return cache
        pm = QPixmap(self.size())
        pm.fill(Qt.GlobalColor.transparent)
        layer = QPainter(pm)
        layer.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        saved = self._theme
        self._theme = self._solid_theme(saved)
        try:
            self._paint_background(layer)
        finally:
            self._theme = saved
        layer.end()
        self._bg_layer = pm
        return pm

    @staticmethod
    def _solid_theme(theme: Theme) -> Theme:
        def solid(color: str) -> str:
            c = QColor(color)
            c.setAlpha(255)
            return c.name()

        return replace(
            theme,
            paper=solid(theme.paper),
            paper_2=solid(theme.paper_2),
            paper_edge=solid(theme.paper_edge),
        )

    def _paint_background(self, painter: QPainter) -> None:
        t = self._theme
        embedded = self._is_embedded()
        paper = self._paper_rect()
        radius = self._paper_radius()
        path = QPainterPath()
        path.addRoundedRect(paper, radius, radius)

        if not embedded:
            self._paint_shadow(painter, paper, radius)
            self._paint_paper_edges(painter, paper, radius)

        gradient = QLinearGradient(
            paper.left(), paper.top(), paper.left(), paper.bottom()
        )
        paper_col = qcolor(t.paper)
        paper2_col = qcolor(t.paper_2)
        gradient.setColorAt(0.0, paper_col)
        gradient.setColorAt(0.58, _mix(paper_col, paper2_col, 0.45))
        gradient.setColorAt(1.0, paper2_col)
        painter.fillPath(path, QBrush(gradient))

        painter.save()
        painter.setClipPath(path)
        self._paint_light_and_grain(painter, paper)
        if embedded:
            self._paint_inner_page_stack(painter, paper, radius)
        painter.restore()

        self._paint_spine(painter, paper, radius)

        pen = QPen(qcolor(t.line))
        pen.setWidthF(max(0.8, px(1, self._eff) * 0.85))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _paint_shadow(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        e = self._eff
        shadow = qcolor(self._theme.shadow)
        base_alpha = max(0.10, shadow.alphaF())
        painter.setPen(Qt.PenStyle.NoPen)
        layers = 12
        spread = float(px(9, e))
        offset_y = float(px(3.5, e))
        for layer in range(layers, 0, -1):
            grow = spread * layer / layers
            rect = QRectF(
                paper.left() - grow * 0.75,
                paper.top() + offset_y + grow * 0.2,
                paper.width() + grow * 1.5,
                paper.height() + grow * 1.25,
            )
            fade = (1.0 - (layer - 1.0) / layers) ** 1.35
            color = QColor(shadow)
            color.setAlphaF(base_alpha * 0.070 * fade)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, radius + grow * 0.75, radius + grow * 0.75)
        pen = QPen(_with_alpha(shadow, min(0.55, base_alpha * 1.15)))
        pen.setWidthF(max(1.0, 1.5 * e))
        painter.setPen(pen)
        painter.drawLine(
            QPointF(paper.left() + radius * 0.6, paper.bottom() + px(1.0, e)),
            QPointF(paper.right() - radius * 0.6, paper.bottom() + px(1.0, e)),
        )
        painter.setPen(Qt.PenStyle.NoPen)

    def _paint_paper_edges(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        e = self._eff
        t = self._theme
        dark = t.dark
        layers = (
            (px(12, e), px(15, e), 0.55),
            (px(7, e), px(10, e), 0.38),
            (px(3, e), px(5.5, e), 0.20),
        )
        paper2 = qcolor(t.paper_2)
        edge = qcolor(t.paper_edge)
        shadow = qcolor(t.shadow)
        for order, (inset, dy, shade) in enumerate(layers):
            jitter = px(0.8, e) if order % 2 else 0
            rect = QRectF(
                paper.left() + inset + jitter,
                paper.top() + dy,
                paper.width() - 2 * inset - jitter,
                paper.height() - dy * 0.30,
            )
            depth = edge if not dark else _mix(paper2, shadow, 0.70)
            top_col = _solid(_mix(paper2, depth, 0.26 + shade * 0.55))
            bottom_col = _solid(_mix(top_col, shadow if not dark else _mix(edge, shadow, 0.55), 0.22 + order * 0.10))
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0.0, top_col)
            gradient.setColorAt(0.85, bottom_col)
            path = QPainterPath()
            corner = max(2.0, radius - inset * 0.22)
            path.addRoundedRect(rect, corner, corner)
            painter.fillPath(path, QBrush(gradient))
            pen = QPen(_with_alpha(_mix(edge, shadow, 0.30), 0.75))
            pen.setWidthF(max(0.7, 0.75 * e))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _paint_inner_page_stack(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        e = self._eff
        t = self._theme
        band = float(px(9, e))
        tone = _mix(qcolor(t.paper_edge), qcolor(t.paper_2), 0.35)
        gradient = QLinearGradient(
            paper.left(), paper.bottom() - band, paper.left(), paper.bottom()
        )
        gradient.setColorAt(0.0, _with_alpha(tone, 0.0))
        gradient.setColorAt(0.55, _with_alpha(tone, 0.50))
        gradient.setColorAt(1.0, _with_alpha(tone, 0.95))
        painter.fillRect(
            QRectF(paper.left(), paper.bottom() - band, paper.width(), band),
            QBrush(gradient),
        )
        line_color = _mix(qcolor(t.paper_edge), qcolor(t.ink_soft), 0.30)
        for index, alpha in ((1, 0.55), (2, 0.32)):
            y = paper.bottom() - float(px(2.2 * index, e))
            pen = QPen(_with_alpha(line_color, alpha))
            pen.setWidthF(max(0.6, 0.7 * e))
            painter.setPen(pen)
            painter.drawLine(
                QPointF(paper.left() + radius * 0.8, y),
                QPointF(paper.right() - radius * 0.8, y),
            )
        painter.setPen(Qt.PenStyle.NoPen)

    def _paint_light_and_grain(self, painter: QPainter, paper: QRectF) -> None:
        e = self._eff
        t = self._theme
        light = QRadialGradient(
            QPointF(paper.left() + paper.width() * 0.26, paper.top() + paper.height() * 0.16),
            max(24.0, paper.width() * 0.95),
        )
        sheen = _with_alpha(qcolor(t.paper).lighter(112), 0.55)
        light.setColorAt(0.0, sheen)
        light.setColorAt(0.55, _with_alpha(sheen, 0.12))
        light.setColorAt(1.0, _with_alpha(sheen, 0.0))
        painter.fillRect(paper, QBrush(light))

        vign = QLinearGradient(
            paper.left(), paper.bottom() - paper.height() * 0.30, paper.left(), paper.bottom()
        )
        vign.setColorAt(0.0, _with_alpha(qcolor(t.shadow), 0.0))
        vign.setColorAt(1.0, _with_alpha(qcolor(t.shadow), 0.11))
        painter.fillRect(paper, QBrush(vign))

        ink = qcolor(t.ink)
        edge = qcolor(t.paper_edge)
        seed = (
            sum(ord(char) for char in t.name) * 131
            + int(paper.width()) * 17
            + int(paper.height()) * 31
        ) & 0x7FFFFFFF
        rng = random.Random(seed)
        grain_e = min(e, 1.5)
        painter.setPen(Qt.PenStyle.NoPen)

        margin = float(px(14, e))
        mottles = max(5, int(paper.width() * paper.height() / 30000))
        for _ in range(mottles):
            cx = rng.uniform(paper.left() + margin, paper.right() - margin)
            cy = rng.uniform(paper.top() + margin, paper.bottom() - margin)
            rx = rng.uniform(12.0, 42.0) * min(e, 1.8)
            ry = rx * rng.uniform(0.55, 1.05)
            tone = edge if rng.random() < 0.7 else ink
            painter.setBrush(_with_alpha(tone, rng.uniform(0.008, 0.017)))
            painter.drawEllipse(QPointF(cx, cy), rx, ry)

        count = max(260, int(paper.width() * paper.height() / 420))
        for _ in range(count):
            x = rng.uniform(paper.left(), paper.right())
            y = rng.uniform(paper.top(), paper.bottom())
            r = rng.uniform(0.35, 1.25) * grain_e
            painter.setBrush(_with_alpha(ink, rng.uniform(0.020, 0.058)))
            painter.drawEllipse(QPointF(x, y), r, r)

        fibers = max(40, int(paper.height() / 6))
        for _ in range(fibers):
            x = rng.uniform(paper.left(), paper.right())
            y = rng.uniform(paper.top(), paper.bottom())
            length = rng.uniform(8.0, 38.0) * grain_e
            color = _with_alpha(ink, rng.uniform(0.016, 0.042))
            pen = QPen(color)
            pen.setWidthF(max(0.5, 0.6 * grain_e))
            painter.setPen(pen)
            painter.drawLine(QPointF(x, y), QPointF(x + length, y + rng.uniform(-0.8, 0.8)))
        painter.setPen(Qt.PenStyle.NoPen)

    def _paint_spine(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        e = self._eff
        t = self._theme
        band_h = float(px(27, e))
        if paper.height() < band_h * 2.2:
            return
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(paper, radius, radius)
        painter.setClipPath(path)

        band = QRectF(paper.left(), paper.top(), paper.width(), band_h)
        tone = _mix(qcolor(t.paper), qcolor(t.paper_edge), 0.55 if t.dark else 0.40)
        gradient = QLinearGradient(band.topLeft(), band.bottomLeft())
        gradient.setColorAt(0.0, _mix(tone, qcolor(t.paper), 0.25))
        gradient.setColorAt(0.72, tone)
        gradient.setColorAt(1.0, _mix(tone, qcolor(t.paper_2), 0.55))
        painter.fillRect(band, QBrush(gradient))

        shade_h = float(px(10, e))
        shade = QLinearGradient(
            paper.left(),
            paper.top() + band_h,
            paper.left(),
            paper.top() + band_h + shade_h,
        )
        shade.setColorAt(0.0, _with_alpha(qcolor(t.shadow), 0.16))
        shade.setColorAt(1.0, _with_alpha(qcolor(t.shadow), 0.0))
        painter.fillRect(
            QRectF(paper.left(), paper.top() + band_h, paper.width(), shade_h),
            QBrush(shade),
        )

        pen = QPen(_with_alpha(_mix(qcolor(t.line), qcolor(t.ink_soft), 0.35), 0.95))
        pen.setWidthF(max(0.7, 0.8 * e))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(paper.left(), paper.top() + band_h),
            QPointF(paper.right(), paper.top() + band_h),
        )

        inset = max(float(px(22, e)), paper.width() * 0.075)
        count = 5
        usable = paper.width() - 2 * inset
        step = usable / (count - 1) if count > 1 else 0.0
        hole_r = max(2.2, float(px(3.0, e)))
        cy = paper.top() + band_h * 0.5
        hole_fill = _solid(_mix(qcolor(t.shadow), qcolor(t.paper_2), 0.20))
        rim = _mix(qcolor(t.paper_edge), qcolor(t.ink), 0.10)
        light = (
            _mix(qcolor(t.paper_edge), qcolor(t.ink), 0.16)
            if t.dark
            else qcolor(t.paper_edge).lighter(116)
        )
        for index in range(count):
            cx = paper.left() + inset + step * index
            painter.setPen(QPen(_with_alpha(rim, 0.88), max(0.7, 0.8 * e)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                QPointF(cx, cy), hole_r + max(1.0, 1.1 * e), hole_r + max(1.0, 1.1 * e)
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hole_fill)
            painter.drawEllipse(QPointF(cx, cy), hole_r, hole_r)
            painter.setPen(QPen(_with_alpha(light, 0.85), max(0.8, hole_r * 0.55)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(
                QRectF(cx - hole_r, cy - hole_r, hole_r * 2, hole_r * 2),
                195 * 16,
                150 * 16,
            )
        painter.restore()
