"""Sinh QSS (Qt Style Sheet) từ bảng màu :class:`~qtcalendar.core.theme.Theme`.

Mọi màu sắc/kích thước phải lấy từ ``Theme`` và ``scale`` – **không hard-code**
màu trong các file view.

Hợp đồng API
------------

``px(value: float, scale: float = 1.0) -> int``
    Quy đổi một số "design pixel" sang pixel thật theo hệ số ``scale``.

``build_stylesheet(theme: Theme, scale: float = 1.0) -> str``
    QSS cho toàn bộ ứng dụng (cửa sổ widget, khung giấy, nhãn chữ, chip giờ
    hoàng đạo, lưới tháng, hộp thoại cài đặt, menu khay hệ thống).

    Các selector được hai view dùng (phải có trong QSS):

    ==============================  ==================================
    Selector                        Dùng cho
    ==============================  ==================================
    ``QWidget#BlocRoot``            nền khung bloc
    ``QLabel#WeekdayLabel``         dòng "THỨ HAI"
    ``QLabel#SolarDayLabel``        số ngày dương cực lớn
    ``QLabel#SolarMonthLabel``      "THÁNG 10 · 2026"
    ``QLabel#LunarCaptionLabel``    caption "ÂM LỊCH" của khối âm lịch
    ``QLabel#LunarMonthLabel``      "tháng Chín (nhuận)" trong khối âm lịch
    ``QLabel#LunarYearLabel``       "năm Bính Ngọ" trong khối âm lịch
    ``QWidget#LunarPill``           viên thuốc chứa số ngày âm cỡ lớn
    ``QLabel#LunarLabel``           dòng âm lịch (dùng cho lịch tháng)
    ``QLabel#CanChiLabel``          dòng Can Chi
    ``QLabel#QuoteLabel``           ca dao cuối bloc
    ``QLabel#CreditLabel``          nguồn ca dao
    ``QLabel#ChipLabel``            chip giờ hoàng đạo
    ``QLabel#TietKhiLabel``         nhãn tiết khí
    ``QLabel#HolidayLabel``         nhãn ngày lễ (màu accent)
    ``QFrame#Divider``              đường kẻ ngăn
    ``QWidget#MonthRoot``           nền lịch tháng
    ``QLabel#MonthTitleLabel``      tiêu đề tháng
    ``QLabel#MonthSubtitleLabel``   dòng âm lịch dưới tiêu đề
    ``QPushButton#NavButton``       nút ‹ ›
    ``QPushButton#ViewSwitch``      nút chuyển chế độ xem
    ``QWidget#DayCell``             ô ngày trong lưới tháng
    ``QLabel#CellSolarLabel``       số dương trong ô
    ``QLabel#CellLunarLabel``       số âm trong ô
    ``QDialog`` / ``QComboBox`` / ``QSlider`` / ``QCheckBox`` …
    ==============================  ==================================

    Ghi chú thiết kế: các selector **của lịch bloc** chỉ đặt màu / nền / viền;
    phần typography (font, cỡ chữ, giãn chữ) do ``BlocView`` tự tính để có thể
    auto-fit số ngày và tự thu nhỏ dòng Can Chi/trích dẫn theo bề rộng thật.
    Nhờ vậy QSS không bao giờ ghi đè font động khi widget được polish lại.

``build_dialog_stylesheet(theme: Theme, scale: float = 1.0) -> str``
    Phần QSS riêng cho hộp thoại cài đặt (nếu muốn tách).

``qcolor(spec: str) -> QColor``
    Tiện ích đổi chuỗi màu của ``Theme`` (``"#RRGGBB"`` hoặc ``"rgba(r, g, b, a)"``)
    thành ``QColor`` cho các view tự vẽ bằng ``QPainter``.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from ..core.theme import Theme, rgba

__all__ = [
    "px",
    "build_stylesheet",
    "build_dialog_stylesheet",
    "qcolor",
    "blend",
]


def px(value: float, scale: float = 1.0) -> int:
    """Quy đổi design-pixel sang pixel thật."""
    return max(1, int(round(value * scale)))


def qcolor(spec: str) -> QColor:
    """Đổi chuỗi màu của ``Theme`` thành ``QColor``.

    Hỗ trợ ``"#RRGGBB"``, ``"#AARRGGBB"`` và ``"rgba(r, g, b, a)"`` (định dạng
    do :func:`qtcalendar.core.theme.rgba` sinh ra).
    """
    text = (spec or "").strip()
    if text.startswith("rgba(") and text.endswith(")"):
        body = text[5:-1].replace(" ", "")
        try:
            parts = body.split(",")
            if len(parts) == 4:
                r, g, b = (int(parts[i]) for i in range(3))
                a = float(parts[3])
                color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
                color.setAlphaF(max(0.0, min(1.0, a)))
                return color
        except (ValueError, IndexError):
            pass
    return QColor(text)


def blend(color_a: str, color_b: str, t: float) -> str:
    """Trộn hai màu của ``Theme`` thành chuỗi ``"#RRGGBB"`` (cho QSS)."""
    a = qcolor(color_a)
    b = qcolor(color_b)
    t = max(0.0, min(1.0, t))
    r = int(round(a.red() * (1 - t) + b.red() * t))
    g = int(round(a.green() * (1 - t) + b.green() * t))
    blue = int(round(a.blue() * (1 - t) + b.blue() * t))
    return f"#{r:02X}{g:02X}{blue:02X}"


# ---------------------------------------------------------------------------
# Các mảnh QSS
# ---------------------------------------------------------------------------


def _base_qss(theme: Theme, scale: float) -> str:
    """Quy tắc chung: chữ, tooltip, hộp thoại, nhãn mặc định."""
    t = theme
    return f"""
