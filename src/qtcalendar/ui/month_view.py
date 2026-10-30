"""Lịch tháng – lưới 7 cột, hiển thị song song Dương lịch và Âm lịch.

Bố cục
======

::

    ┌───────────────────────────────────────────┐
    │  ‹      Tháng 10 / 2026               ›   │  MonthTitleLabel + NavButton
    │         Tháng Chín · năm Bính Ngọ         │  MonthSubtitleLabel
    │  T2   T3   T4   T5   T6   T7   CN         │  header (CN màu accent)
    │ ┌────┬────┬────┬────┬────┬────┬────┐      │
    │ │ 28 │ 29 │ 30 │ 1  │ 2  │ 3  │ 4  │      │  DayCell
    │ │ 16 │ 17 │ 18 │ 19 │ 20 │ 21 │ 22 │      │  (dương to, âm nhỏ)
    │ └────┴────┴────┴────┴────┴────┴────┘      │
    │              … 5–6 hàng …                 │
    │  ● Hôm nay: 28/10/2026 · 19/9 Bính Ngọ    │  chú thích chân
    │                              [Hôm nay]    │  TodayButton
    └───────────────────────────────────────────┘

Hợp đồng API
------------

``class MonthView(QWidget)``

``apply_theme(theme: Theme, scale: float = 1.0)``
``set_today(day: datetime.date)``
    Ngày được tô nổi bật (mặc định ``date.today()``).
``set_month(year: int, month: int)``
    Dựng lại lưới cho tháng đó (dùng ``calendar_service.build_month_grid``).
    Lưới dùng đúng số hàng cần thiết (tối thiểu 5, tối đa 6) và luôn co
    giãn vừa khít chiều cao còn lại – tháng 4 tuần được đệm thêm một tuần
    của tháng sau (làm mờ) để không có khoảng trống chết.
``set_scale(scale: float)``
``current_month() -> tuple[int, int]``
``go_today()``  /  ``step_month(delta: int)``
``set_show_lunar(flag: bool)``
    Cho phép ẩn dòng ngày âm.
``set_selected(day: datetime.date | None)`` / ``selected()``
    Ngày đang xem ở lịch bloc phía trên – ô đó được viền nhấn (trừ khi trùng
    hôm nay, vì ô hôm nay đã tô đầy màu).

Tín hiệu:

* ``day_activated(object)`` – phát ``datetime.date`` khi người dùng bấm một ô.
* ``month_changed(int, int)`` – phát ``(năm, tháng)`` sau mỗi lần đổi tháng.
* ``today_requested()`` – nút "hôm nay".

Yêu cầu thẩm mỹ
---------------

* Ô hôm nay: nền tròn/chữ nhật bo góc ``theme.today_bg``, chữ ``theme.today_ink``.
* Chủ nhật dùng ``theme.weekend_ink``; ngày của tháng khác dùng
  ``theme.ink_faint``; ngày rằm/mùng 1 có thể đậm hơn.
* Ô ngày nên là widget con tự vẽ (``paintEvent``) để nhẹ RAM, **không** dùng
  ``QGraphicsEffect``.
* Nhãn âm lịch luôn gọn, không bao giờ bị cắt: mùng 1 là "1" (đậm) + chấm
  nhỏ, rằm là "Rằm" (kèm chấm), các ngày khác chỉ là số.
* Kích thước ô co giãn theo cửa sổ; cỡ chữ theo ``scale``.

Ghi chú triển khai
------------------

* Lưới luôn đủ **6 hàng × 7 cột** (kể cả tháng chỉ cần 4–5 tuần, các ô dư
  được điền ngày tháng kế tiếp và làm mờ). Nhờ vậy bố cục không "giật" mỗi
  lần chuyển tháng – quan trọng với một widget neo trên desktop.
* Toàn bộ nền giấy, ô ngày, dấu hôm nay… được vẽ tay trong ``paintEvent``;
  QSS chỉ dùng cho chữ của header/footer và hai loại nút.
* Module này **không** tạo hiệu ứng đồ hoạ (``QGraphicsEffect``) và tái sử
  dụng 42 ô widget cho mọi tháng để giữ RAM thấp.
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.calendar_service import (
    build_month_grid,
    get_day_info,
    shift_month,
    today as system_today,
    week_header,
)
from ..core.canchi_constants import LUNAR_MONTH_NAMES
from ..core.theme import Theme, alpha_of, get_theme
from ..core.types import DayInfo

__all__ = ["MonthView"]

#: Lưới tối đa 6 hàng × 7 cột; lưới thực tế dùng 5–6 hàng tuỳ tháng.
_WEEK_ROWS = 6
_MIN_WEEK_ROWS = 5
_COLUMNS = 7
_TOTAL_CELLS = _WEEK_ROWS * _COLUMNS

#: Chặn trên cho cỡ chữ header/footer để chữ không tràn khi cửa sổ hẹp.
_TEXT_SCALE_CAP = 1.35
#: Chặn trên cho lề/nút để cửa sổ nhỏ vẫn đủ chỗ cho lưới.
_METRIC_SCALE_CAP = 1.5


def _text_scale(scale: float) -> float:
    """Hệ số cỡ chữ header/footer (đã chặn trên để không tràn bề ngang)."""
    return min(_scale_of(scale), _TEXT_SCALE_CAP)


def _metric_scale(scale: float) -> float:
    """Hệ số lề/nút (đã chặn trên để cửa sổ nhỏ vẫn đủ chỗ)."""
    return min(_scale_of(scale), _METRIC_SCALE_CAP)


# --------------------------------------------------------------------------- #
# Tiện ích nhỏ
# --------------------------------------------------------------------------- #
def _px(value: float, scale: float = 1.0) -> int:
    """Quy đổi design-pixel sang pixel thật theo ``scale``."""
    return max(1, int(round(value * scale)))


def _scale_of(scale: float) -> float:
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return 1.0
    return max(0.75, min(2.0, value))


def _alpha(color: str | QColor, alpha: float) -> QColor:
    """Trả một màu đã chỉnh độ mờ (``0..1``)."""
    qcolor = QColor(color)
    qcolor.setAlphaF(max(0.0, min(1.0, alpha)))
    return qcolor


class _ElidedLabel(QLabel):
    """Nhãn một dòng cho tiêu đề tháng.

    Ghi chú hiệu năng (quan trọng): bản đầu tự rút gọn chữ bằng
    ``QFontMetrics.elidedText`` ngay trong ``setText``. Trên Windows, việc đo
    chữ này kích hoạt DirectWrite nạp **bộ font dự phòng** và tốn thêm
    ~80 MB RAM (đo thực nghiệm: MonthView từ 60 MB tăng lên 138 MB). Vì vậy
    nhãn nay dùng ``QLabel`` thuần, chỉ cắt chữ khi layout không đủ chỗ —
    với bề ngang thật của widget (324 px) mọi chuỗi tiêu đề đều vừa.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text or ""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        super().setText(self._full_text)

    def setText(self, text: str) -> None:  # noqa: N802 - API Qt
        """Đặt văn bản đầy đủ."""
        self._full_text = text or ""
        super().setText(self._full_text)

    def full_text(self) -> str:
        """Văn bản gốc."""
        return self._full_text


