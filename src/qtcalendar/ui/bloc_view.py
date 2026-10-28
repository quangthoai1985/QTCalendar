"""Lịch ngày – mặt trước "tờ lịch bloc" truyền thống Việt Nam.

Thiết kế (từ trên xuống)
=======================

::

    ┌──────────────────────────────┐
    │ •   •   •   •                │  dải gáy: các lỗ đục như bloc thật
    │         TH Ứ  H A I          │  WEEKDAY_UPPER, chữ giãn, màu accent
    │           1 2                │  SolarDayLabel: cực lớn (≈ 132 px)
    │       THÁNG 10 · 2026        │  SolarMonthLabel
    │ ─────────────────────────    │  Divider nét đứt
    │           Â M  L Ị C H       │  LunarCaptionLabel (nhỏ, giãn chữ)
    │  ╭──────╮   tháng Chín       │  LunarPill (số âm lớn, viền accent)
    │  │  19  │   năm Bính Ngọ     │   + LunarMonthLabel/LunarYearLabel
    │  ╰──────╯                    │
    │ năm Bính Ngọ · Canh Tý       │  CanChiLabel (nhỏ hơn khối âm lịch)
    │ [Sương Giáng]  [Ngày hoàng…] │  TietKhiLabel + HolidayLabel
    │ ⏱  Tý 23–01  Sửu 01–03 …    │  6 chip ChipLabel
    │ ─────────────────────────    │
    │  "Một cây làm chẳng nên non…" │  QuoteLabel (nghiêng)
    │         — Ca dao —           │  CreditLabel
    └──────────────────────────────┘
       ▬▬▬  mép giấy xếp lớp phía dưới (vẽ trong paintEvent)

Khối âm lịch (điểm nhấn thị giác thứ hai sau số ngày dương)
------------------------------------------------------------

* Số ngày âm cỡ lớn (~52 px ở 344×468, gấp ~2,9 lần cỡ chữ cũ 17,8 px) đặt
  trong "viên thuốc" bo tròn: nền gradient accent rất nhạt, viền accent,
  chữ màu accent; vẽ tay (_LunarPill) để canh giữa theo thân chữ.
* Ngày 1 âm hiển thị **"Mùng 1"**, ngày 15 hiển thị **"Rằm"** (thay cho số);
  tháng nhuận hiển thị **"tháng Hai (nhuận)"**.
* Bên phải viên thuốc: "tháng Chín" (19,2 px DemiBold, màu ink) và
  "năm Bính Ngọ" (13,8 px DemiBold, màu ink_soft).
* Dòng Can Chi 3 cấp vẫn giữ nhưng nhỏ hơn (10,6 px, màu ink_soft).
* Cả khối co giãn theo cùng hệ số nội dung và **luôn hiện đủ** số + tháng +
  năm ở mọi kích thước (đã tự kiểm 240×310 … 980×1280).

Hợp đồng API
------------

``class BlocView(QWidget)``

``apply_theme(theme: Theme, scale: float = 1.0) -> None``
    Đổi bảng màu/cỡ chữ. View phải tự giữ ``theme`` và ``scale`` để dùng
    lại trong ``paintEvent``.

``set_day(info: DayInfo) -> None``
    Cập nhật toàn bộ nội dung một ngày. Đây là hàm **duy nhất** để đẩy dữ
    liệu vào view.

``set_quote(quote: Quote | None) -> None``
    Đặt câu ca dao; ``None`` = ẩn khu vực ca dao.

``set_show_auspicious(flag: bool)`` / ``set_show_tiet_khi(flag: bool)``
    Ẩn/hiện khu vực giờ hoàng đạo và tiết khí.

``refresh() -> None``
    Vẽ lại (gọi sau khi đổi theme/scale).

Tín hiệu: ``quote_clicked`` (bấm vào khung ca dao để đổi câu khác).

Yêu cầu thẩm mỹ
---------------

* Nền giấy: gradient ``paper`` → ``paper_2``, bo góc ``theme.radius``, viền
  mảnh ``theme.line``; phía dưới vẽ 2–3 "mép giấy" xếp lớp mỏng hơn để gợi
  cảm giác tập lịch dày.
* Số ngày dùng ``theme.font_display`` (Segoe UI Black), màu ``theme.ink``,
  canh giữa, tự thu nhỏ nếu khung quá hẹp (dùng ``QFontMetrics``).
* Chữ ca dao dùng ``theme.font_quote`` (Georgia), in nghiêng, màu
  ``theme.quote_ink``, tối đa 3 dòng rồi elide.
* Toàn bộ chữ phải hiển thị đúng dấu tiếng Việt.
* Không dùng ``QGraphicsDropShadowEffect`` (tốn RAM); bóng đổ vẽ tay trong
  ``paintEvent`` nếu cần.

Ghi chú triển khai
------------------

* Bố cục đặt tay (``setGeometry``) thay vì ``QVBoxLayout`` để kiểm soát nhịp
  dọc kiểu ấn phẩm: khoảng thở quanh số ngày, dòng ca dao luôn neo đáy, và
  khu vực ca dao tự co số dòng khi khung thấp.
* Toàn bộ typography của bloc đặt trong code (không đặt ``font-size`` trong
  QSS) để số ngày, Can Chi, trích dẫn có thể auto-fit theo bề rộng thật và
  không bị QSS ghi đè khi widget được polish lại.
* Hệ số phóng nội dung thực tế: ``min(scale, w/344, h/468)`` – ``scale`` do
  người dùng đặt nhưng luôn bị kẹp để nội dung không bao giờ tràn khung.
* **Chế độ nhúng**: khi view nằm trong một shell trong suốt đã tự vẽ bóng đổ
  quanh card (``widget_window.CalendarWidget``, nhận biết qua
  ``WA_TranslucentBackground`` của cửa sổ chủ), view tô giấy kín khung – khớp
  với ``MonthView`` – và thay bóng/mép giấy bên ngoài bằng dải "chân tập
  giấy" mảnh ở đáy. Ở chế độ chạy độc lập (script preview) view tự vẽ bóng
  mềm + 3 mép giấy xếp lớp đúng đặc tả.
* Chống tràn ở khung thấp: khu vực ca dao giảm số dòng tối đa 3 → 2 → 1
  (rồi elide), bỏ dòng ghi nguồn khi cao < 360 px; khoảng hở ca dao → nguồn
  luôn ≥ 6 px; số ngày thu theo cả bề rộng lẫn chiều cao bằng
  ``QFontMetrics``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

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

#: Kích thước "design" tham chiếu – mọi hệ số co giãn neo vào đây.
_DESIGN_W = 344
_DESIGN_H = 468

#: Nhãn nguồn cho từng chủ đề ca dao khi tác giả để trống.
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


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------


def _resolve_family(name: str, fallback: str) -> str:
    """Trả về họ font có thật trên máy (tự lùi nếu thiếu)."""
    families = set(QFontDatabase.families())
    if name in families:
        return name
    # "Segoe UI Black" → thử họ gốc "Segoe UI" (Qt trên một số nền tảng gộp weight).
    base = name.rsplit(" ", 1)[0] if " " in name else ""
    if base and base in families:
        return base
    if fallback in families:
        return fallback
    return QFontDatabase.families()[0] if QFontDatabase.families() else "Segoe UI"


def _mix(color_a: QColor, color_b: QColor, t: float) -> QColor:
    """Trộn hai màu theo tỉ lệ ``t`` (0 = a, 1 = b)."""
    t = max(0.0, min(1.0, t))
    return QColor(
        int(round(color_a.red() * (1 - t) + color_b.red() * t)),
        int(round(color_a.green() * (1 - t) + color_b.green() * t)),
        int(round(color_a.blue() * (1 - t) + color_b.blue() * t)),
        int(round(color_a.alpha() * (1 - t) + color_b.alpha() * t)),
    )


def _with_alpha(color: QColor, alpha: float) -> QColor:
    """Bản sao của ``color`` với độ mờ mới (0..1)."""
    out = QColor(color)
    out.setAlphaF(max(0.0, min(1.0, alpha)))
    return out


def _solid(color: QColor) -> QColor:
    """Bản sao đục hoàn toàn (bỏ alpha) – dùng cho các mảng giấy xếp lớp."""
    out = QColor(color)
    out.setAlpha(255)
    return out


def _make_day_font(family: str, pixel_size: int) -> QFont:
    """Font cho số ngày: Black weight + siết nhẹ khoảng chữ cho chắc tay."""
    font = QFont(family)
    font.setPixelSize(max(6, int(pixel_size)))
    font.setWeight(_WEIGHT_BLACK)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setLetterSpacing(
        QFont.SpacingType.AbsoluteSpacing, -max(0.4, pixel_size * 0.012)
    )
    return font


def _wrap_elided(text: str, metrics: QFontMetricsF, width: float, max_lines: int) -> list[str]:
    """Ngắt dòng văn bản theo bề rộng, tối đa ``max_lines`` dòng rồi elide."""
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
    """QLabel phát tín hiệu khi bấm – dùng cho khung ca dao."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - API Qt
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _DayNumber(QLabel):
    """Số ngày dương – tự vẽ để canh giữa theo *thân chữ* thay vì hộp dòng.

    QLabel canh giữa theo hộp dòng của font (cao hơn nhiều so với thân chữ số),
    nên với cỡ rất lớn sẽ bị lệch xuống và tốn chỗ. Vẽ tay với
    ``QFontMetricsF.tightBoundingRect`` cho phép tận dụng gần trọn chiều cao
    khu vực dành cho số ngày.
    """

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

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
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
        # "Mực thấm" rất nhẹ phía dưới – gợi cảm giác in typo, không phải bóng đổ.
        ghost = _with_alpha(self._ink, 0.10)
        painter.setPen(ghost)
        bleed = max(0.8, self._pixel_size * 0.008)
        painter.drawText(QPointF(x + bleed, y + bleed), text)
        painter.setPen(self._ink)
        painter.drawText(QPointF(x, y), text)