/* ===== nền tảng chung ===== */
QWidget {{
    color: {t.ink};
}}
QDialog {{
    background-color: {t.paper};
    color: {t.ink};
    font-family: "{t.font_ui}";
    font-size: {px(12, scale)}px;
}}
QDialog QLabel {{
    color: {t.ink};
    background: transparent;
    font-size: {px(12, scale)}px;
}}
QMessageBox {{
    background-color: {t.paper};
}}
QToolTip {{
    background-color: {t.paper_2};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(6, scale)}px;
    padding: {px(4, scale)}px {px(7, scale)}px;
    font-size: {px(11, scale)}px;
}}
"""


def _bloc_qss(theme: Theme, scale: float) -> str:
    """Da của tờ lịch bloc (typography do BlocView đặt trong code)."""
    t = theme
    return f"""
/* ===== lịch bloc: da và màu ===== */
QWidget#BlocRoot {{
    background: transparent;
}}
QLabel#WeekdayLabel {{
    color: {t.accent};
    background: transparent;
}}
QLabel#SolarDayLabel {{
    color: {t.ink};
    background: transparent;
}}
QLabel#SolarMonthLabel {{
    color: {t.ink_soft};
    background: transparent;
}}
QLabel#LunarLabel {{
    color: {t.ink};
    background: transparent;
}}
QLabel#LunarCaptionLabel {{
    color: {t.ink_faint};
    background: transparent;
}}
QLabel#LunarMonthLabel {{
    color: {t.ink};
    background: transparent;
}}
QLabel#LunarYearLabel {{
    color: {t.ink_soft};
    background: transparent;
}}
QWidget#LunarPill {{
    background: transparent;
}}
QLabel#CanChiLabel {{
    color: {t.ink_soft};
    background: transparent;
}}
QLabel#QuoteLabel {{
    color: {t.quote_ink};
    background: transparent;
}}
QLabel#QuoteLabel:hover {{
    color: {t.accent};
}}
QLabel#CreditLabel {{
    color: {t.ink_faint};
    background: transparent;
}}
QLabel#SectionCaption {{
    color: {t.ink_faint};
    background: transparent;
}}
QLabel#ChipLabel {{
    background-color: {t.chip_bg};
    color: {t.chip_ink};
    border: 1px solid {rgba(t.line, 0.85)};
    border-radius: {px(t.radius * 0.52, scale)}px;
}}
QLabel#ChipLabel:hover {{
    background-color: {t.hover_bg};
    color: {t.ink};
}}
QLabel#TietKhiLabel {{
    background-color: {t.chip_bg};
    color: {t.chip_ink};
    border: 1px solid {t.line};
    border-radius: {px(t.radius * 0.62, scale)}px;
}}
QLabel#HolidayLabel {{
    background-color: {t.accent};
    color: {t.accent_ink};
    border: 1px solid {t.accent};
    border-radius: {px(t.radius * 0.62, scale)}px;
}}
QLabel#AuspiciousDayLabel {{
    background-color: transparent;
    color: {t.ink_soft};
    border: 1px solid {rgba(t.accent_2, 0.80)};
    border-radius: {px(t.radius * 0.62, scale)}px;
}}
/* Bố cục chân lịch 3 cột truyền thống */
QLabel#Col1MonthEn {{
    color: {t.accent};
    background: transparent;
}}
QLabel#Col1MonthVn {{
    color: {t.ink};
    background: transparent;
}}
QLabel#Col1Zodiac {{
    color: {t.accent_2};
    background: transparent;
}}
QLabel#Col1HoursTitle {{
    color: {t.ink_faint};
    background: transparent;
}}
QLabel#Col1Hours {{
    color: {t.ink_soft};
    background: transparent;
}}
QLabel#Col1Footer {{
    color: {t.ink_faint};
    background: transparent;
}}
QLabel#Col2Weekday {{
    color: {t.accent};
    background: transparent;
}}
QLabel#Col2WeekdayEn {{
    color: {t.ink_soft};
    background: transparent;
}}
QLabel#Col3LunarMonth {{
    color: {t.accent};
    background: transparent;
}}
QLabel#Col3CanChi {{
    color: {t.ink};
    background: transparent;
}}
QLabel#Col3TietKhi {{
    color: {t.accent_2};
    background: transparent;
}}
QFrame#Divider {{
    background: transparent;
    border: none;
    border-top: {px(1, scale)}px dashed {blend(t.line, t.ink_soft, 0.42)};
}}
QWidget#DividerOrnament {{
    background: transparent;
}}
"""


def _month_qss(theme: Theme, scale: float) -> str:
    """Da của lịch tháng 7 cột."""
    t = theme
    return f"""