def _month_qss(theme: Theme, scale: float) -> str:
    """QSS dự phòng cho lịch tháng khi ``ui.styles`` chưa sẵn sàng.

    Khi ``ui.styles.build_stylesheet`` đã implement, stylesheet của nó được
    áp **trước** phần này để mọi selector riêng của lịch tháng vẫn đúng ý đồ
    thiết kế (màu lấy cùng một bộ token ``Theme``).
    """
    s = _scale_of(scale)
    sm = _metric_scale(s)
    st = _text_scale(s)
    font = theme.font_ui
    accent = QColor(theme.accent)
    hover_border = accent.lighter(112).name()
    return "\n".join(
        [
            f'QWidget {{ font-family: "{font}"; }}',
            "QWidget#MonthRoot, QWidget#DayCell { background: transparent; }",
            (
                f"QLabel#MonthTitleLabel {{ color: {theme.ink};"
                f" font-size: {_px(19, st)}px; font-weight: bold;"
                " background: transparent; padding: 0px; border: none; }"
            ),
            (
                f"QLabel#MonthSubtitleLabel {{ color: {theme.ink_soft};"
                f" font-size: {_px(10.5, st)}px;"
                " background: transparent; padding: 0px; border: none; }"
            ),
            (
                f"QLabel#WeekdayHeaderLabel {{ color: {theme.ink_soft};"
                f" font-size: {_px(10.5, st)}px; font-weight: bold;"
                " background: transparent; padding: 0px; border: none; }"
            ),
            (
                f"QLabel#WeekdayHeaderSundayLabel {{ color: {theme.accent};"
                f" font-size: {_px(10.5, st)}px; font-weight: bold;"
                " background: transparent; padding: 0px; border: none; }"
            ),
            (
                f"QLabel#WeekdayHeaderSaturdayLabel {{ color: {theme.accent_2};"
                f" font-size: {_px(10.5, st)}px; font-weight: bold;"
                " background: transparent; padding: 0px; border: none; }"
            ),
            (
                f"QLabel#FooterDotLabel {{ color: {theme.accent};"
                f" font-size: {_px(8.5, st)}px; background: transparent;"
                " padding: 0px; border: none; }"
            ),
            (
                f"QLabel#FooterInfoLabel {{ color: {theme.ink_soft};"
                f" font-size: {_px(10, st)}px; background: transparent;"
                " padding: 0px; border: none; }"
            ),
            (
                f"QPushButton#NavButton {{ color: {theme.ink_soft};"
                " background: transparent; border: none;"
                f" border-radius: {_px(9, sm)}px; font-size: {_px(22, sm)}px;"
                " font-weight: bold; padding: 0px; }"
            ),
            (
                f"QPushButton#NavButton:hover {{ color: {theme.accent};"
                f" background: {theme.hover_bg}; }}"
            ),
            f"QPushButton#NavButton:pressed {{ background: {theme.chip_bg}; }}",
            (
                "QPushButton#TodayButton {"
                f" color: {theme.chip_ink}; background: {theme.chip_bg};"
                f" border: 1px solid {theme.line};"
                f" border-radius: {_px(11, sm)}px;"
                f" padding: {_px(3, sm)}px {_px(10, sm)}px;"
                f" font-size: {_px(10, st)}px; font-weight: bold; }}"
            ),
            (
                "QPushButton#TodayButton:hover {"
                f" color: {theme.accent}; background: {theme.hover_bg};"
                f" border-color: {hover_border}; }}"
            ),
            (
                "QPushButton#TodayButton:pressed {"
                f" background: {theme.chip_bg}; }}"
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# Ô ngày
# --------------------------------------------------------------------------- #
class _DayCell(QWidget):
    """Một ô ngày trong lưới tháng – tự vẽ, không dùng widget con."""

    clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DayCell")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._info: DayInfo | None = None
        self._theme: Theme = get_theme(None)
        self._scale = 1.0
        self._today: date | None = None
        self._selected: date | None = None
        self._in_month = True
        self._show_lunar = True
        self._hover = False
        self._index = 0

    # ----- cấu hình -------------------------------------------------------- #
    def configure(
        self,
        info: DayInfo,
        *,
        theme: Theme,
        scale: float,
        today: date | None,
        in_month: bool,
        show_lunar: bool,
        index: int,
        selected: date | None = None,
    ) -> None:
        self._info = info
        self._theme = theme
        self._scale = _scale_of(scale)
        self._today = today
        self._selected = selected
        self._in_month = bool(in_month)
        self._show_lunar = bool(show_lunar)
        self._index = index
        self.setToolTip(self._tooltip_text())
        self.update()

    def restyle(self, *, theme: Theme, scale: float, show_lunar: bool) -> None:
        self._theme = theme
        self._scale = _scale_of(scale)
        self._show_lunar = bool(show_lunar)
        self.update()

    def set_today_ref(self, day: date | None) -> None:
        self._today = day
        self.update()

    def set_selected_ref(self, day: date | None) -> None:
        self._selected = day
        self.update()

    def is_selected(self) -> bool:
        """Ô của ngày đang xem ở bloc (ô hôm nay đã tô đầy nên không tính)."""
        info = self._info
        if info is None or self._selected is None or info.solar != self._selected:
            return False
        return not (self._today is not None and info.solar == self._today)

    # ----- tương tác ------------------------------------------------------- #
    def enterEvent(self, event) -> None:  # noqa: N802 - API Qt
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - API Qt
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - API Qt
        if event.button() == Qt.MouseButton.LeftButton and self._info is not None:
            self.clicked.emit(self._info.solar)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - API Qt
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._info is not None:
                self.clicked.emit(self._info.solar)
            event.accept()
            return
        owner = self.parentWidget()
        if isinstance(owner, MonthView) and owner.handle_cell_key(self, key):
            event.accept()
            return
        super().keyPressEvent(event)

    # ----- vẽ -------------------------------------------------------------- #
    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        info = self._info
        if info is None:
            return
        theme = self._theme
        scale = self._scale

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        cell = QRectF(self.rect())
        inset = max(1.0, round(2.0 * scale))
        box = cell.adjusted(inset, inset, -inset, -inset)
        if box.width() <= 4 or box.height() <= 4:
            return

        radius = max(4.0, min(box.width(), box.height()) * 0.24)
        is_today = self._today is not None and info.solar == self._today

        # --- nền ô ---------------------------------------------------------
        if is_today:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.today_bg))
            painter.drawRoundedRect(box, radius, radius)
        elif self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.hover_bg))
            painter.drawRoundedRect(box, radius, radius)

        if self.is_selected():
            pen = QPen(QColor(theme.accent))
            pen.setWidthF(max(1.2, 1.5 * scale))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(0.75, 0.75, -0.75, -0.75), radius, radius)
        elif self.hasFocus() and not is_today:
            pen = QPen(QColor(theme.accent))
            pen.setWidthF(1.0)
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        # --- màu chữ -------------------------------------------------------
        special_lunar = self._in_month and (info.is_month_start or info.is_full_moon)
        if is_today:
            solar_color = QColor(theme.today_ink)
            lunar_color = _alpha(theme.today_ink, 0.92)
            marker_color = _alpha(theme.today_ink, 0.9)
        elif not self._in_month:
            solar_color = _alpha(theme.ink_faint, 0.95)
            lunar_color = _alpha(theme.ink_faint, 0.72)
            marker_color = _alpha(theme.ink_faint, 0.5)
        else:
            if info.holiday:
                solar_color = QColor(theme.accent)
            elif info.is_sunday:
                solar_color = QColor(theme.weekend_ink)
            elif info.solar.weekday() == 5:  # Thứ Bảy
                solar_color = QColor(theme.accent_2)
            else:
                solar_color = QColor(theme.ink)
            lunar_color = QColor(theme.ink_soft)
            marker_color = QColor(theme.accent)
            if special_lunar:
                lunar_color = QColor(theme.accent)

        # --- cỡ chữ --------------------------------------------------------
        width, height = box.width(), box.height()
        if self._show_lunar:
            solar_px = min(width * 0.44, height * 0.32) * scale
            lunar_px = solar_px * 0.50
        else:
            solar_px = min(width * 0.44, height * 0.42) * scale
            lunar_px = 0.0
        solar_px = max(
            10.0, min(solar_px, height * 0.40, width * 0.46)
        )
        solar_px = float(round(solar_px))
        lunar_px = float(round(max(7.0, min(lunar_px, height * 0.17))))

        font_solar = QFont(theme.font_ui)
        font_solar.setPixelSize(int(solar_px))
        font_solar.setWeight(QFont.Weight.Bold)
        font_lunar = QFont(theme.font_ui)
        font_lunar.setPixelSize(int(lunar_px))
        font_lunar.setWeight(
            QFont.Weight.DemiBold if special_lunar else QFont.Weight.Normal
        )

        fm_lunar = QFontMetricsF(font_lunar)
        lunar_text = ""
        dot_d = 0.0
        dot_gap = 0.0

        # Nhãn âm lịch luôn gọn để không bao giờ bị cắt ở ô nhỏ:
        #   mùng 1 → "1" đậm + chấm nhỏ, rằm → "Rằm" + chấm nhỏ, còn lại → số.
        if self._show_lunar and lunar_px > 0:
            if not self._in_month:
                lunar_text = str(info.lunar.day)
                special_lunar = False
            elif info.is_month_start:
                lunar_text = f"1/{info.lunar.month}"
            elif info.is_full_moon:
                lunar_text = "Rằm"
            else:
                lunar_text = str(info.lunar.day)
            if special_lunar:
                dot_d = max(2.2, round(lunar_px * 0.24))
                dot_gap = max(1.2, round(lunar_px * 0.20))

        # --- bố trí dọc: số dương + số âm ----------------------------------
        solar_band = solar_px * 1.14
        lunar_band = lunar_px * 1.28
        gap = max(1.0, round(lunar_px * 0.16)) if lunar_text else 0.0
        total = solar_band + (gap + lunar_band if lunar_text else 0.0)
        top = box.top() + (height - total) / 2.0

        painter.setFont(font_solar)
        painter.setPen(solar_color)
        solar_rect = QRectF(box.left(), top, width, solar_band)
        solar_text = str(info.solar.day)
        painter.drawText(
            solar_rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            solar_text,
        )

        # Ngày lễ: chấm vàng nhỏ ngay cạnh số dương để không bị lẫn với
        # Chủ nhật (cũng dùng màu accent).
        if info.holiday and self._in_month and not is_today:
            fm_solar = QFontMetricsF(font_solar)
            text_w = fm_solar.horizontalAdvance(solar_text)
            dot_r = max(1.6, min(2.8, width * 0.028))
            gap = max(1.4, width * 0.022)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.accent_2))
            painter.drawEllipse(
                QPointF(
                    box.center().x() + text_w / 2.0 + gap + dot_r,
                    solar_rect.center().y() - solar_band * 0.18,
                ),
                dot_r,
                dot_r,
            )

        if lunar_text:
            painter.setFont(font_lunar)
            painter.setPen(lunar_color)
            lunar_rect = QRectF(
                box.left(), top + solar_band + gap, width, lunar_band
            )
            text_w = fm_lunar.horizontalAdvance(lunar_text)
            if special_lunar and dot_d > 0.0:
                cluster_w = text_w + dot_gap + dot_d
                start_x = box.center().x() - cluster_w / 2.0
                baseline = (
                    lunar_rect.top()
                    + (lunar_rect.height() - fm_lunar.height()) / 2.0
                    + fm_lunar.ascent()
                )
                painter.drawText(QPointF(start_x, baseline), lunar_text)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(marker_color)
                painter.drawEllipse(
                    QPointF(
                        start_x + text_w + dot_gap + dot_d / 2.0,
                        lunar_rect.center().y(),
                    ),
                    dot_d / 2.0,
                    dot_d / 2.0,
                )
            else:
                painter.drawText(
                    lunar_rect,
                    int(
                        Qt.AlignmentFlag.AlignHCenter
                        | Qt.AlignmentFlag.AlignVCenter
                    ),
                    lunar_text,
                )

        # --- chấm vàng đánh dấu ngày lễ ------------------------------------
        # (đã vẽ ngay cạnh số dương ở trên)

        painter.end()

    # ----- tooltip --------------------------------------------------------- #
    def _tooltip_text(self) -> str:
        info = self._info
        if info is None:
            return ""
        lines = [f"{info.weekday_name}, {info.solar:%d/%m/%Y}"]
        if info.holiday:
            lines.append(f"Lễ: {info.holiday}")
        lunar = (
            f"Ngày {info.lunar.day} tháng "
            f"{LUNAR_MONTH_NAMES[info.lunar.month - 1]}{info.lunar.leap_text}"
            f" · năm {info.year_can_chi.text}"
        )
        lines.append(lunar)
        extra = f"Can Chi: {info.day_can_chi.text}"
        if info.tiet_khi:
            extra += f" · Tiết khí: {info.tiet_khi}"
        lines.append(extra)
        if info.is_month_start:
            lines.append("Ngày mùng 1 âm lịch")
        elif info.is_full_moon:
            lines.append("Ngày rằm (15 âm lịch)")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Lịch tháng