class _LunarPill(QWidget):
    """Hiển thị số ngày âm lịch cỡ lớn cân đối giữa hai đường nét hoa văn truyền thống."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LunarDayDisplay")
        self._text = ""
        self._font = QFont(get_theme(None).font_display)
        self._ink = qcolor(get_theme(None).accent)
        self._line_color = qcolor(get_theme(None).line)
        self._ornament_color = qcolor(get_theme(None).accent_2)
        self._border_w = 1.0

    def configure(
        self,
        text: str,
        font: QFont,
        *,
        ink: QColor,
        border: QColor | None = None,
        bg_top: QColor | None = None,
        bg_bottom: QColor | None = None,
        border_w: float = 1.0,
        radius: float = 0.0,
        line_color: QColor | None = None,
        ornament_color: QColor | None = None,
    ) -> None:
        self._text = text
        self._font = QFont(font)
        self._ink = QColor(ink)
        if line_color is not None:
            self._line_color = QColor(line_color)
        elif border is not None:
            self._line_color = QColor(border)
        if ornament_color is not None:
            self._ornament_color = QColor(ornament_color)
        self.update()

    def text(self) -> str:  # noqa: A003 - tên API thuận tiện cho self-check
        return self._text

    def font_for_paint(self) -> QFont:
        return QFont(self._font)

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
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

        # Mực thấm nhẹ gợi cảm giác in ấn truyền thống
        ghost = _with_alpha(self._ink, 0.12)
        painter.setPen(ghost)
        painter.drawText(QPointF(x + 1.0, y + 1.0), self._text)

        # Vẽ số ngày âm chính (màu accent đỏ son truyền thống)
        painter.setPen(self._ink)
        painter.drawText(QPointF(x, y), self._text)

        # Đường kẻ hoa văn đối xứng hai bên nếu chiều rộng đủ chỗ
        text_left = (w - tight.width()) / 2.0
        text_right = text_left + tight.width()
        margin = max(10.0, w * 0.07)
        gap = 12.0
        ornament_size = 5.0
        cy = h / 2.0

        if text_left - margin > gap + ornament_size + 14.0:
            # Đường kẻ bên trái
            pen = QPen(self._line_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            x_line_start = margin
            x_line_end = text_left - gap - ornament_size - 4.0
            painter.drawLine(QPointF(x_line_start, cy), QPointF(x_line_end, cy))

            # Hình thoi trang trí bên trái
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._ornament_color)
            p_left = QPainterPath()
            p_left.moveTo(text_left - gap - ornament_size / 2.0, cy - ornament_size / 2.0)
            p_left.lineTo(text_left - gap, cy)
            p_left.lineTo(text_left - gap - ornament_size / 2.0, cy + ornament_size / 2.0)
            p_left.lineTo(text_left - gap - ornament_size, cy)
            p_left.closeSubpath()
            painter.drawPath(p_left)

            # Đường kẻ bên phải
            painter.setPen(pen)
            x_r_start = text_right + gap + ornament_size + 4.0
            x_r_end = w - margin
            painter.drawLine(QPointF(x_r_start, cy), QPointF(x_r_end, cy))

            # Hình thoi trang trí bên phải
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
    """Chấm hình thoi nhỏ giữa đường kẻ ngăn (chi tiết kiểu ấn phẩm)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DividerOrnament")
        self._color = qcolor(get_theme(None).accent_2)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        side = max(4, int(round(self.height() or 8)))
        return QSize(side, side)

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
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
    """Một dòng ngăn cách: nét đứt bên trái · hình thoi · nét đứt bên phải."""

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
# View
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Plan:
    """Kết quả chọn bố cục cho một kích thước khung."""

    day_h: int
    gaps: dict[str, int]
    badge_widgets: list[QLabel]
    badge_rows: list[list[QLabel]]
    badge_h: int
    badges_h: int
    chips: list[QLabel]
    chip_rows: list[list[QLabel]]
    chip_w: int
    chip_h: int
    chips_h: int
    hours_h: int
    show_caption: bool
    quote_lines: list[str]
    quote_h: int
    stretch: int