/* ===== lịch tháng ===== */
QWidget#MonthRoot {{
    background-color: {t.paper};
    border-radius: {px(t.radius, scale)}px;
}}
QLabel#MonthTitleLabel {{
    color: {t.ink};
    background: transparent;
    font-family: "{t.font_ui}";
    font-size: {px(20, scale)}px;
    font-weight: 700;
}}
QLabel#MonthSubtitleLabel {{
    color: {t.ink_soft};
    background: transparent;
    font-family: "{t.font_quote}";
    font-size: {px(11, scale)}px;
    font-style: italic;
}}
QLabel#MonthFooterLabel {{
    color: {t.ink_faint};
    background: transparent;
    font-size: {px(9, scale)}px;
}}
QLabel#WeekHeaderLabel {{
    color: {t.ink_soft};
    background: transparent;
    font-size: {px(10, scale)}px;
    font-weight: 600;
}}
QLabel#WeekHeaderLabel[weekend="true"] {{
    color: {t.weekend_ink};
}}
QPushButton#NavButton {{
    background-color: transparent;
    color: {t.ink_soft};
    border: 1px solid {t.line};
    border-radius: {px(9, scale)}px;
    font-size: {px(15, scale)}px;
    padding: {px(1, scale)}px {px(7, scale)}px;
}}
QPushButton#NavButton:hover {{
    background-color: {t.hover_bg};
    color: {t.accent};
    border-color: {rgba(t.accent, 0.55)};
}}
QPushButton#NavButton:pressed {{
    background-color: {t.chip_bg};
}}
QPushButton#NavButton:disabled {{
    color: {t.ink_faint};
    border-color: {rgba(t.line, 0.6)};
}}
QPushButton#ViewSwitch {{
    background-color: transparent;
    color: {t.ink_soft};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    padding: {px(2, scale)}px {px(9, scale)}px;
    font-size: {px(11, scale)}px;
}}
QPushButton#ViewSwitch:hover {{
    background-color: {t.hover_bg};
    color: {t.ink};
}}
QPushButton#ViewSwitch:checked {{
    background-color: {t.accent};
    color: {t.accent_ink};
    border-color: {t.accent};
}}
QWidget#DayCell {{
    background-color: transparent;
    border-radius: {px(8, scale)}px;
}}
QWidget#DayCell:hover {{
    background-color: {t.hover_bg};
}}
QWidget#DayCell[today="true"] {{
    background-color: {t.today_bg};
}}
QWidget#DayCell[selected="true"] {{
    background-color: {t.chip_bg};
}}
QWidget#DayCell[otherMonth="true"] {{
    background-color: transparent;
}}
QLabel#CellSolarLabel {{
    color: {t.ink};
    background: transparent;
    font-size: {px(13, scale)}px;
    font-weight: 600;
}}
QLabel#CellLunarLabel {{
    color: {t.ink_soft};
    background: transparent;
    font-size: {px(9, scale)}px;
}}
QWidget#DayCell[otherMonth="true"] QLabel#CellSolarLabel {{
    color: {t.ink_faint};
}}
QWidget#DayCell[otherMonth="true"] QLabel#CellLunarLabel {{
    color: {rgba(t.ink_faint, 0.75)};
}}
QWidget#DayCell[today="true"] QLabel#CellSolarLabel {{
    color: {t.today_ink};
}}
QWidget#DayCell[today="true"] QLabel#CellLunarLabel {{
    color: {rgba(t.today_ink, 0.82)};
}}
"""


def _dialog_qss(theme: Theme, scale: float) -> str:
    """Da của hộp thoại cài đặt: nút, combo, slider, checkbox, khung nhóm."""
    t = theme
    return f"""