# --------------------------------------------------------------------------- #
class MonthView(QWidget):
    """Lưới lịch tháng 7 cột."""

    #: Bấm vào một ô ngày → phát ``datetime.date``.
    day_activated = Signal(object)
    #: Đổi tháng → phát ``(năm, tháng)``.
    month_changed = Signal(int, int)
    #: Bấm nút "về hôm nay".
    today_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonthRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._theme: Theme = get_theme(None)
        self._scale = 1.0
        self._today: date = system_today()
        self._selected: date | None = None
        self._year: int = self._today.year
        self._month: int = self._today.month
        self._show_lunar = True
        self._grid_data = None
        self._cells: list[_DayCell] = []

        self._build_ui()
        self.apply_theme(self._theme, 1.0)
        self.set_month(self._year, self._month)

    # ----- dựng giao diện -------------------------------------------------- #
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._outer = outer

        self._btn_prev = QPushButton("\u2039", self)
        self._btn_prev.setObjectName("NavButton")
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.setToolTip("Tháng trước")
        self._btn_prev.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        self._btn_next = QPushButton("\u203a", self)
        self._btn_next.setObjectName("NavButton")
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.setToolTip("Tháng sau")
        self._btn_next.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        self._title = _ElidedLabel("", self)
        self._title.setObjectName("MonthTitleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitle = _ElidedLabel("", self)
        self._subtitle.setObjectName("MonthSubtitleLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        title_col.addWidget(self._title)
        title_col.addWidget(self._subtitle)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        header.addWidget(self._btn_prev, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addLayout(title_col, 1)
        header.addWidget(self._btn_next, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self._grid = grid

        self._weekday_labels: list[QLabel] = []
        for column, name in enumerate(week_header(0)):
            label = QLabel(name, self)
            if column == _COLUMNS - 1:
                obj_name = "WeekdayHeaderSundayLabel"
            elif column == _COLUMNS - 2:
                obj_name = "WeekdayHeaderSaturdayLabel"
            else:
                obj_name = "WeekdayHeaderLabel"
            label.setObjectName(obj_name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, column)
            self._weekday_labels.append(label)

        for row in range(_WEEK_ROWS):
            for column in range(_COLUMNS):
                cell = _DayCell(self)
                cell.clicked.connect(self._on_cell_clicked)
                grid.addWidget(cell, row + 1, column)
                self._cells.append(cell)
        self._cells = self._cells[:_TOTAL_CELLS]

        for column in range(_COLUMNS):
            grid.setColumnStretch(column, 1)
        for row in range(_WEEK_ROWS):
            grid.setRowStretch(row + 1, 1)
        outer.addLayout(grid, 1)
        self._visible_rows = _MIN_WEEK_ROWS

        self._footer_dot = QLabel("\u25cf", self)
        self._footer_dot.setObjectName("FooterDotLabel")
        self._today_info = QLabel("", self)
        self._today_info.setObjectName("FooterInfoLabel")
        self._today_info.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._today_info.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._btn_today = QPushButton("Hôm nay", self)
        self._btn_today.setObjectName("TodayButton")
        self._btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_today.setToolTip("Về tháng hiện tại")
        self._btn_today.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(0)
        footer.addWidget(self._footer_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._today_info, 1)
        footer.addWidget(self._btn_today, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(footer)
        self._footer_layout = footer

        self._btn_prev.clicked.connect(lambda: self.step_month(-1))
        self._btn_next.clicked.connect(lambda: self.step_month(1))
        self._btn_today.clicked.connect(self._on_today_clicked)

    # ----- theme / scale --------------------------------------------------- #
    def apply_theme(self, theme: Theme, scale: float = 1.0) -> None:
        """Đổi bảng màu và hệ số phóng to nội dung."""
        if theme is None:  # pragma: no cover - phòng thủ
            theme = get_theme(None)
        self._theme = theme
        self._scale = _scale_of(scale)

        self.setStyleSheet(self._build_stylesheet(theme, self._scale))
        self._apply_metrics()

        for cell in self._cells:
            cell.restyle(
                theme=self._theme,
                scale=self._scale,
                show_lunar=self._show_lunar,
            )
        self.update()

    def _build_stylesheet(self, theme: Theme, scale: float) -> str:
        fallback = _month_qss(theme, scale)
        theirs = ""
        try:  # ui.styles do người khác phụ trách – chưa xong thì dùng fallback
            from .styles import build_stylesheet  # noqa: PLC0415

            candidate = build_stylesheet(theme, scale)
            if isinstance(candidate, str) and candidate.strip():
                theirs = candidate
        except Exception:  # pragma: no cover - styles.py đang được hoàn thiện
            theirs = ""
        # QSS của ui.styles áp trước, phần riêng của lịch tháng áp sau để các
        # selector của view này luôn đủ và đúng bố cục.
        return (theirs + "\n" + fallback) if theirs else fallback

    def _apply_metrics(self) -> None:
        scale = self._scale
        sm = _metric_scale(scale)
        st = _text_scale(scale)
        theme = self._theme

        self._outer.setContentsMargins(
            _px(14, sm), _px(11, sm), _px(14, sm), _px(9, sm)
        )
        self._outer.setSpacing(_px(7, sm))

        nav_size = QSize(_px(30, sm), _px(30, sm))
        self._btn_prev.setFixedSize(nav_size)
        self._btn_next.setFixedSize(nav_size)

        nav_font = QFont(theme.font_ui)
        nav_font.setPixelSize(_px(22, st))
        nav_font.setWeight(QFont.Weight.DemiBold)
        self._btn_prev.setFont(nav_font)
        self._btn_next.setFont(nav_font)

        title_font = QFont(theme.font_ui)
        title_font.setPixelSize(_px(19, st))
        title_font.setWeight(QFont.Weight.Bold)
        self._title.setFont(title_font)

        subtitle_font = QFont(theme.font_ui)
        subtitle_font.setPixelSize(_px(10.5, st))
        self._subtitle.setFont(subtitle_font)

        weekday_font = QFont(theme.font_ui)
        weekday_font.setPixelSize(_px(10.5, st))
        weekday_font.setWeight(QFont.Weight.DemiBold)
        weekday_font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing, 0.5 * st
        )
        header_height = _px(21, sm)
        for label in self._weekday_labels:
            label.setFont(weekday_font)
            label.setFixedHeight(header_height)

        footer_font = QFont(theme.font_ui)
        footer_font.setPixelSize(_px(10, st))
        self._today_info.setFont(footer_font)
        dot_font = QFont(theme.font_ui)
        dot_font.setPixelSize(_px(8.5, st))
        self._footer_dot.setFont(dot_font)

        pill_font = QFont(theme.font_ui)
        pill_font.setPixelSize(_px(10, st))
        pill_font.setWeight(QFont.Weight.DemiBold)
        self._btn_today.setFont(pill_font)
        self._btn_today.setMinimumHeight(_px(24, sm))

        # Khoảng cách giữa chấm accent và cặp nút pill ở chân.
        self._footer_layout.setSpacing(_px(6, sm))

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme.paper))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.paper))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.accent_ink))
        self.setPalette(palette)

        self._refresh_footer_text()

    def set_scale(self, scale: float) -> None:
        """Đổi hệ số phóng to nội dung (không đổi tháng đang xem)."""
        self.apply_theme(self._theme, scale)

    # ----- dữ liệu --------------------------------------------------------- #
    def set_today(self, day: date) -> None:
        """Ngày được tô nổi bật trong lưới."""
        if not isinstance(day, date):  # pragma: no cover - phòng thủ
            return
        self._today = day
        for cell in self._cells:
            cell.set_today_ref(day)
        self._refresh_footer_text()
        self.update()

    def set_selected(self, day: date | None) -> None:
        """Đánh dấu ngày đang xem ở lịch bloc (``None`` = không đánh dấu)."""
        self._selected = day if isinstance(day, date) else None
        for cell in self._cells:
            cell.set_selected_ref(self._selected)

    def selected(self) -> date | None:
        return self._selected

    def set_month(self, year: int, month: int) -> None:
        """Dựng lại lưới cho tháng ``month``/``year``.

        Số hàng = số tuần thực tế của tháng (chặn trong khoảng 5–6) nên lưới
        luôn vừa khít chiều cao còn lại: tháng 4 tuần được đệm thêm một tuần
        của tháng sau (làm mờ), tháng 5–6 tuần dùng đúng số hàng của nó.
        """
        year, month = int(year), int(month)
        if not 1 <= month <= 12:
            raise ValueError(f"Tháng không hợp lệ: {month}")
        if not 1 <= year <= 9999:
            raise ValueError(f"Năm không hợp lệ: {year}")

        grid = build_month_grid(year, month)
        self._grid_data = grid
        self._year, self._month = year, month

        rows = max(_MIN_WEEK_ROWS, min(_WEEK_ROWS, len(grid.weeks)))
        days: list[DayInfo] = list(grid.days)
        while len(days) < rows * _COLUMNS:
            days.append(get_day_info(days[-1].solar + timedelta(days=1)))

        self._title.setText(grid.title)
        self._subtitle.setText(self._subtitle_text(grid))

        for index, (cell, info) in enumerate(zip(self._cells, days)):
            cell.configure(
                info,
                theme=self._theme,
                scale=self._scale,
                today=self._today,
                in_month=info.solar.month == month,
                show_lunar=self._show_lunar,
                index=index,
                selected=self._selected,
            )
        self._apply_rows(rows)
        self._refresh_footer_text()
        self.update()

    def _apply_rows(self, rows: int) -> None:
        """Bật/tắt các hàng của lưới theo số tuần thực tế của tháng."""
        rows = max(_MIN_WEEK_ROWS, min(_WEEK_ROWS, int(rows)))
        self._visible_rows = rows
        for row in range(_WEEK_ROWS):
            self._grid.setRowStretch(row + 1, 1 if row < rows else 0)
            for column in range(_COLUMNS):
                self._cells[row * _COLUMNS + column].setVisible(row < rows)

    def set_show_lunar(self, flag: bool) -> None:
        """Ẩn/hiện dòng ngày âm lịch trong các ô."""
        self._show_lunar = bool(flag)
        for cell in self._cells:
            cell.restyle(
                theme=self._theme,
                scale=self._scale,
                show_lunar=self._show_lunar,
            )
        self.update()

    # ----- điều hướng ------------------------------------------------------ #
    def current_month(self) -> tuple[int, int]:
        """Tháng đang hiển thị ``(năm, tháng)``."""
        return (self._year, self._month)

    def visible_rows(self) -> int:
        """Số hàng tuần đang hiển thị (5 hoặc 6) – tiện cho kiểm thử."""
        return int(getattr(self, "_visible_rows", _MIN_WEEK_ROWS))

    def go_today(self) -> None:
        """Về tháng hiện tại và làm mới ngày hôm nay."""
        day = system_today()
        self.set_today(day)
        if (day.year, day.month) != (self._year, self._month):
            self.set_month(day.year, day.month)
            self.month_changed.emit(day.year, day.month)
        else:
            self.update()

    def step_month(self, delta: int) -> None:
        """Chuyển tháng ``delta`` bước (âm = lùi)."""
        year, month = shift_month(self._year, self._month, int(delta))
        self.set_month(year, month)
        self.month_changed.emit(year, month)

    # ----- tín hiệu nội bộ ------------------------------------------------- #
    def _on_cell_clicked(self, solar) -> None:
        if isinstance(solar, date):
            self.day_activated.emit(solar)

    def _on_today_clicked(self) -> None:
        self.go_today()
        self.today_requested.emit()

    def handle_cell_key(self, cell: _DayCell, key: int) -> bool:
        """Điều hướng bằng phím mũi tên giữa các ô ngày."""
        try:
            index = self._cells.index(cell)
        except ValueError:  # pragma: no cover - phòng thủ
            return False
        if key == Qt.Key.Key_Left:
            target = index - 1
        elif key == Qt.Key.Key_Right:
            target = index + 1
        elif key == Qt.Key.Key_Up:
            target = index - _COLUMNS
        elif key == Qt.Key.Key_Down:
            target = index + _COLUMNS
        else:
            return False
        if 0 <= target < len(self._cells):
            self._cells[target].setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    # ----- vẽ nền giấy ----------------------------------------------------- #
    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Chỉ nền trong đi; lưới ngày là widget con nên chữ luôn đục 100 %.
        paper_alpha = alpha_of(theme.paper)
        if paper_alpha < 0.999:
            painter.setOpacity(paper_alpha)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if rect.width() <= 2 or rect.height() <= 2:
            return
        radius = float(max(6, int(theme.radius)))
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(theme.paper))
        gradient.setColorAt(1.0, QColor(theme.paper_2))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(theme.paper_edge), 1.0))
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()

    # ----- kích thước gợi ý ------------------------------------------------ #
    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        return QSize(344, 470)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - API Qt
        # Đủ nhỏ để widget window co còn 260×320 mà không bị Qt nới ngược.
        return QSize(240, 300)

    def resizeEvent(self, event) -> None:  # noqa: N802 - API Qt
        super().resizeEvent(event)
        if hasattr(self, "_today_info"):
            self._refresh_footer_text()

    # ----- chú thích chân -------------------------------------------------- #
    def _footer_texts(self) -> tuple[str, ...]:
        """Các biến thể dòng "hôm nay", dài → ngắn, tuỳ bề ngang còn lại."""
        info = get_day_info(self._today)
        lunar = f"{info.lunar.day}/{info.lunar.month}{info.lunar.leap_text}"
        solar = f"{info.solar:%d/%m/%Y}"
        tail = f"{solar} · {lunar} {info.year_can_chi.text}"
        return (f"Hôm nay: {tail}", tail, solar)

    def _refresh_footer_text(self) -> None:
        """Chọn biến thể chú thích chân vừa bề ngang – không bị cắt chữ."""
        variants = self._footer_texts()
        metrics = self._today_info.fontMetrics()
        spacing = self._footer_layout.spacing()
        used = (
            self._footer_dot.sizeHint().width()
            + self._btn_today.sizeHint().width()
            + 4 * spacing
        )
        margin = _px(14, _metric_scale(self._scale)) * 2
        available = max(0, self.width() - margin - used)
        text = variants[-1]
        for candidate in variants:
            if metrics.horizontalAdvance(candidate) <= available:
                text = candidate
                break
        self._today_info.setText(text)
        self._today_info.setToolTip(variants[0])

    @staticmethod
    def _subtitle_text(grid) -> str:
        """Dòng phụ kiểu "Tháng Chín · năm Bính Ngọ"."""
        anchor: DayInfo | None = None
        fallback: DayInfo | None = None
        for info in grid.days:
            if info.solar.month != grid.month:
                continue
            if fallback is None:
                fallback = info
            if info.is_month_start:
                anchor = info
                break
        chosen = anchor or fallback
        if chosen is None:  # pragma: no cover - không thể xảy ra
            return ""
        name = LUNAR_MONTH_NAMES[chosen.lunar.month - 1]
        leap = " nhuận" if chosen.lunar.leap else ""
        return f"Tháng {name}{leap} · Năm {chosen.year_can_chi.text}"