class BlocView(QWidget):
    """Mặt trước lịch bloc."""

    #: Phát khi người dùng bấm vào khung ca dao (đổi câu khác).
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
        self._hours_visible: bool = False
        self._quote_visible: bool = False
        self._credit_visible: bool = False
        self._badge_tiet_visible: bool = False
        self._badge_holiday_visible: bool = False
        self._badge_ausp_visible: bool = False
        self._day_px: int = 120
        self._pill_text: str = ""
        self._pill_is_word: bool = False
        self._pill_factor: float = 1.0
        self._qss_scale: float = 0.0

        # ---- font / metrics (dựng lại mỗi lần relayout) ----
        self._ui_family = _resolve_family(self._theme.font_ui, "Tahoma")
        self._display_family = _resolve_family(self._theme.font_display, self._ui_family)
        self._quote_family = _resolve_family(self._theme.font_quote, "Times New Roman")
        self._f_weekday = QFont(self._ui_family)
        self._f_month = QFont(self._ui_family)
        self._f_lunar_caption = QFont(self._ui_family)
        self._f_lunar_month = QFont(self._ui_family)
        self._f_lunar_year = QFont(self._ui_family)
        self._f_canchi = QFont(self._ui_family)
        self._f_quote = QFont(self._quote_family)
        self._f_credit = QFont(self._ui_family)
        self._f_chip = QFont(self._ui_family)
        self._f_badge = QFont(self._ui_family)
        self._f_holiday = QFont(self._ui_family)
        self._f_caption = QFont(self._ui_family)

        # ---- con: dòng thứ ----
        self._weekday = QLabel("", self)
        self._weekday.setObjectName("WeekdayLabel")
        self._weekday.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- con: số ngày ----
        self._day = _DayNumber(self)

        # ---- con: tháng / năm ----
        self._month = QLabel("", self)
        self._month.setObjectName("SolarMonthLabel")
        self._month.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- ngăn cách 1 ----
        self._div1 = _DividerRow(self)

        # ---- khối âm lịch: caption · viên thuốc số ngày · tháng · năm ----
        self._lunar_caption = QLabel("ÂM LỊCH", self)
        self._lunar_caption.setObjectName("LunarCaptionLabel")
        self._lunar_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lunar_pill = _LunarPill(self)

        self._lunar_month = QLabel("", self)
        self._lunar_month.setObjectName("LunarMonthLabel")
        self._lunar_month.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lunar_year = QLabel("", self)
        self._lunar_year.setObjectName("LunarYearLabel")
        self._lunar_year.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._canchi = QLabel("", self)
        self._canchi.setObjectName("CanChiLabel")
        self._canchi.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- badge: tiết khí · ngày lễ · ngày hoàng đạo ----
        self._badge_tiet = QLabel("", self)
        self._badge_tiet.setObjectName("TietKhiLabel")
        self._badge_tiet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_holiday = QLabel("", self)
        self._badge_holiday.setObjectName("HolidayLabel")
        self._badge_holiday.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_ausp = QLabel("Ngày hoàng đạo", self)
        self._badge_ausp.setObjectName("AuspiciousDayLabel")
        self._badge_ausp.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- giờ hoàng đạo ----
        self._hours_caption = QLabel("GIỜ HOÀNG ĐẠO", self)
        self._hours_caption.setObjectName("SectionCaption")
        self._hours_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hour_chips: list[QLabel] = []
        for _ in range(6):
            chip = QLabel("", self)
            chip.setObjectName("ChipLabel")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hour_chips.append(chip)

        # ---- ngăn cách 2 + ca dao ----
        self._div2 = _DividerRow(self)

        self._quote_label = _ClickableLabel(self)
        self._quote_label.setObjectName("QuoteLabel")
        self._quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quote_label.setToolTip("Bấm để đổi câu ca dao khác")
        self._quote_label.clicked.connect(self.quote_clicked)

        self._credit = QLabel("", self)
        self._credit.setObjectName("CreditLabel")
        self._credit.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._all_widgets: tuple[QWidget, ...] = (
            self._weekday,
            self._day,
            self._month,
            self._div1,
            self._lunar_caption,
            self._lunar_pill,
            self._lunar_month,
            self._lunar_year,
            self._canchi,
            self._badge_tiet,
            self._badge_holiday,
            self._badge_ausp,
            self._hours_caption,
            *self._hour_chips,
            self._div2,
            self._quote_label,
            self._credit,
        )
        for widget in self._all_widgets:
            widget.hide()

        self._apply_fonts()
        self._apply_theme_colors()

    # ------------------------------------------------------------------
    # API công khai
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        """Kích thước gợi ý theo design × scale."""
        return QSize(px(_DESIGN_W, self._scale), px(_DESIGN_H, self._scale))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - API Qt
        """Khung nhỏ nhất còn đọc được (cố định, không nhân theo scale).

        Quan trọng: nếu nhân theo ``self._scale`` thì content scale của shell
        (vốn tăng khi cửa sổ to ra) sẽ làm *minimum layout* của cửa sổ lớn dần
        và chặn việc kéo thu nhỏ về 260×330 – đây là lỗi ``test_widget_window``
        bắt được. Vì vậy luôn trả về kích thước thiết kế nhỏ nhất cố định.
        """
        return QSize(px(236, 1.0), px(300, 1.0))

    def apply_theme(self, theme: Theme, scale: float = 1.0) -> None:
        """Đổi bảng màu/cỡ chữ và vẽ lại toàn bộ."""
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
        """Cập nhật toàn bộ nội dung một ngày."""
        self._info = info
        self._sync_content()
        self.refresh()

    def set_quote(self, quote: Quote | None) -> None:
        """Đặt câu ca dao; ``None`` = ẩn khu vực ca dao."""
        self._quote = quote
        self._sync_quote()
        self.refresh()

    def set_show_auspicious(self, flag: bool) -> None:
        """Ẩn/hiện khu vực giờ hoàng đạo."""
        self._show_auspicious = bool(flag)
        self.refresh()

    def set_show_tiet_khi(self, flag: bool) -> None:
        """Ẩn/hiện nhãn tiết khí."""
        self._show_tiet_khi = bool(flag)
        self.refresh()

    def refresh(self) -> None:
        """Vẽ lại (gọi sau khi đổi theme/scale/nội dung)."""
        self._bg_layer = None  # màu/kích thước có thể đã đổi
        self._relayout()
        self.update()

    # ------------------------------------------------------------------
    # Nội bộ: màu / font
    # ------------------------------------------------------------------

    @property
    def current_day(self) -> DayInfo | None:
        """Ngày đang hiển thị (``None`` nếu chưa có dữ liệu)."""
        return self._info

    def _apply_theme_colors(self) -> None:
        """Nạp màu theme vào các widget tự vẽ (QLabel còn lại do QSS lo)."""
        t = self._theme
        self._day.configure(self._display_family, self._day_px, qcolor(t.ink))
        for divider in (self._div1, self._div2):
            divider.configure(
                spacing=max(4, px(9, self._eff)),
                ornament_size=max(4, px(7, self._eff)),
                color=_with_alpha(qcolor(t.accent_2), 0.92),
            )

    def _apply_fonts(self) -> None:
        """Dựng lại toàn bộ font theo hệ số phóng nội dung hiện tại."""
        e = self._eff
        t = self._theme
        self._ui_family = _resolve_family(t.font_ui, "Tahoma")
        self._display_family = _resolve_family(t.font_display, self._ui_family)
        self._quote_family = _resolve_family(t.font_quote, "Times New Roman")

        def make(
            family: str,
            size: float,
            weight: QFont.Weight = _WEIGHT_NORMAL,
            *,
            italic: bool = False,
            spacing: float | None = None,
        ) -> QFont:
            font = QFont(family)
            font.setPixelSize(max(6, int(round(size))))
            font.setWeight(weight)
            font.setItalic(italic)
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            if spacing is not None:
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(spacing))
            return font

        self._f_weekday = make(
            self._ui_family, px(13.0, e), _WEIGHT_BOLD, spacing=px(3.1, e)
        )
        self._f_month = make(
            self._ui_family, px(11.6, e), _WEIGHT_DEMI, spacing=px(2.3, e)
        )
        self._f_lunar_caption = make(
            self._ui_family,
            max(px(9.4, e), 8),
            _WEIGHT_DEMI,
            spacing=max(px(2.6, e), 1.4),
        )
        self._f_lunar_month = make(
            self._ui_family, max(px(19.2, e), 12), _WEIGHT_DEMI
        )
        self._f_lunar_year = make(
            self._ui_family, max(px(13.8, e), 9), _WEIGHT_DEMI
        )
        self._f_canchi = make(
            self._ui_family, max(px(10.6, e), 8), _WEIGHT_NORMAL
        )
        self._f_quote = make(self._quote_family, px(13.4, e), _WEIGHT_NORMAL, italic=True)
        self._f_credit = make(
            self._ui_family, px(9.4, e), _WEIGHT_MEDIUM, spacing=px(1.5, e)
        )
        self._f_chip = make(self._ui_family, max(px(10.5, e), 8), _WEIGHT_MEDIUM)
        self._f_badge = make(self._ui_family, max(px(10.4, e), 8), _WEIGHT_DEMI)
        self._f_holiday = make(self._ui_family, max(px(10.4, e), 8), _WEIGHT_BOLD)
        self._f_caption = make(
            self._ui_family, px(8.6, e), _WEIGHT_DEMI, spacing=px(1.9, e)
        )

        self._weekday.setFont(self._f_weekday)
        self._month.setFont(self._f_month)
        self._lunar_caption.setFont(self._f_lunar_caption)
        self._lunar_month.setFont(self._f_lunar_month)
        self._lunar_year.setFont(self._f_lunar_year)
        self._canchi.setFont(self._f_canchi)
        self._badge_tiet.setFont(self._f_badge)
        self._badge_holiday.setFont(self._f_holiday)
        self._badge_ausp.setFont(self._f_badge)
        self._hours_caption.setFont(self._f_caption)
        for chip in self._hour_chips:
            chip.setFont(self._f_chip)
        self._quote_label.setFont(self._f_quote)
        self._credit.setFont(self._f_credit)
        for divider in (self._div1, self._div2):
            divider.configure(
                spacing=max(4, px(9, e)),
                ornament_size=max(4, px(7, e)),
                color=_with_alpha(qcolor(self._theme.accent_2), 0.92),
            )

    # ------------------------------------------------------------------
    # Nội bộ: nội dung
    # ------------------------------------------------------------------

    def _sync_content(self) -> None:
        info = self._info
        if info is None:
            self._weekday.setText("")
            self._day.setText("")
            self._month.setText("")
            self._lunar_caption.setText("")
            self._lunar_month.setText("")
            self._lunar_year.setText("")
            self._pill_text = ""
            self._pill_is_word = False
            self._pill_factor = 1.0
            self._canchi.setText("")
            self._hours_visible = False
            self._badge_tiet_visible = False
            self._badge_holiday_visible = False
            self._badge_ausp_visible = False
            for chip in self._hour_chips:
                chip.setText("")
                chip.hide()
            self._hours_caption.hide()
            self._badge_tiet.hide()
            self._badge_holiday.hide()
            self._badge_ausp.hide()
            return

        self._weekday.setText(WEEKDAY_UPPER[info.weekday_index])
        self._day.setText(str(info.solar.day))
        self._month.setText(f"THÁNG {info.solar.month} · {info.solar.year}")

        # --- khối âm lịch ---
        lunar = info.lunar
        self._lunar_caption.setText("—  Â M   L Ị C H  —")
        month_name = LUNAR_MONTH_NAMES[lunar.month - 1]
        leap = " (nhuận)" if lunar.leap else ""
        self._lunar_month.setText(f"Tháng {month_name}{leap} · Năm {info.year_can_chi.text}")
        self._lunar_year.setText("")
        if lunar.day == 1:
            self._pill_text = "MÙNG 1"
            self._pill_is_word = True
            self._pill_factor = 0.70
        elif lunar.day == 15:
            self._pill_text = "NGÀY RẰM"
            self._pill_is_word = True
            self._pill_factor = 0.72
        else:
            self._pill_text = str(lunar.day)
            self._pill_is_word = False
            self._pill_factor = 1.0
        tooltip = f"{info.lunar_line} · {info.year_can_chi.text}"
        self._lunar_month.setToolTip(tooltip)
        self._lunar_year.setToolTip(tooltip)
        self._lunar_pill.setToolTip(tooltip)

        # Dòng Can Chi: ngày và tháng
        self._canchi.setText(
            f"ngày {info.day_can_chi.text} · tháng {info.month_can_chi.text}"
        )

        # --- badge tiết khí / lễ / hoàng đạo ---
        tiet = (info.tiet_khi or "").strip()
        self._badge_tiet.setText(tiet)
        self._badge_tiet_visible = bool(tiet) and self._show_tiet_khi
        self._badge_tiet.setVisible(self._badge_tiet_visible)

        holiday = (info.holiday or "").strip()
        self._badge_holiday.setText(holiday)
        self._badge_holiday_visible = bool(holiday)
        self._badge_holiday.setVisible(self._badge_holiday_visible)

        self._badge_ausp_visible = bool(info.is_auspicious_day)
        self._badge_ausp.setVisible(self._badge_ausp_visible)

        # --- chip giờ hoàng đạo ---
        hours = info.auspicious_hours
        self._hours_visible = self._show_auspicious and bool(hours)
        for index, chip in enumerate(self._hour_chips):
            if index < len(hours):
                hour = hours[index]
                chip.setText(hour.compact_text)
                chip.setToolTip(f"Giờ {hour.chi} ({hour.time_text}) · {hour.god}")
                chip.setVisible(self._hours_visible)
            else:
                chip.setText("")
                chip.setVisible(False)
        self._hours_caption.setVisible(self._hours_visible)

    def _sync_quote(self) -> None:
        quote = self._quote
        if quote is None or not quote.text.strip():
            self._quote_label.setText("")
            self._credit.setText("")
            self._quote_visible = False
            self._quote_label.setVisible(False)
            self._credit.setVisible(False)
            self._div2.setVisible(False)
            return
        self._quote_visible = True
        author = (quote.credit or "").strip()
        if not author:
            author = _TOPIC_CREDIT.get(quote.topic, "Ca dao")
        self._credit.setText(f"— {author} —")
        self._quote_label.setToolTip(
            f"{quote.text.strip()}\n\nBấm để đổi câu ca dao khác"
        )

    # ------------------------------------------------------------------
    # Nội bộ: hình học
    # ------------------------------------------------------------------

    def _compute_eff(self, width: float, height: float) -> float:
        """Hệ số phóng nội dung thực tế.

        ``widget_window.CalendarWidget`` đã truyền vào ``apply_theme`` một
        *content scale* = ``settings.scale × tỉ lệ cửa sổ so với 344×468``
        (xem ``CalendarWidget.content_scale``), nên ở đây chỉ cần kẹp thêm
        theo kích thước khung thật để nội dung không bao giờ tràn: lấy
        ``min(scale, fit)``. Nhờ vậy khi người dùng kéo tay nắm resize, nội
        dung phóng/thu theo cửa sổ (do content scale) và luôn vừa khung.
        """
        w = float(width) if width > 0 else _DESIGN_W * self._scale
        h = float(height) if height > 0 else _DESIGN_H * self._scale
        fit = min(w / _DESIGN_W, h / _DESIGN_H)
        return max(0.45, min(self._scale, fit, 3.2))

    def _is_embedded(self) -> bool:
        """``True`` khi nằm trong shell trong suốt đã tự vẽ bóng đổ quanh card.

        ``widget_window.CalendarWidget`` đặt sẵn lề 10 px và tự vẽ bóng quanh
        vùng ``QStackedWidget`` (giống cách ``MonthView`` tô kín card). Ở chế
        độ đó view tô giấy kín khung và **không** vẽ bóng/mép giấy bên ngoài để
        tránh bóng đôi và vệt tối ở góc; thay vào đó là dải "chân tập giấy"
        mảnh ở đáy. Khi chạy độc lập (preview) view tự vẽ đủ bóng + mép giấy.
        """
        override = getattr(self, "_embedded_override", None)
        if override is not None:
            return bool(override)
        host = self.window()
        return host is not self and host.testAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

    def set_embedded(self, flag: bool | None) -> None:
        """Ép chế độ "phủ kín khung" (``True``) / tự vẽ bóng (``False``).

        ``None`` = tự nhận biết như cũ. ``CalendarWidget`` gọi ``True`` khi ghim
        desktop, vì lúc đó cửa sổ **đục** (cửa sổ con không nhận alpha) nên
        không được vẽ bóng/mép giấy — tránh sinh khung đen quanh lịch.
        """
        self._embedded_override = flag
        self._bg_layer = None
        self.update()

    def _paper_radius(self) -> float:
        """Bán kính bo góc của tờ giấy."""
        if self._is_embedded():
            return float(max(4, self._theme.radius))
        return float(px(self._theme.radius, self._eff))

    def _paper_rect(self) -> QRectF:
        e = self._eff
        width = float(self.width())
        height = float(self.height())
        if self._is_embedded():
            # shell đã lo bóng đổ: tờ giấy phủ kín card để khớp với MonthView
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
        top_gap = px(7, e)
        side = max(float(px(12, e)), float(self.width()) * 0.058)
        left = paper.left() + side
        right = paper.right() - side
        top = paper.top() + band_h + top_gap
        bottom = paper.bottom() - px(9, e)
        return QRectF(left, top, max(24.0, right - left), max(24.0, bottom - top))

    # ------------------------------------------------------------------
    # Nội bộ: bố cục
    # ------------------------------------------------------------------

    def _relayout(self) -> None:
        if self.width() < 20 or self.height() < 20:
            return
        self._eff = self._compute_eff(self.width(), self.height())
        # QSS của bloc được sinh theo scale người dùng; khi khung bị kéo giãn lớn
        # (eff lệch nhiều) thì sinh lại để bo góc/padding của chip, badge... cân
        # theo tỉ lệ nội dung thay vì bị "vuông" đi ở khung lớn.
        if abs(self._eff - self._qss_scale) > 0.10:
            self.setStyleSheet(build_stylesheet(self._theme, max(0.45, self._eff)))
            self._qss_scale = self._eff
        self._apply_fonts()
        self._sync_content()
        self._sync_quote()
        t = self._theme
        e = self._eff
        content = self._content_rect()
        cw = content.width()
        avail_h = content.height()

        # --- đo ---
        fm_weekday = QFontMetricsF(self._f_weekday)
        fm_month = QFontMetricsF(self._f_month)
        fm_lunar_caption = QFontMetricsF(self._f_lunar_caption)
        fm_lunar_month = QFontMetricsF(self._f_lunar_month)
        fm_lunar_year = QFontMetricsF(self._f_lunar_year)
        fm_canchi = QFontMetricsF(self._f_canchi)
        fm_quote = QFontMetricsF(self._f_quote)
        fm_credit = QFontMetricsF(self._f_credit)
        fm_chip = QFontMetricsF(self._f_chip)
        fm_badge = QFontMetricsF(self._f_badge)
        fm_holiday = QFontMetricsF(self._f_holiday)
        fm_caption = QFontMetricsF(self._f_caption)

        h_weekday = int(math.ceil(fm_weekday.height())) + 1
        h_month = int(math.ceil(fm_month.height()))
        h_canchi = int(math.ceil(fm_canchi.height()))
        line_h = int(math.ceil(fm_quote.height())) + px(1, e)
        h_credit = int(math.ceil(fm_credit.height()))
        h_caption = int(math.ceil(fm_caption.height()))
        h_lunar_caption = int(math.ceil(fm_lunar_caption.height()))

        margin_badge_x = px(8, e)
        margin_badge_y = px(3.4, e)
        h_badge = int(math.ceil(max(fm_badge.height(), fm_holiday.height()))) + 2 * margin_badge_y + 2
        margin_chip_x = px(6.4, e)
        margin_chip_y = px(2.2, e)
        h_chip = int(math.ceil(fm_chip.height())) + 2 * margin_chip_y + 2
        h_div = max(5, px(6, e))
        h_ornament = max(4, px(7, e))

        # --- khối âm lịch: caption + số ngày tâm + dòng tháng/năm ---
        lunar_num_px = max(int(px(28, e)), int(round(px(46, e))))
        lunar_day_h = int(round(lunar_num_px * 1.15))
        lunar_caption_gap = max(2, px(3, e))
        lunar_month_gap = max(2, px(3, e))

        month_text = self._lunar_month.text()
        month_font_px = max(int(px(14.0, e)), 11)
        lunar_month_font = self._fit_label_font(
            month_text, self._ui_family, month_font_px, cw, px(9, e), _WEIGHT_DEMI
        )
        fm_lunar_month = QFontMetricsF(lunar_month_font)
        h_lunar_month = int(math.ceil(fm_lunar_month.height()))
        h_lunar_year = 0
        h_lunar_block = h_lunar_caption + lunar_caption_gap + lunar_day_h + lunar_month_gap + h_lunar_month

        visible_badges: list[QLabel] = []
        if self._badge_tiet_visible:
            visible_badges.append(self._badge_tiet)
        if self._badge_holiday_visible:
            visible_badges.append(self._badge_holiday)
        if self._badge_ausp_visible:
            visible_badges.append(self._badge_ausp)

        badge_widths: dict[QLabel, int] = {}
        for label in visible_badges:
            metrics = fm_holiday if label is self._badge_holiday else fm_badge
            badge_widths[label] = (
                int(math.ceil(metrics.horizontalAdvance(label.text())))
                + 2 * margin_badge_x
                + 4
            )

        hours = self._info.auspicious_hours if (self._info and self._hours_visible) else ()
        chip_labels = list(self._hour_chips[: len(hours)])
        chip_widths = [
            int(math.ceil(fm_chip.horizontalAdvance(chip.text()))) + 2 * margin_chip_x + 4
            for chip in chip_labels
        ]
        chip_w = max(chip_widths) if chip_widths else 0
        chip_gap = px(5, e)
        chip_cols = 3 if len(chip_labels) > 3 else max(1, len(chip_labels))
        chip_rows_count = int(math.ceil(len(chip_labels) / chip_cols)) if chip_labels else 0
        chips_h = (
            chip_rows_count * h_chip + max(0, chip_rows_count - 1) * chip_gap
            if chip_rows_count
            else 0
        )

        quote_text = ""
        if self._quote_visible and self._quote is not None:
            quote_text = self._quote.text.strip()

        gaps = {
            "after_weekday": max(2, px(3, e)),
            "after_day": max(2, px(2, e)),
            "after_month": max(2, px(7, e)),
            "after_div1": max(2, px(6, e)),
            "after_lunar": max(1, px(5, e)),
            "after_canchi": max(2, px(6, e)),
            "after_badges": max(2, px(6, e)),
            "before_div2": max(2, px(7, e)),
            "after_div2": max(2, px(6, e)),
            "after_quote": max(6, px(9, e)),
        }

        # khung quá thấp: bỏ dòng ghi nguồn để ca dao không bị chật
        credit_visible = self._quote_visible and self.height() >= 360
        self._credit_visible = credit_visible

        badge_gap = max(5, px(7, e))
        badge_gap_y = max(4, px(5, e))

        h_badges = 0
        badge_rows: list[list[QLabel]] = []
        if visible_badges:
            badge_rows = _wrap_widths(visible_badges, badge_widths, cw, badge_gap)
            h_badges = len(badge_rows) * h_badge + max(0, len(badge_rows) - 1) * badge_gap_y

        # --- chọn phương án: số dòng ca dao / caption / độ co khoảng cách ---
        caption_visible = self._hours_visible and bool(hours)
        best: _Plan | None = None
        day_min = max(px(64, e), int(avail_h * 0.24))
        # khung càng thấp càng giảm số dòng ca dao tối đa (3 → 2 → 1) rồi elide
        if self.height() >= 400:
            quote_line_cap = 3
        elif self.height() >= 330:
            quote_line_cap = 2
        else:
            quote_line_cap = 1
        quote_options = tuple(
            value for value in (3, 2, 1, 0) if value <= quote_line_cap or value == 0
        )
        for quote_max in (quote_options if quote_text else (0,)):
            for use_caption in ((True, False) if caption_visible else (False,)):
                for gap_scale in (1.0, 0.86, 0.72):
                    s = gap_scale
                    g = {key: max(1, int(round(value * s))) for key, value in gaps.items()}
                    quote_lines = (
                        _wrap_elided(quote_text, fm_quote, cw, quote_max)
                        if quote_max
                        else []
                    )
                    h_quote = len(quote_lines) * line_h
                    h_hours = (
                        (h_caption + px(4, e) if use_caption else 0) + chips_h
                        if self._hours_visible
                        else 0
                    )
                    top_fixed = (
                        h_weekday
                        + g["after_weekday"]
                        + g["after_day"]
                        + h_month
                        + g["after_month"]
                        + h_div
                        + g["after_div1"]
                        + h_lunar_block
                        + g["after_lunar"]
                        + h_canchi
                        + g["after_canchi"]
                        + h_badges
                        + (g["after_badges"] if self._hours_visible else 0)
                        + h_hours
                    )
                    if self._quote_visible:
                        bottom_fixed = (
                            g["before_div2"]
                            + h_div
                            + g["after_div2"]
                            + h_quote
                            + (
                                g["after_quote"] + h_credit
                                if credit_visible
                                else max(3, px(4, e))
                            )
                        )
                    else:
                        bottom_fixed = 0
                    day_h = int(avail_h - top_fixed - bottom_fixed)
                    plan = _Plan(
                        day_h=day_h,
                        gaps=g,
                        badge_widgets=visible_badges,
                        badge_rows=badge_rows,
                        badge_h=h_badge,
                        badges_h=h_badges,
                        chips=chip_labels,
                        chip_rows=[
                            chip_labels[i : i + chip_cols]
                            for i in range(0, len(chip_labels), chip_cols)
                        ],
                        chip_w=chip_w,
                        chip_h=h_chip,
                        chips_h=chips_h,
                        hours_h=h_hours,
                        show_caption=use_caption,
                        quote_lines=quote_lines,
                        quote_h=h_quote,
                        stretch=0,
                    )
                    if best is None:
                        best = plan
                    if day_h >= day_min:
                        best = plan
                        break
                if best is not None and best.day_h >= day_min:
                    break
            if best is not None and best.day_h >= day_min:
                break
        plan = best

        # đặt nội dung ca dao đã ngắt dòng vào nhãn
        if self._quote_visible and plan.quote_lines:
            self._quote_label.setText("\n".join(plan.quote_lines))
        elif self._quote_visible:
            self._quote_label.setText("")

        day_h = plan.day_h
        day_cap = px(196, e)
        if day_h > day_cap:
            plan.stretch = day_h - day_cap
            day_h = day_cap
        day_h = max(px(52, e), day_h)
        if plan.stretch < 0:
            plan.stretch = 0
        plan.day_h = day_h

        # --- dàn vị trí ---
        self._weekday.setGeometry(
            int(content.left()),
            int(content.top()),
            int(cw),
            h_weekday,
        )
        y = content.top() + h_weekday + plan.gaps["after_weekday"]

        # số ngày: tự thu nhỏ để vừa cả bề rộng lẫn chiều cao khu vực
        day_px = self._fit_day_font(self._day.text(), cw, day_h)
        self._day.configure(self._display_family, day_px, qcolor(t.ink))
        self._day.setGeometry(int(content.left()), int(round(y)), int(cw), day_h)
        y += day_h + plan.gaps["after_day"]

        self._month.setGeometry(int(content.left()), int(round(y)), int(cw), h_month)
        y += h_month + plan.gaps["after_month"]

        self._place_divider(self._div1, content.left(), y, cw, h_div, h_ornament)
        y += h_div + plan.gaps["after_div1"]

        # --- khối âm lịch: caption · số ngày âm ở tâm · tháng/năm ---
        self._lunar_caption.setGeometry(
            int(round(content.left())), int(round(y)), int(cw), h_lunar_caption
        )
        y += h_lunar_caption + lunar_caption_gap

        # font số ngày âm: display Bold/Black
        pill_text = self._pill_text
        if self._pill_is_word:
            pill_family = self._ui_family
            pill_weight = _WEIGHT_BOLD
            pill_font_px = int(round(lunar_num_px * self._pill_factor))
        else:
            pill_family = self._display_family
            pill_weight = _WEIGHT_BLACK
            pill_font_px = lunar_num_px
        pill_font = QFont(pill_family)
        pill_font.setPixelSize(max(8, pill_font_px))
        pill_font.setWeight(pill_weight)
        pill_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        accent = qcolor(t.accent)
        self._lunar_pill.configure(
            pill_text,
            pill_font,
            ink=accent,
            line_color=_with_alpha(qcolor(t.line), 0.75),
            ornament_color=qcolor(t.accent_2),
        )
        self._lunar_pill.setGeometry(
            int(round(content.left())), int(round(y)), int(cw), lunar_day_h
        )
        y += lunar_day_h + lunar_month_gap

        self._lunar_month.setFont(lunar_month_font)
        self._lunar_month.setGeometry(
            int(round(content.left())), int(round(y)), int(cw), h_lunar_month
        )
        self._lunar_year.setGeometry(0, 0, 0, 0)
        y += h_lunar_month + plan.gaps["after_lunar"]

        # Can Chi: thu nhỏ cỡ chữ nếu quá dài
        canchi_font = self._fit_label_font(
            self._canchi.text(),
            self._ui_family,
            max(px(10.6, e), 8),
            cw,
            px(8, e),
            _WEIGHT_NORMAL,
        )
        if canchi_font != self._f_canchi:
            self._f_canchi = canchi_font
            self._canchi.setFont(canchi_font)
        fm_canchi = QFontMetricsF(self._canchi.font())
        self._canchi.setGeometry(
            int(content.left()), int(round(y)), int(cw), int(math.ceil(fm_canchi.height()))
        )
        y += int(math.ceil(fm_canchi.height())) + plan.gaps["after_canchi"]

        # badge
        if plan.badge_rows:
            gap_x = badge_gap
            gap_y = badge_gap_y
            for row_index, row in enumerate(plan.badge_rows):
                row_width = sum(badge_widths[label] for label in row) + gap_x * (len(row) - 1)
                x = content.left() + max(0.0, (cw - row_width) / 2.0)
                row_y = y + row_index * (plan.badge_h + gap_y)
                for label in row:
                    label.setGeometry(
                        int(round(x)), int(round(row_y)), badge_widths[label], plan.badge_h
                    )
                    x += badge_widths[label] + gap_x
            y += plan.badges_h
            if self._hours_visible:
                y += plan.gaps["after_badges"]

        # giờ hoàng đạo
        if self._hours_visible:
            caption_y = y
            if plan.show_caption:
                self._hours_caption.setVisible(True)
                self._hours_caption.setGeometry(
                    int(content.left()), int(round(caption_y)), int(cw), h_caption
                )
                caption_y += h_caption + px(4, e)
            else:
                # phương án nén: bỏ caption để nhường chỗ cho ca dao 3 dòng
                self._hours_caption.setVisible(False)
            chip_gap_x = px(5, e)
            for row_index, row in enumerate(plan.chip_rows):
                row_width = plan.chip_w * len(row) + chip_gap_x * (len(row) - 1)
                x = content.left() + max(0.0, (cw - row_width) / 2.0)
                row_y = caption_y + row_index * (h_chip + chip_gap)
                for chip in row:
                    chip.setGeometry(
                        int(round(x)), int(round(row_y)), plan.chip_w, h_chip
                    )
                    x += plan.chip_w + chip_gap_x

        # đáy: dòng kẻ + ca dao + nguồn (neo đáy)
        bottom = content.bottom()
        end_pad = max(3, px(4, e))
        if self._quote_visible:
            credit_y = bottom - (h_credit if credit_visible else end_pad)
            if credit_visible:
                self._credit.setGeometry(
                    int(content.left()), int(round(credit_y)), int(cw), h_credit
                )
            quote_y = (
                credit_y - (plan.gaps["after_quote"] if credit_visible else 0) - plan.quote_h
            )
            self._quote_label.setGeometry(
                int(content.left()), int(round(quote_y)), int(cw), plan.quote_h
            )
            div2_y = quote_y - plan.gaps["after_div2"] - h_div
            self._place_divider(self._div2, content.left(), div2_y, cw, h_div, h_ornament)
            self._div2.setVisible(True)
        else:
            self._quote_label.setGeometry(
                int(content.left()), int(round(bottom)), int(cw), 0
            )
            self._div2.setVisible(False)

        # --- trạng thái hiển thị của khối đầu (chỉ hiện khi có dữ liệu) ---
        has_info = self._info is not None
        for widget in (
            self._weekday,
            self._day,
            self._month,
            self._div1,
            self._lunar_caption,
            self._lunar_pill,
            self._lunar_month,
            self._lunar_year,
            self._canchi,
        ):
            widget.setVisible(has_info)
        self._quote_label.setVisible(self._quote_visible)
        self._credit.setVisible(credit_visible)

    def _place_divider(
        self,
        divider: _DividerRow,
        x: float,
        y: float,
        width: float,
        height: int,
        ornament: int,
    ) -> None:
        divider.setGeometry(int(round(x)), int(round(y)), int(width), height)
        divider.configure(
            spacing=max(4, px(9, self._eff)),
            ornament_size=ornament,
            color=_with_alpha(qcolor(self._theme.accent_2), 0.92),
        )

    def _fit_day_font(self, text: str, avail_w: float, avail_h: int) -> int:
        """Chọn cỡ số ngày lớn nhất vừa cả bề rộng lẫn chiều cao khu vực."""
        text = text or ""
        if not text:
            return px(120, self._eff)
        e = self._eff
        base = px(158, e)
        font = _make_day_font(self._display_family, base)
        metrics = QFontMetricsF(font)
        advance = metrics.horizontalAdvance(text)
        tight_h = metrics.tightBoundingRect(text).height()
        size = float(base)
        if advance > 0:
            size = min(size, base * (avail_w * 0.985) / advance)
        if tight_h > 0:
            size = min(size, base * max(0.4, (avail_h - px(10, e)) / tight_h))
        size = max(float(px(44, e)), min(size, float(px(214, e))))
        return max(8, int(round(size)))

    def _fit_label_font(
        self,
        text: str,
        family: str,
        base_px: int,
        max_width: float,
        min_px: int,
        weight: QFont.Weight,
    ) -> QFont:
        """Thu nhỏ cỡ chữ của một nhãn cho vừa bề rộng (nếu cần)."""
        font = QFont(family)
        font.setPixelSize(max(6, base_px))
        font.setWeight(weight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text)
        if width <= max_width or width <= 0:
            return font
        ratio = max_width / width
        font.setPixelSize(max(min_px, int(round(base_px * ratio))))
        return font

    def _fit_text_size(
        self,
        text: str,
        family: str,
        weight: QFont.Weight,
        base_px: int,
        max_width: float,
    ) -> int:
        """Cỡ chữ lớn nhất (≤ ``base_px``) để ``text`` vừa ``max_width``."""
        size = max(8, int(base_px))
        if not text or max_width <= 1:
            return size
        font = QFont(family)
        font.setPixelSize(size)
        font.setWeight(weight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        width = QFontMetricsF(font).horizontalAdvance(text)
        if width > max_width > 0:
            size = max(8, int(size * max_width / width))
        return size

    # ------------------------------------------------------------------
    # Sự kiện
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802 - API Qt
        super().resizeEvent(event)
        self._bg_layer = None  # nền giấy phải dựng lại theo kích thước mới
        self._relayout()

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        if self.width() < 12 or self.height() < 12:
            return
        self._eff = self._compute_eff(self.width(), self.height())
        t = self._theme
        painter = QPainter(self)
        paper_alpha = alpha_of(t.paper)
        if paper_alpha < 0.999:
            # Chỉ NỀN trong đi. Mặt giấy được dựng ở một lớp ảnh riêng (đục
            # hoàn toàn) rồi vẽ lại với độ mờ ⇒ các lớp vân giấy/ánh sáng không
            # cộng dồn làm nền mất trong suốt. Chữ/chip là widget con nên luôn
            # đục 100 % (yêu cầu "khoá opacity của chữ").
            painter.setOpacity(paper_alpha)
            painter.drawPixmap(0, 0, self._background_layer())
            painter.end()
            return
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self._paint_background(painter)
        painter.end()

    def _background_layer(self) -> "QPixmap":  # noqa: F821 - import trễ
        """Ảnh nền giấy đục hoàn toàn, dùng lại giữa các lần vẽ."""
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
        """Bản sao theme với màu giấy **đục hoàn toàn** (alpha do lớp ngoài lo)."""

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
        """Vẽ toàn bộ nền giấy (bóng, mép, gradient, vân, gáy, viền)."""
        t = self._theme
        embedded = self._is_embedded()
        paper = self._paper_rect()
        radius = self._paper_radius()
        path = QPainterPath()
        path.addRoundedRect(paper, radius, radius)

        if not embedded:
            # chạy độc lập: tự vẽ bóng đổ + mép giấy xếp lớp
            self._paint_shadow(painter, paper, radius)
            self._paint_paper_edges(painter, paper, radius)

        # ---- mặt giấy chính ----
        gradient = QLinearGradient(
            paper.left(), paper.top(), paper.left(), paper.bottom()
        )
        paper_col = qcolor(t.paper)
        paper2_col = qcolor(t.paper_2)
        gradient.setColorAt(0.0, paper_col)
        gradient.setColorAt(0.58, _mix(paper_col, paper2_col, 0.45))
        gradient.setColorAt(1.0, paper2_col)
        painter.fillPath(path, QBrush(gradient))

        # ---- vân giấy + ánh sáng + vignette (clip theo bo góc) ----
        painter.save()
        painter.setClipPath(path)
        self._paint_light_and_grain(painter, paper)
        if embedded:
            # shell đã lo bóng ngoài: gợi "chân tập giấy" mảnh ngay trong đáy
            self._paint_inner_page_stack(painter, paper, radius)
        painter.restore()

        # ---- dải gáy + lỗ đục ----
        self._paint_spine(painter, paper, radius)

        # ---- viền mảnh ----
        pen = QPen(qcolor(t.line))
        pen.setWidthF(max(0.8, px(1, self._eff) * 0.85))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    # ------------------------------------------------------------------
    # Vẽ nền giấy
    # ------------------------------------------------------------------

    def _paint_shadow(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        """Bóng đổ mềm vẽ tay (không dùng QGraphicsDropShadowEffect)."""
        e = self._eff
        shadow = qcolor(self._theme.shadow)
        base_alpha = max(0.10, shadow.alphaF())
        painter.setPen(Qt.PenStyle.NoPen)
        # "blur" bằng nhiều lớp bo góc lan rộng dần, nhạt dần ra ngoài
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
        # đường bóng mảnh bám ngay dưới mép giấy
        pen = QPen(_with_alpha(shadow, min(0.55, base_alpha * 1.15)))
        pen.setWidthF(max(1.0, 1.5 * e))
        painter.setPen(pen)
        painter.drawLine(
            QPointF(paper.left() + radius * 0.6, paper.bottom() + px(1.0, e)),
            QPointF(paper.right() - radius * 0.6, paper.bottom() + px(1.0, e)),
        )
        painter.setPen(Qt.PenStyle.NoPen)

    def _paint_paper_edges(self, painter: QPainter, paper: QRectF, radius: float) -> None:
        """2–3 mép giấy xếp lớp phía dưới – gợi cảm giác tập lịch dày."""
        e = self._eff
        t = self._theme
        dark = t.dark
        # (inset ngang, lệch dọc, độ tối) – lớp xa nhất vẽ trước
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
            # bo góc gần bằng tờ chính để không hở "khe" tối ở 2 góc dưới
            corner = max(2.0, radius - inset * 0.22)
            path.addRoundedRect(rect, corner, corner)
            painter.fillPath(path, QBrush(gradient))
            pen = QPen(_with_alpha(_mix(edge, shadow, 0.30), 0.75))
            pen.setWidthF(max(0.7, 0.75 * e))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _paint_inner_page_stack(
        self, painter: QPainter, paper: QRectF, radius: float
    ) -> None:
        """Gợi ý "chân tập giấy" ở đáy card khi shell đã lo bóng đổ bên ngoài."""
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
        # hai đường chỉ mép tập giấy
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
        """Ánh sáng mềm + thớ giấy (loang, chấm li ti, sợi ngang) tất định."""
        e = self._eff
        t = self._theme
        # ánh sáng chéo nhẹ phía trên trái
        light = QRadialGradient(
            QPointF(paper.left() + paper.width() * 0.26, paper.top() + paper.height() * 0.16),
            max(24.0, paper.width() * 0.95),
        )
        sheen = _with_alpha(qcolor(t.paper).lighter(112), 0.55)
        light.setColorAt(0.0, sheen)
        light.setColorAt(0.55, _with_alpha(sheen, 0.12))
        light.setColorAt(1.0, _with_alpha(sheen, 0.0))
        painter.fillRect(paper, QBrush(light))
        # vignette đáy – nơi các trang xếp lớp, giấy hơi tối đi
        vign = QLinearGradient(
            paper.left(), paper.bottom() - paper.height() * 0.30, paper.left(), paper.bottom()
        )
        vign.setColorAt(0.0, _with_alpha(qcolor(t.shadow), 0.0))
        vign.setColorAt(1.0, _with_alpha(qcolor(t.shadow), 0.11))
        painter.fillRect(paper, QBrush(vign))

        # ---- thớ giấy (tất định theo theme + kích thước) ----
        ink = qcolor(t.ink)
        edge = qcolor(t.paper_edge)
        # seed ổn định giữa các lần chạy (hash() của str có salt ngẫu nhiên)
        seed = (
            sum(ord(char) for char in t.name) * 131
            + int(paper.width()) * 17
            + int(paper.height()) * 31
        ) & 0x7FFFFFFF
        rng = random.Random(seed)
        # hạt/thớ giấy không phóng to theo tỉ lệ khung (khung rất lớn vẫn phải
        # giữ được cảm giác giấy mịn, không thành "đốm bẩn")
        grain_e = min(e, 1.5)
        painter.setPen(Qt.PenStyle.NoPen)
        # mảng loang rất nhẹ – giấy dạng "handmade" (giữ trong lòng tờ, tránh mép)
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
        # chấm li ti
        count = max(260, int(paper.width() * paper.height() / 420))
        for _ in range(count):
            x = rng.uniform(paper.left(), paper.right())
            y = rng.uniform(paper.top(), paper.bottom())
            r = rng.uniform(0.35, 1.25) * grain_e
            painter.setBrush(_with_alpha(ink, rng.uniform(0.020, 0.058)))
            painter.drawEllipse(QPointF(x, y), r, r)
        # sợi giấy ngang
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
        """Dải gáy trên cùng với các lỗ đục như bloc thật."""
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

        # gáy dày đổ bóng mềm xuống mặt giấy
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

        # đường chỉ chân dải gáy
        pen = QPen(_with_alpha(_mix(qcolor(t.line), qcolor(t.ink_soft), 0.35), 0.95))
        pen.setWidthF(max(0.7, 0.8 * e))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(paper.left(), paper.top() + band_h),
            QPointF(paper.right(), paper.top() + band_h),
        )

        # lỗ đục
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
            # gờ giấy dày quanh lỗ
            painter.setPen(QPen(_with_alpha(rim, 0.88), max(0.7, 0.8 * e)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                QPointF(cx, cy), hole_r + max(1.0, 1.1 * e), hole_r + max(1.0, 1.1 * e)
            )
            # lòng lỗ
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hole_fill)
            painter.drawEllipse(QPointF(cx, cy), hole_r, hole_r)
            # ánh sáng ở đáy lỗ (bắt sáng trên bề dày giấy)
            painter.setPen(QPen(_with_alpha(light, 0.85), max(0.8, hole_r * 0.55)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(
                QRectF(cx - hole_r, cy - hole_r, hole_r * 2, hole_r * 2),
                195 * 16,
                150 * 16,
            )
        painter.restore()


def _wrap_widths(
    widgets: list[QLabel],
    widths: dict[QLabel, int],
    max_width: float,
    gap: int,
) -> list[list[QLabel]]:
    """Chia các nhãn thành dòng sao cho tổng bề rộng không vượt ``max_width``."""
    rows: list[list[QLabel]] = []
    row: list[QLabel] = []
    row_width = 0.0
    for widget in widgets:
        width = float(widths.get(widget, 0))
        extra = width if not row else width + gap
        if row and row_width + extra > max_width:
            rows.append(row)
            row = [widget]
            row_width = width
        else:
            row.append(widget)
            row_width += extra
    if row:
        rows.append(row)
    return rows