/* ===== hộp thoại cài đặt ===== */
QDialog QGroupBox {{
    background-color: {rgba(t.paper_2, 0.55)};
    border: 1px solid {t.line};
    border-radius: {px(10, scale)}px;
    margin-top: {px(14, scale)}px;
    padding: {px(10, scale)}px {px(10, scale)}px {px(8, scale)}px {px(10, scale)}px;
    font-size: {px(12, scale)}px;
    font-weight: 600;
}}
QDialog QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {px(10, scale)}px;
    padding: 0 {px(4, scale)}px;
    color: {t.accent};
    background-color: {t.paper};
}}
QDialog QLabel#SectionTitle {{
    color: {t.ink_soft};
    font-size: {px(10, scale)}px;
    font-weight: 700;
}}
QDialog QLabel#HintLabel {{
    color: {t.ink_faint};
    font-size: {px(10, scale)}px;
}}
QDialog QPushButton {{
    background-color: {t.chip_bg};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    padding: {px(6, scale)}px {px(14, scale)}px;
    font-size: {px(12, scale)}px;
    min-height: {px(18, scale)}px;
}}
QDialog QPushButton:hover {{
    background-color: {t.hover_bg};
    border-color: {rgba(t.accent, 0.45)};
}}
QDialog QPushButton:pressed {{
    background-color: {t.paper_2};
}}
QDialog QPushButton:default {{
    background-color: {t.accent};
    color: {t.accent_ink};
    border-color: {t.accent};
    font-weight: 700;
}}
QDialog QPushButton:default:hover {{
    background-color: {rgba(t.accent, 0.88)};
}}
QDialog QPushButton:default:pressed {{
    background-color: {rgba(t.accent, 0.78)};
}}
QDialog QPushButton:disabled {{
    color: {t.ink_faint};
    background-color: {t.paper_2};
    border-color: {rgba(t.line, 0.7)};
}}
QDialog QPushButton#PrimaryButton {{
    background-color: {t.accent};
    color: {t.accent_ink};
    border: 1px solid {t.accent};
    font-weight: 700;
}}
QDialog QPushButton#PrimaryButton:hover {{
    background-color: {rgba(t.accent, 0.88)};
}}
QDialog QPushButton#GhostButton {{
    background-color: transparent;
    color: {t.ink_soft};
    border: 1px solid {t.line};
}}
QDialog QPushButton#GhostButton:hover {{
    background-color: {t.hover_bg};
    color: {t.ink};
}}
QComboBox {{
    background-color: {t.paper_2};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    padding: {px(4, scale)}px {px(8, scale)}px;
    min-height: {px(18, scale)}px;
    font-size: {px(12, scale)}px;
}}
QComboBox:hover {{
    border-color: {rgba(t.accent, 0.50)};
}}
QComboBox:focus {{
    border-color: {t.accent};
}}
QComboBox:disabled {{
    color: {t.ink_faint};
    background-color: {rgba(t.paper_2, 0.6)};
}}
QComboBox::drop-down {{
    border: none;
    width: {px(18, scale)}px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.paper};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    padding: {px(3, scale)}px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_ink};
    outline: none;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {t.paper_2};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    padding: {px(4, scale)}px {px(6, scale)}px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_ink};
    font-size: {px(12, scale)}px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {t.accent};
}}
QSlider::groove:horizontal {{
    height: {px(4, scale)}px;
    background: {t.line};
    border-radius: {px(2, scale)}px;
}}
QSlider::sub-page:horizontal {{
    background: {t.accent};
    border-radius: {px(2, scale)}px;
}}
QSlider::handle:horizontal {{
    width: {px(14, scale)}px;
    height: {px(14, scale)}px;
    margin: -{px(5, scale)}px 0;
    background: {t.paper};
    border: {px(2, scale)}px solid {t.accent};
    border-radius: {px(8, scale)}px;
}}
QSlider::handle:horizontal:hover {{
    background: {t.chip_bg};
    border-color: {t.accent_2};
}}
QSlider::groove:vertical {{
    width: {px(4, scale)}px;
    background: {t.line};
    border-radius: {px(2, scale)}px;
}}
QSlider::handle:vertical {{
    width: {px(14, scale)}px;
    height: {px(14, scale)}px;
    margin: 0 -{px(5, scale)}px;
    background: {t.paper};
    border: {px(2, scale)}px solid {t.accent};
    border-radius: {px(8, scale)}px;
}}
QCheckBox, QRadioButton {{
    color: {t.ink};
    background: transparent;
    font-size: {px(12, scale)}px;
    spacing: {px(8, scale)}px;
}}
QCheckBox::indicator {{
    width: {px(15, scale)}px;
    height: {px(15, scale)}px;
    border: 1px solid {rgba(t.ink_soft, 0.60)};
    border-radius: {px(4, scale)}px;
    background-color: {t.paper};
}}
QRadioButton::indicator {{
    width: {px(15, scale)}px;
    height: {px(15, scale)}px;
    border: 1px solid {rgba(t.ink_soft, 0.60)};
    border-radius: {px(8, scale)}px;
    background-color: {t.paper};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {t.accent};
}}
QCheckBox::indicator:checked {{
    background-color: {t.accent};
    border-color: {t.accent};
}}
QRadioButton::indicator:checked {{
    background-color: {t.accent};
    border: {px(4, scale)}px solid {t.paper};
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {t.ink_faint};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: {px(10, scale)}px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {rgba(t.ink_soft, 0.32)};
    border-radius: {px(5, scale)}px;
    min-height: {px(24, scale)}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {rgba(t.accent, 0.55)};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: {px(10, scale)}px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {rgba(t.ink_soft, 0.32)};
    border-radius: {px(5, scale)}px;
    min-width: {px(24, scale)}px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {t.paper_2};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    outline: none;
    font-size: {px(12, scale)}px;
}}
QListWidget::item, QTreeWidget::item {{
    padding: {px(4, scale)}px {px(5, scale)}px;
    border-radius: {px(5, scale)}px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {t.accent};
    color: {t.accent_ink};
}}
QTabWidget::pane {{
    border: 1px solid {t.line};
    border-radius: {px(8, scale)}px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {t.ink_soft};
    padding: {px(5, scale)}px {px(12, scale)}px;
    border-bottom: {px(2, scale)}px solid transparent;
    font-size: {px(12, scale)}px;
}}
QTabBar::tab:selected {{
    color: {t.accent};
    border-bottom: {px(2, scale)}px solid {t.accent};
}}
QTabBar::tab:hover {{
    color: {t.ink};
}}
"""


def _menu_qss(theme: Theme, scale: float) -> str:
    """Menu chuột phải / menu khay hệ thống."""
    t = theme
    return f"""
/* ===== menu khay hệ thống ===== */
QMenu {{
    background-color: {t.paper};
    color: {t.ink};
    border: 1px solid {t.line};
    border-radius: {px(10, scale)}px;
    padding: {px(4, scale)}px;
    font-family: "{t.font_ui}";
    font-size: {px(12, scale)}px;
}}
QMenu::item {{
    padding: {px(5, scale)}px {px(18, scale)}px {px(5, scale)}px {px(10, scale)}px;
    border-radius: {px(6, scale)}px;
    background: transparent;
}}
QMenu::item:selected {{
    background-color: {t.hover_bg};
    color: {t.ink};
}}
QMenu::item:disabled {{
    color: {t.ink_faint};
}}
QMenu::separator {{
    height: 1px;
    background: {t.line};
    margin: {px(4, scale)}px {px(6, scale)}px;
}}
QMenu::indicator {{
    width: {px(13, scale)}px;
    height: {px(13, scale)}px;
}}
"""


# ---------------------------------------------------------------------------
# API công khai
# ---------------------------------------------------------------------------


def build_stylesheet(theme: Theme, scale: float = 1.0) -> str:
    """Sinh QSS đầy đủ cho giao diện."""
    return "\n".join(
        (
            _base_qss(theme, scale),
            _bloc_qss(theme, scale),
            _month_qss(theme, scale),
            _dialog_qss(theme, scale),
            _menu_qss(theme, scale),
        )
    )


def build_dialog_stylesheet(theme: Theme, scale: float = 1.0) -> str:
    """Sinh QSS riêng cho hộp thoại cài đặt."""
    return "\n".join((_base_qss(theme, scale), _dialog_qss(theme, scale)))
