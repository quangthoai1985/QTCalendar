"""Hộp thoại cài đặt.

Nội dung (nhóm theo thẻ hoặc theo hàng, gọn trong ~460x560 px)
==============================================================

**Giao diện**
  * Bảng màu: combo 4 theme (``giay_do``, ``xanh_ngoc``, ``hoang_hon``,
    ``dem_sao``) kèm ô vuông xem trước màu.
  * Màu nền giấy: hàng swatch gợi ý từ ``BACKGROUND_PRESETS`` (tooltip tên
    màu, viền accent + dấu ✓ cho mục đang chọn), nút "Màu tuỳ chọn…"
    (``QColorDialog``, không chọn alpha vì alpha do thanh độ trong suốt lo)
    và nút "Theo giao diện" (``bg_color = ""``). Màu nền tối tự chuyển bộ mực
    sáng nhờ ``theme.with_background``.
  * Độ trong suốt: ``QSlider`` 20–100 % + nhãn phần trăm cập nhật trực tiếp.
  * Cỡ nội dung: ``QSlider`` 75–200 %.
  * Chế độ xem: 2 nút chọn "Lịch ngày" / "Lịch tháng".
  * Hiện ca dao / giờ hoàng đạo / tiết khí: 3 checkbox.
  * Nguồn ca dao: combo "Theo ngày" (``daily``) / "Ngẫu nhiên" (``random``).

**Hành vi cửa sổ**
  * Vị trí: combo "Ghim sát Desktop" (``desktop``) / "Cửa sổ nổi" (``floating``).
  * Luôn nổi trên cùng, Khoá vị trí, Khởi động cùng Windows: checkbox.
  * Nút "Đặt lại vị trí".

**Nâng cao**
  * Thuật toán âm lịch: combo "Chính xác cao" (``precise``) / "Hồ Ngọc Đức
    gốc" (``hnd``) – xem tài liệu so sánh; lưu vào ``Settings.lunar_engine``.
  * Nhãn hiển thị đường dẫn tệp ``settings.json`` đang dùng
    (``ConfigStore().path``).

**Nút**: "Đặt lại mặc định" (trái) · "Huỷ" · "Lưu" (mặc định, Enter).

Hợp đồng API
------------

``class SettingsDialog(QDialog)``

``__init__(settings: Settings, parent=None, *, autostart_available: bool = True)``
    Sửa trên **bản sao**; không được ghi đè ``settings`` gốc.

``settings() -> Settings``
    Cấu hình sau khi người dùng đã bấm Lưu.

``@staticmethod edit(settings, parent=None, **kwargs) -> Settings | None``
    Mở hộp thoại; trả ``Settings`` mới nếu Lưu, ``None`` nếu Huỷ.

``set_theme_preview(theme: Theme)`` – áp bảng màu cho chính hộp thoại.

Yêu cầu: mọi thay đổi hiển thị ngay trong hộp thoại (xem trước màu/độ mờ),
không cần chuyển qua lại với widget chính.

Ghi chú triển khai
------------------

* Hộp thoại chia **3 thẻ**: "Giao diện" (nhóm cơ sở), "Cửa sổ" (hành vi
  cửa sổ) và "Nâng cao"; phần "Xem trước" nằm cố định phía trên hàng nút
  nên luôn nhìn thấy dù đang ở thẻ nào.
* Thẻ xem trước mô phỏng đúng tờ lịch bloc: nền "màn hình" phía sau + tờ giấy
  vẽ lại với **màu nền tuỳ chọn** và **độ trong suốt** đang chọn
  (``paper_theme``: alpha chỉ nằm trên nền giấy, chữ vẫn đục 100 %), cập nhật
  ngay khi kéo slider hoặc bấm swatch màu nền.
* Hộp thoại luôn vẽ nền **đục** (alpha của độ mờ được bỏ khi áp QSS cho
  chrome hộp thoại) để bảng cài đặt không bị trong suốt khó đọc; màu nền vẫn
  đổi ngay trên nền hộp thoại.
* Toàn bộ điều khiển đọc/ghi trên ``Settings.copy()``; ``settings`` truyền
  vào không bị thay đổi. QSS lấy từ ``ui.styles`` nếu module đó đã sẵn sàng,
  ngược lại dùng bộ QSS tối giản dựng từ chính các token ``Theme``.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QLinearGradient,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import ConfigStore, Settings, config_path
from ..core.theme import (
    BACKGROUND_PRESETS,
    THEME_ORDER,
    THEMES,
    Theme,
    get_theme,
    is_valid_color,
    paper_theme,
)

__all__ = ["SettingsDialog"]

#: Nhãn hiển thị cho từng giá trị ``Settings.*``.
PLACEMENT_LABELS: tuple[tuple[str, str], ...] = (
    ("desktop", "Ghim sát Desktop"),
    ("floating", "Cửa sổ nổi"),
)
QUOTE_LABELS: tuple[tuple[str, str], ...] = (
    ("daily", "Theo ngày"),
    ("random", "Ngẫu nhiên"),
)
ENGINE_LABELS: tuple[tuple[str, str], ...] = (
    ("precise", "Chính xác cao"),
    ("hnd", "Hồ Ngọc Đức gốc"),
)

_PREVIEW_HEIGHT = 88


# --------------------------------------------------------------------------- #
# Tiện ích
# --------------------------------------------------------------------------- #
def _px(value: float, scale: float = 1.0) -> int:
    return max(1, int(round(value * scale)))


def _blend(color_a: str, color_b: str, ratio: float) -> str:
    """Trộn hai màu hex (``ratio`` 0 → a, 1 → b)."""
    ratio = max(0.0, min(1.0, ratio))
    ca, cb = QColor(color_a), QColor(color_b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * ratio),
        round(ca.green() + (cb.green() - ca.green()) * ratio),
        round(ca.blue() + (cb.blue() - ca.blue()) * ratio),
    ).name()


def _field_bg(theme: Theme) -> str:
    """Màu nền của ô nhập, dịu hơn nền giấy một chút."""
    if theme.is_dark:
        return _blend(theme.paper, theme.paper_2, 0.45)
    return _blend(theme.paper, theme.paper_2, 0.8)


def _solid(color: str) -> str:
    """Bỏ alpha (nếu có) khỏi chuỗi màu ``#AARRGGBB`` → ``#RRGGBB``."""
    text = str(color or "")
    digits = text.lstrip("#")
    if len(digits) == 8:
        return "#" + digits[2:]
    return text


def _opaque_theme(theme: Theme) -> Theme:
    """Theme nền đục để vẽ chrome hộp thoại (không cho cửa sổ bị trong suốt)."""
    return replace(
        theme,
        paper=_solid(theme.paper),
        paper_2=_solid(theme.paper_2),
        paper_edge=_solid(theme.paper_edge),
    )


def _fade(color: str, factor: float) -> QColor:
    """Nhân thêm alpha cho màu (dùng cho nền giấy có sẵn alpha)."""
    qcolor = QColor(color)
    qcolor.setAlphaF(max(0.0, min(1.0, qcolor.alphaF() * factor)))
    return qcolor


def _normalized_color(color: str) -> str:
    """Chuẩn hoá màu nền: ``""`` hoặc ``#RRGGBB`` viết hoa; màu sai → ``""``."""
    text = str(color or "").strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    if not is_valid_color(text):
        return ""
    return text.upper()


def _theme_icon(theme: Theme, size: int = 18) -> QIcon:
    """Ô vuông màu nhỏ hiển thị trong combo bảng màu."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(0.5, 0.5, size - 1, size - 1)
    painter.setPen(QPen(QColor(theme.paper_edge), 1.0))
    painter.setBrush(QColor(theme.paper))
    painter.drawRoundedRect(rect, 5.0, 5.0)
    inner = rect.adjusted(3.6, 3.6, -3.6, -3.6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(theme.accent))
    painter.drawEllipse(inner)
    painter.end()
    return QIcon(pixmap)


def _config_file_path() -> str:
    """Đường dẫn tệp ``settings.json`` đang dùng (theo :class:`ConfigStore`)."""
    try:
        return str(ConfigStore().path)
    except Exception:  # pragma: no cover - phòng thủ
        try:
            return str(config_path())
        except Exception:
            return "settings.json"


# --------------------------------------------------------------------------- #
# QSS
# --------------------------------------------------------------------------- #
def _dialog_qss(theme: Theme) -> str:
    """QSS dự phòng (và bổ sung) cho hộp thoại cài đặt."""
    font = theme.font_ui
    field_bg = _field_bg(theme)
    hover_bg = theme.hover_bg
    accent = QColor(theme.accent)
    primary_hover = accent.lighter(112).name()
    primary_pressed = accent.darker(112).name()
    border = theme.line

    return "\n".join(
        [
            f'QWidget {{ font-family: "{font}"; }}',
            (
                "QDialog#SettingsDialog {"
                " background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                f" stop:0 {theme.paper}, stop:1 {theme.paper_2}); }}"
            ),
            "QWidget#SettingsPage { background: transparent; }",
            (
                "QDialog#SettingsDialog QLabel { color: "
                f"{theme.ink}; background: transparent; padding: 0px; border: none; }}"
            ),
            (
                f"QLabel#DialogTitleLabel {{ color: {theme.ink};"
                " font-size: 20px; font-weight: bold; }"
            ),
            (
                f"QLabel#DialogSubtitleLabel {{ color: {theme.ink_soft};"
                " font-size: 11px; }"
            ),
            (
                f"QLabel#FieldLabel {{ color: {theme.ink_soft};"
                " font-size: 11px; font-weight: bold; }"
            ),
            (
                f"QLabel#HintLabel {{ color: {theme.ink_faint};"
                " font-size: 9.5px; }"
            ),
            (
                f"QLabel#ValueLabel {{ color: {theme.ink};"
                " font-size: 11px; font-weight: bold; min-width: 42px; }"
            ),
            (
                f"QLabel#PreviewCaption {{ color: {theme.ink_faint};"
                " font-size: 9.5px; font-weight: bold; }"
            ),
            (
                f"QLabel#PreviewMeta {{ color: {theme.ink_faint};"
                " font-size: 9.5px; }"
            ),
            (
                f"QLabel#PathLabel {{ color: {theme.ink_soft};"
                f" font-size: 10px; background: {field_bg};"
                f" border: 1px solid {border}; border-radius: 6px;"
                " padding: 5px 8px; }"
            ),
            (
                "QTabWidget#SettingsTabs::pane {"
                f" border: 1px solid {border}; border-radius: 10px;"
                " background: transparent; top: -1px; }"
            ),
            (
                f"QTabBar::tab {{ color: {theme.ink_soft};"
                " background: transparent; border: none;"
                " padding: 6px 16px; margin-right: 4px;"
                f" border-radius: 8px; font-size: 11px; font-weight: bold; }}"
            ),
            (
                f"QTabBar::tab:selected {{ color: {theme.accent};"
                f" background: {theme.chip_bg}; }}"
            ),
            f"QTabBar::tab:hover:!selected {{ color: {theme.ink}; }}",
            (
                "QComboBox {"
                f" color: {theme.ink}; background: {field_bg};"
                f" border: 1px solid {border}; border-radius: 7px;"
                " padding: 5px 26px 5px 10px; font-size: 11px; min-height: 18px; }"
            ),
            f"QComboBox:hover {{ border-color: {theme.accent}; }}",
            "QComboBox::drop-down { border: none; width: 20px; }",
            "QComboBox::down-arrow { image: none; width: 0px; height: 0px; }",
            (
                "QComboBox QAbstractItemView {"
                f" background: {theme.paper}; color: {theme.ink};"
                f" border: 1px solid {border}; border-radius: 6px;"
                " padding: 4px; selection-background-color: "
                f"{theme.accent}; selection-color: {theme.accent_ink};"
                " outline: 0; }"
            ),
            "QComboBox QAbstractItemView::item { min-height: 22px; padding: 2px 6px; }",
            "QSlider { min-height: 20px; background: transparent; }",
            "QSlider::groove:horizontal { height: 4px; border-radius: 2px; }",
            f"QSlider::groove:horizontal {{ background: {border}; }}",
            (
                "QSlider::sub-page:horizontal {"
                f" background: {theme.accent}; border-radius: 2px; }}"
            ),
            (
                "QSlider::add-page:horizontal {"
                f" background: {border}; border-radius: 2px; }}"
            ),
            (
                "QSlider::handle:horizontal {"
                f" background: {theme.accent}; width: 14px; height: 14px;"
                f" margin: -6px 0; border: 2px solid {theme.paper};"
                " border-radius: 8px; }"
            ),
            f"QSlider::handle:horizontal:hover {{ background: {primary_hover}; }}",
            (
                f"QPushButton#PrimaryButton {{ background: {theme.accent};"
                f" color: {theme.accent_ink}; border: none; border-radius: 8px;"
                " padding: 7px 20px; font-size: 11.5px; font-weight: bold; }"
            ),
            (
                f"QPushButton#PrimaryButton:hover {{ background: {primary_hover}; }}"
            ),
            (
                f"QPushButton#PrimaryButton:pressed {{ background: {primary_pressed}; }}"
            ),
            (
                f"QPushButton#SecondaryButton {{ background: transparent;"
                f" color: {theme.ink}; border: 1px solid {border};"
                " border-radius: 8px; padding: 7px 18px;"
                " font-size: 11.5px; font-weight: bold; }"
            ),
            (
                f"QPushButton#SecondaryButton:hover {{ color: {theme.accent};"
                f" border-color: {theme.accent}; background: {hover_bg}; }}"
            ),
            (
                f"QPushButton#GhostButton {{ background: transparent;"
                f" color: {theme.ink_soft}; border: none; border-radius: 8px;"
                " padding: 7px 12px; font-size: 11px; }"
            ),
            (
                f"QPushButton#GhostButton:hover {{ color: {theme.accent};"
                f" background: {hover_bg}; }}"
            ),
            (
                "QPushButton#GhostButton:pressed {"
                f" background: {theme.chip_bg}; }}"
            ),
            (
                "QPushButton#BgSwatch { background: transparent; border: none;"
                " padding: 0px; min-width: 0px; min-height: 0px; }"
            ),
            (
                f"QLabel#BgStatusLabel {{ color: {theme.ink_faint};"
                " font-size: 9.5px; background: transparent; }"
            ),
            (
                "QPushButton#BgThemeButton, QPushButton#BgPickButton {"
                f" color: {theme.ink_soft}; background: transparent;"
                f" border: 1px solid {border}; border-radius: 6px;"
                " padding: 3px 8px; font-size: 10px; font-weight: bold;"
                " min-height: 0px; }"
            ),
            (
                "QPushButton#BgThemeButton:hover, QPushButton#BgPickButton:hover {"
                f" color: {theme.accent}; border-color: {theme.accent};"
                f" background: {hover_bg}; }}"
            ),
            (
                f"QPushButton#BgThemeButton:checked {{ color: {theme.accent};"
                f" border-color: {theme.accent}; background: {hover_bg}; }}"
            ),
            (
                f"QToolTip {{ background: {theme.chip_bg}; color: {theme.ink};"
                f" border: 1px solid {border}; padding: 4px 7px;"
                " border-radius: 4px; }"
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# Widget phụ trợ
# --------------------------------------------------------------------------- #
class _ComboBox(QComboBox):
    """Combo tự vẽ mũi tên để đồng bộ màu với theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._arrow_color = QColor("#808080")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(28)

    def set_arrow_color(self, color: str | QColor) -> None:
        self._arrow_color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = float(self.width())
        height = float(self.height())
        cx = width - 13.0
        cy = height / 2.0 + 1.0
        size = 4.0
        pen = QPen(
            self._arrow_color,
            1.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.drawLine(
            QPointF(cx - size, cy - size * 0.55),
            QPointF(cx, cy + size * 0.55),
        )
        painter.drawLine(
            QPointF(cx, cy + size * 0.55),
            QPointF(cx + size, cy - size * 0.55),
        )
        painter.end()


class _ThemedCheckBox(QCheckBox):
    """Checkbox tự vẽ ô chọn – giữ được màu theme trên cả 4 bảng màu."""

    _BOX = 17.0

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._theme: Theme = get_theme(None)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        metrics = self.fontMetrics()
        width = int(self._BOX) + 9 + metrics.horizontalAdvance(self.text()) + 4
        height = max(int(self._BOX) + 7, metrics.height() + 6)
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - API Qt
        return self.sizeHint()

    def hitButton(self, pos) -> bool:  # noqa: N802 - API Qt
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        theme = self._theme
        enabled = self.isEnabled()
        checked = self.isChecked()
        hovered = self.underMouse()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        box = self._BOX
        top = (self.height() - box) / 2.0
        rect = QRectF(1.0, top, box, box)
        radius = 5.0

        if checked:
            fill = theme.accent if enabled else theme.ink_faint
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(rect, radius, radius)
            tick = QPen(
                QColor(theme.accent_ink),
                max(1.6, box * 0.11),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(tick)
            painter.drawLine(
                QPointF(rect.left() + box * 0.26, rect.top() + box * 0.52),
                QPointF(rect.left() + box * 0.44, rect.top() + box * 0.70),
            )
            painter.drawLine(
                QPointF(rect.left() + box * 0.44, rect.top() + box * 0.70),
                QPointF(rect.left() + box * 0.76, rect.top() + box * 0.31),
            )
        else:
            border_color = theme.accent if (hovered and enabled) else theme.ink_faint
            painter.setPen(QPen(QColor(border_color), 1.3))
            painter.setBrush(QColor(theme.paper))
            painter.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7), radius, radius)

        if self.hasFocus():
            pen = QPen(QColor(theme.accent), 1.0)
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2.0, -2.0, 2.0, 2.0), 7.0, 7.0)

        painter.setPen(QColor(theme.ink if enabled else theme.ink_faint))
        painter.setFont(self.font())
        text_rect = QRectF(
            rect.right() + 9.0,
            0.0,
            max(0.0, self.width() - rect.right() - 11.0),
            float(self.height()),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )
        painter.end()


class _ColorSwatch(QPushButton):
    """Nút vuông nhỏ chọn nhanh màu nền giấy.

    Mỗi swatch tự vẽ đúng màu của nó; khi được chọn có **viền accent** dày
    2 px và **dấu ✓** màu tương phản (trắng trên nền tối, mực đậm trên nền
    sáng) để luôn thấy rõ trên cả 10 màu gợi ý.
    """

    _SIZE = 22

    def __init__(self, name: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._color = _normalized_color(color)
        self._theme: Theme = get_theme(None)
        self.setObjectName("BgSwatch")
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setToolTip(f"{name} · {self._color}")
        self.setAccessibleName(f"Màu nền {name}")
        self.setProperty("color", self._color)

    def color(self) -> str:
        """Mã màu của swatch (``#RRGGBB`` viết hoa)."""
        return self._color

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.4, 1.4, -1.4, -1.4)
        radius = 5.5
        fill = QColor(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)

        # Viền: accent đậm khi chọn, accent nhẹ khi rê chuột, xám ấm khi thường
        # (đủ đậm để các swatch gần trắng vẫn tách khỏi nền giấy).
        if self.isChecked():
            pen = QPen(QColor(theme.accent), 2.0)
        elif self.underMouse():
            pen = QPen(QColor(theme.accent), 1.4)
        else:
            pen = QPen(QColor(_blend(theme.line, theme.ink_soft, 0.45)), 1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.8, 0.8, -0.8, -0.8), radius, radius)

        if self.isChecked():
            tick_color = (
                QColor("#FFFFFF")
                if fill.lightnessF() < 0.55
                else QColor(theme.ink)
            )
            tick = QPen(
                tick_color,
                1.9,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(tick)
            size = rect.width()
            painter.drawLine(
                QPointF(rect.left() + size * 0.26, rect.top() + size * 0.52),
                QPointF(rect.left() + size * 0.43, rect.top() + size * 0.70),
            )
            painter.drawLine(
                QPointF(rect.left() + size * 0.43, rect.top() + size * 0.70),
                QPointF(rect.left() + size * 0.76, rect.top() + size * 0.31),
            )

        if self.hasFocus():
            focus = QPen(QColor(theme.accent), 1.0)
            focus.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(focus)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(-1.2, -1.2, 1.2, 1.2), radius + 1.0, radius + 1.0
            )
        painter.end()


class _ElidedLabel(QLabel):
    """Nhãn một dòng, tự rút gọn giữa chừng khi hẹp."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setToolTip(text)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        super().setText(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._apply_elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - API Qt
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        metrics = self.fontMetrics()
        width = max(0, self.width() - 20)  # trừ padding QSS
        text = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideMiddle, width
        )
        if text != self.text():
            super().setText(text)


class _PreviewCard(QWidget):
    """Mô phỏng tờ lịch bloc để xem trước theme + độ trong suốt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewCard")
        self.setFixedHeight(_PREVIEW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._theme: Theme = get_theme(None)
        self._opacity = 1.0
        self._scale = 1.0

    def set_preview(self, theme: Theme, opacity: float, scale: float) -> None:
        self._theme = theme
        self._opacity = max(0.2, min(1.0, float(opacity)))
        self._scale = max(0.75, min(1.6, float(scale)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        theme = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if outer.width() <= 20 or outer.height() <= 20:
            return
        radius = 12.0

        # "Màn hình" phía sau để nhìn rõ độ trong suốt.
        backdrop = QLinearGradient(outer.topLeft(), outer.topRight())
        backdrop.setColorAt(0.0, QColor("#77848F"))
        backdrop.setColorAt(0.55, QColor("#59636E"))
        backdrop.setColorAt(1.0, QColor("#3B434D"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(backdrop)
        painter.drawRoundedRect(outer, radius, radius)

        # Tờ giấy: alpha chỉ áp lên **nền giấy** (chữ vẫn đục 100 %) – đúng như
        # cách widget thật vẽ với ``paper_theme``.
        paper_rect = outer.adjusted(11.0, 9.0, -11.0, -9.0)
        paper = QLinearGradient(paper_rect.topLeft(), paper_rect.bottomLeft())
        paper.setColorAt(0.0, _fade(theme.paper, self._opacity))
        paper.setColorAt(1.0, _fade(theme.paper_2, self._opacity))
        painter.setPen(QPen(_fade(theme.paper_edge, self._opacity), 1.0))
        painter.setBrush(paper)
        painter.drawRoundedRect(paper_rect, 9.0, 9.0)

        scale = self._scale
        inner = paper_rect.adjusted(15.0 * scale, 10.0, -15.0, -10.0)
        inner_height = inner.height()

        # Số ngày lớn bên trái.
        number_font = QFont(theme.font_ui)
        number_px = int(min(inner_height * 0.74, 38.0 * scale))
        number_font.setPixelSize(max(16, number_px))
        number_font.setWeight(QFont.Weight.Black)
        metrics = QFontMetricsF(number_font)
        number = "28"
        number_width = metrics.horizontalAdvance(number)
        number_left = inner.left()
        number_baseline = inner.top() + (inner_height + metrics.ascent()) / 2.0 - 2.0
        painter.setFont(number_font)
        painter.setPen(QColor(theme.ink))
        painter.drawText(QPointF(number_left, number_baseline), number)

        # Vách ngăn dọc mảnh.
        divider_x = number_left + number_width + 14.0 * scale
        divider_top = inner.top() + inner_height * 0.16
        divider_bottom = inner.bottom() - inner_height * 0.16
        painter.setPen(QPen(QColor(theme.line), 1.0))
        painter.drawLine(
            QPointF(divider_x, divider_top), QPointF(divider_x, divider_bottom)
        )

        text_left = divider_x + 13.0 * scale
        text_width = max(20.0, inner.right() - text_left)
        weekday_font = QFont(theme.font_ui)
        weekday_font.setPixelSize(max(8, int(9.5 * scale)))
        weekday_font.setWeight(QFont.Weight.Bold)
        weekday_font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing, 0.6 * scale
        )
        solar_font = QFont(theme.font_ui)
        solar_font.setPixelSize(max(10, int(12.5 * scale)))
        solar_font.setWeight(QFont.Weight.DemiBold)
        lunar_font = QFont(theme.font_ui)
        lunar_font.setPixelSize(max(8, int(10.0 * scale)))

        lines = [
            ("THÁNG 10 · 2026", weekday_font, theme.accent),
            ("Thứ Tư, 28/10/2026", solar_font, theme.ink),
            ("Ngày 19 tháng Chín · năm Bính Ngọ", lunar_font, theme.ink_soft),
        ]
        heights = [QFontMetricsF(font).height() for _, font, _ in lines]
        spacing = 3.0 * scale
        total_height = sum(heights) + spacing * (len(lines) - 1)
        y = inner.top() + (inner_height - total_height) / 2.0
        for (text, font, color), line_height in zip(lines, heights):
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(
                QRectF(text_left, y, text_width, line_height),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                text,
            )
            y += line_height + spacing

        painter.end()


# --------------------------------------------------------------------------- #
# Hộp thoại
# --------------------------------------------------------------------------- #
class SettingsDialog(QDialog):
    """Hộp thoại cài đặt của QT Calendar."""

    def __init__(
        self,
        settings: Settings,
        parent: QWidget | None = None,
        *,
        autostart_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Cài đặt – QT Calendar")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)

        #: Bản nháp – hộp thoại không bao giờ sửa trực tiếp ``settings`` gốc.
        self._draft = settings.copy()
        self._draft.bg_color = _normalized_color(self._draft.bg_color)
        self._theme: Theme = get_theme(self._draft.theme)
        self._autostart_available = bool(autostart_available)
        self._combos: list[_ComboBox] = []
        self._checkboxes: list[_ThemedCheckBox] = []
        self._swatches: list[_ColorSwatch] = []

        self._build_ui()
        self._connect_signals()
        self._load_from(self._draft)
        self._refresh_visual()

    # ----- dựng giao diện -------------------------------------------------- #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 12)
        root.setSpacing(9)
        self._root_layout = root

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Cài đặt", self)
        title.setObjectName("DialogTitleLabel")
        subtitle = QLabel(
            "Tuỳ chỉnh giao diện và hành vi của QT Calendar", self
        )
        subtitle.setObjectName("DialogSubtitleLabel")
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)
        root.addLayout(header)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("SettingsTabs")
        self._tabs.setDocumentMode(False)
        self._tabs.addTab(self._build_appearance_page(), "Giao diện")
        self._tabs.addTab(self._build_window_page(), "Cửa sổ")
        self._tabs.addTab(self._build_advanced_page(), "Nâng cao")
        root.addWidget(self._tabs, 1)

        caption_row = QHBoxLayout()
        caption_row.setSpacing(8)
        caption = QLabel("Xem trước", self)
        caption.setObjectName("PreviewCaption")
        self._preview_meta = QLabel("", self)
        self._preview_meta.setObjectName("PreviewMeta")
        self._preview_meta.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        caption_row.addWidget(caption)
        caption_row.addStretch(1)
        caption_row.addWidget(self._preview_meta)
        root.addLayout(caption_row)

        self._preview = _PreviewCard(self)
        root.addWidget(self._preview)

        buttons = QHBoxLayout()
        buttons.setSpacing(9)
        self._btn_reset = QPushButton("Đặt lại mặc định", self)
        self._btn_reset.setObjectName("GhostButton")
        self._btn_reset.setAutoDefault(False)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel = QPushButton("Huỷ", self)
        self._btn_cancel.setObjectName("SecondaryButton")
        self._btn_cancel.setAutoDefault(False)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save = QPushButton("Lưu", self)
        self._btn_save.setObjectName("PrimaryButton")
        self._btn_save.setDefault(True)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(self._btn_reset)
        buttons.addStretch(1)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        root.addLayout(buttons)

        self.resize(470, 566)

    # -- các trang ----------------------------------------------------------
    def _build_appearance_page(self) -> QWidget:
        page, layout = self._new_page()

        self._theme_combo = self._new_combo()
        for name in THEME_ORDER:
            theme = THEMES[name]
            self._theme_combo.addItem(
                _theme_icon(theme), theme.display_name, name
            )
        self._theme_combo.setIconSize(QSize(16, 16))

        self._opacity_row, self._opacity_slider, self._opacity_value = (
            self._slider_row(20, 100, 100, "%")
        )
        self._scale_row, self._scale_slider, self._scale_value = self._slider_row(
            75, 200, 100, "%"
        )

        self._chk_show_month = self._new_checkbox("Hiện lịch tháng dưới lịch ngày")

        self._chk_quote = self._new_checkbox("Hiện ca dao")
        self._chk_auspicious = self._new_checkbox("Hiện giờ hoàng đạo")
        self._chk_tiet_khi = self._new_checkbox("Hiện tiết khí")
        display_box = QGridLayout()
        display_box.setContentsMargins(0, 0, 0, 0)
        display_box.setHorizontalSpacing(14)
        display_box.setVerticalSpacing(5)
        display_box.addWidget(self._chk_quote, 0, 0)
        display_box.addWidget(self._chk_tiet_khi, 0, 1)
        display_box.addWidget(self._chk_auspicious, 1, 0, 1, 2)

        self._quote_combo = self._new_combo()
        for value, label in QUOTE_LABELS:
            self._quote_combo.addItem(label, value)

        form = self._new_form()
        form.addRow(self._field_label("Bảng màu"), self._theme_combo)
        form.addRow(self._field_label("Màu nền giấy"), self._build_bg_row())
        form.addRow(self._field_label("Độ trong suốt"), self._opacity_row)
        form.addRow(self._field_label("Cỡ nội dung"), self._scale_row)
        form.addRow(self._field_label("Chế độ xem"), self._chk_show_month)
        form.addRow(self._field_label("Hiển thị"), self._vertical(display_box))
        form.addRow(self._field_label("Nguồn ca dao"), self._quote_combo)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_window_page(self) -> QWidget:
        page, layout = self._new_page()

        self._placement_combo = self._new_combo()
        for value, label in PLACEMENT_LABELS:
            self._placement_combo.addItem(label, value)
        placement_hint = self._hint_label(
            "Ghim sát Desktop: widget nằm ngay trên nền Desktop và không bị "
            "che khi bấm Hiện Desktop."
        )
        placement_box = self._vertical(
            [self._placement_combo, placement_hint], spacing=4
        )

        self._chk_on_top = self._new_checkbox("Luôn nổi trên cùng")
        self._chk_lock = self._new_checkbox("Khoá vị trí")
        self._chk_autostart = self._new_checkbox("Khởi động cùng Windows")
        if not self._autostart_available:
            self._chk_autostart.setEnabled(False)
            self._chk_autostart.setToolTip("Chưa hỗ trợ trên nền tảng này.")
        behaviour_box = QVBoxLayout()
        behaviour_box.setSpacing(5)
        behaviour_box.addWidget(self._chk_on_top)
        behaviour_box.addWidget(self._chk_lock)
        behaviour_box.addWidget(self._chk_autostart)
        self._autostart_hint = self._hint_label("Không hỗ trợ trên nền tảng này.")
        self._autostart_hint.setVisible(False)
        if not self._autostart_available:
            self._autostart_hint.setVisible(True)
            behaviour_box.addWidget(self._autostart_hint)
        behaviour_box.addWidget(
            self._hint_label(
                "Luôn nổi trên cùng và Khoá vị trí chỉ áp dụng ở chế độ cửa sổ nổi."
            )
        )

        self._btn_reset_pos = QPushButton("Đặt lại vị trí", page)
        self._btn_reset_pos.setObjectName("SecondaryButton")
        self._btn_reset_pos.setAutoDefault(False)
        self._btn_reset_pos.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset_pos.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self._reset_status = self._hint_label("")
        self._reset_status.setVisible(False)
        position_box = self._vertical(
            [self._btn_reset_pos, self._reset_status], spacing=4
        )

        form = self._new_form()
        form.addRow(self._field_label("Vị trí"), placement_box)
        form.addRow(self._field_label("Hành vi"), self._vertical(behaviour_box))
        form.addRow(self._field_label("Toạ độ đã lưu"), position_box)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_advanced_page(self) -> QWidget:
        page, layout = self._new_page()

        self._engine_combo = self._new_combo()
        for value, label in ENGINE_LABELS:
            self._engine_combo.addItem(label, value)
        engine_hint = self._hint_label(
            "Chính xác cao dùng chuỗi Meeus, khớp lịch vạn niên Việt Nam; "
            "bản gốc Hồ Ngọc Đức là thuật toán cổ điển."
        )
        engine_box = self._vertical(
            [self._engine_combo, engine_hint], spacing=4
        )

        path_text = _config_file_path()
        self._path_label = _ElidedLabel(path_text, page)
        self._path_label.setObjectName("PathLabel")
        path_hint = self._hint_label(
            "Tệp cấu hình dùng để lưu mọi lựa chọn trong hộp thoại này."
        )
        path_box = self._vertical([self._path_label, path_hint], spacing=4)

        form = self._new_form()
        form.addRow(self._field_label("Thuật toán âm lịch"), engine_box)
        form.addRow(self._field_label("Tệp cấu hình"), path_box)
        layout.addLayout(form)
        layout.addWidget(
            self._hint_label("Thay đổi được áp dụng ngay sau khi bấm Lưu.")
        )
        layout.addStretch(1)
        return page

    # -- tiện ích dựng widget ----------------------------------------------
    def _build_bg_row(self) -> QWidget:
        """Hàng "Màu nền giấy": 10 swatch gợi ý + 2 nút + nhãn màu đang dùng."""
        row = QWidget(self)
        row.setObjectName("SettingsPage")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        swatch_row = QHBoxLayout()
        swatch_row.setContentsMargins(0, 0, 0, 0)
        swatch_row.setSpacing(6)
        for name, color in BACKGROUND_PRESETS:
            swatch = _ColorSwatch(name, color, row)
            swatch.clicked.connect(
                lambda _checked=False, chosen=color: self._set_bg_color(chosen)
            )
            self._swatches.append(swatch)
            swatch_row.addWidget(swatch, 0)
        swatch_row.addStretch(1)
        layout.addLayout(swatch_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
        self._btn_bg_theme = QPushButton("Theo giao diện", row)
        self._btn_bg_theme.setObjectName("BgThemeButton")
        self._btn_bg_theme.setCheckable(True)
        self._btn_bg_theme.setAutoDefault(False)
        self._btn_bg_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_bg_theme.setToolTip(
            "Dùng màu giấy gốc của bảng màu đang chọn"
        )
        self._btn_bg_pick = QPushButton("Màu tuỳ chọn…", row)
        self._btn_bg_pick.setObjectName("BgPickButton")
        self._btn_bg_pick.setAutoDefault(False)
        self._btn_bg_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_bg_pick.setToolTip("Mở bảng chọn màu nền giấy tuỳ ý")
        self._bg_status = QLabel("", row)
        self._bg_status.setObjectName("BgStatusLabel")
        self._bg_status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        action_row.addWidget(self._btn_bg_theme, 0)
        action_row.addWidget(self._btn_bg_pick, 0)
        action_row.addStretch(1)
        action_row.addWidget(self._bg_status, 0)
        layout.addLayout(action_row)
        return row

    def _new_page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self)
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(9)
        return page, layout

    def _new_form(self) -> QFormLayout:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        return form

    def _new_combo(self) -> _ComboBox:
        combo = _ComboBox(self)
        self._combos.append(combo)
        return combo

    def _new_checkbox(self, text: str) -> _ThemedCheckBox:
        checkbox = _ThemedCheckBox(text, self)
        self._checkboxes.append(checkbox)
        return checkbox

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("FieldLabel")
        return label

    def _hint_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("HintLabel")
        label.setWordWrap(True)
        return label

    def _vertical(self, items, *, spacing: int = 4) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SettingsPage")
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(spacing)
        if isinstance(items, QLayout):
            box.addLayout(items)
            return container
        for item in items:
            if isinstance(item, QWidget):
                box.addWidget(item)
            else:
                box.addLayout(item)
        return container

    def _slider_row(
        self, minimum: int, maximum: int, value: int, suffix: str
    ) -> tuple[QWidget, QSlider, QLabel]:
        container = QWidget(self)
        container.setObjectName("SettingsPage")
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        slider = QSlider(Qt.Orientation.Horizontal, container)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setPageStep(5)
        slider.setSingleStep(1)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        label = QLabel(f"{value}{suffix}", container)
        label.setObjectName("ValueLabel")
        label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(slider, 1)
        layout.addWidget(label, 0)
        return container, slider, label

    # ----- kết nối tín hiệu ------------------------------------------------ #
    def _connect_signals(self) -> None:
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._scale_slider.valueChanged.connect(self._on_scale_changed)
        self._chk_quote.toggled.connect(self._on_show_quote_changed)
        self._btn_bg_theme.clicked.connect(lambda: self._set_bg_color(""))
        self._btn_bg_pick.clicked.connect(self._pick_bg_color)
        self._btn_reset.clicked.connect(self._on_reset_defaults)
        self._btn_reset_pos.clicked.connect(self._on_reset_position)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save.clicked.connect(self._on_save)

    # ----- nạp dữ liệu ----------------------------------------------------- #
    def _load_from(
        self, settings: Settings, *, use_live_autostart: bool = True
    ) -> None:
        self._set_combo_value(self._theme_combo, settings.theme)
        self._set_combo_value(
            self._quote_combo,
            settings.quote_mode,
        )
        self._set_combo_value(self._placement_combo, settings.placement)
        self._set_combo_value(
            self._engine_combo,
            str(getattr(settings, "lunar_engine", "precise")),
        )

        self._opacity_slider.setValue(int(round(settings.opacity * 100)))
        self._scale_slider.setValue(int(round(settings.scale * 100)))
        self._opacity_value.setText(f"{self._opacity_slider.value()}%")
        self._scale_value.setText(f"{self._scale_slider.value()}%")

        self._chk_show_month.setChecked(bool(settings.show_month))

        self._chk_quote.setChecked(bool(settings.show_quote))
        self._chk_auspicious.setChecked(bool(settings.show_auspicious))
        self._chk_tiet_khi.setChecked(bool(settings.show_tiet_khi))
        self._chk_on_top.setChecked(bool(settings.always_on_top))
        self._chk_lock.setChecked(bool(settings.lock_position))
        autostart_state = bool(settings.run_at_startup)
        if use_live_autostart and self._autostart_available:
            autostart_state = self._live_autostart_state(autostart_state)
        self._chk_autostart.setChecked(autostart_state)

        self._draft.bg_color = _normalized_color(settings.bg_color)
        self._quote_combo.setEnabled(self._chk_quote.isChecked())
        self._reset_status.setVisible(False)
        self._sync_bg_widgets()
        self._update_meta()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _live_autostart_state(fallback: bool) -> bool:
        """Đọc trạng thái Registry nếu tầng platform đã sẵn sàng."""
        try:  # platform.autostart do người khác phụ trách
            from ..platform import autostart  # noqa: PLC0415

            getter = getattr(autostart, "is_enabled", None)
            if callable(getter):
                return bool(getter())
        except Exception:  # pragma: no cover - module đang được hoàn thiện
            pass
        return fallback

    # ----- sự kiện --------------------------------------------------------- #
    def _on_theme_changed(self, index: int) -> None:
        name = self._theme_combo.itemData(index)
        if isinstance(name, str) and name in THEMES:
            self._draft.theme = name
        self._refresh_visual()

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_value.setText(f"{value}%")
        self._refresh_visual()

    def _on_scale_changed(self, value: int) -> None:
        self._scale_value.setText(f"{value}%")
        self._refresh_visual()

    def _on_show_quote_changed(self, checked: bool) -> None:
        self._quote_combo.setEnabled(bool(checked))

    # ----- màu nền giấy ----------------------------------------------------- #
    def _base_theme(self) -> Theme:
        """Theme gốc đang chọn trong combo (chưa áp màu nền/độ mờ)."""
        name = self._theme_combo.currentData()
        if isinstance(name, str) and name in THEMES:
            return THEMES[name]
        return get_theme(self._draft.theme)

    def _current_bg(self) -> str:
        """Màu nền đang chọn: ``""`` = theo giao diện, ngược lại ``#RRGGBB``."""
        return _normalized_color(self._draft.bg_color)

    def _set_bg_color(self, color: str) -> None:
        """Đổi màu nền giấy của bản nháp và cập nhật ngay phần xem trước."""
        self._draft.bg_color = _normalized_color(color)
        self._sync_bg_widgets()
        self._refresh_visual()

    def _pick_bg_color(self) -> None:
        """Mở bảng chọn màu (không chọn alpha – alpha do thanh độ mờ lo)."""
        current = self._current_bg()
        start = QColor(current) if current else QColor(_solid(self._theme.paper))
        color = QColorDialog.getColor(start, self, "Chọn màu nền giấy")
        if color.isValid():
            self._set_bg_color(color.name())

    def _sync_bg_widgets(self) -> None:
        """Đồng bộ trạng thái swatch/nút/nhãn với màu nền của bản nháp."""
        background = self._current_bg()
        for swatch in self._swatches:
            swatch.setChecked(bool(background) and swatch.color() == background)
        self._btn_bg_theme.setChecked(not background)
        if background:
            self._bg_status.setText(background)
            self._bg_status.setToolTip(f"Nền giấy tuỳ chọn {background}")
        else:
            self._bg_status.setText("Theo giao diện")
            self._bg_status.setToolTip("Nền giấy lấy theo bảng màu đang chọn")

    def _on_reset_position(self) -> None:
        self._draft.x = -1
        self._draft.y = -1
        self._reset_status.setText(
            "Đã đặt lại vị trí – vị trí mới áp dụng sau khi bấm Lưu."
        )
        self._reset_status.setVisible(True)

    def _on_reset_defaults(self) -> None:
        defaults = Settings()
        self._draft = defaults.copy()
        self._load_from(defaults, use_live_autostart=False)
        self._refresh_visual()
        self._reset_status.setVisible(False)

    def _on_save(self) -> None:
        self._collect()
        self.accept()

    # ----- theme / preview ------------------------------------------------- #
    def set_theme_preview(self, theme: Theme) -> None:
        """Áp bảng màu cho chính hộp thoại (và thẻ xem trước).

        ``theme`` có thể là theme đã áp **màu nền + độ mờ** (``paper_theme``).
        Hộp thoại dùng bản nền **đục** (bỏ alpha của màu giấy) để bảng cài
        đặt không bị trong suốt khó đọc, còn thẻ xem trước giữ nguyên alpha
        trong màu giấy – đúng như widget thật.
        """
        if theme is None:  # pragma: no cover - phòng thủ
            theme = get_theme(None)
        self._theme = theme

        index = self._theme_combo.findData(theme.name)
        if index >= 0 and index != self._theme_combo.currentIndex():
            self._theme_combo.blockSignals(True)
            self._theme_combo.setCurrentIndex(index)
            self._theme_combo.blockSignals(False)

        chrome = _opaque_theme(theme)
        self._apply_stylesheet(chrome)
        for combo in self._combos:
            combo.set_arrow_color(chrome.ink_soft)
        for checkbox in self._checkboxes:
            checkbox.set_theme(chrome)
        for swatch in self._swatches:
            swatch.set_theme(chrome)
        self._preview.set_preview(
            theme,
            1.0,
            self._scale_slider.value() / 100.0,
        )
        self._update_meta()
        self.update()

    def _apply_stylesheet(self, theme: Theme) -> None:
        theirs = ""
        try:  # ui.styles do người khác phụ trách
            from .styles import build_stylesheet  # noqa: PLC0415

            candidate = build_stylesheet(theme, 1.0)
            if isinstance(candidate, str):
                theirs = candidate
        except Exception:  # pragma: no cover - styles.py đang được hoàn thiện
            theirs = ""
        try:
            from .styles import build_dialog_stylesheet  # noqa: PLC0415

            extra = build_dialog_stylesheet(theme, 1.0)
            if isinstance(extra, str) and extra.strip():
                theirs = f"{theirs}\n{extra}" if theirs else extra
        except Exception:  # pragma: no cover
            pass

        fallback = _dialog_qss(theme)
        self.setStyleSheet(f"{theirs}\n{fallback}" if theirs else fallback)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme.paper))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.paper))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme.chip_bg))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
        palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor(theme.accent_ink)
        )
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.chip_bg))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.ink))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.ink_faint))
        self.setPalette(palette)

        font = QFont(theme.font_ui)
        font.setPixelSize(12)
        self.setFont(font)

    def _refresh_visual(self) -> None:
        """Tính theme hiển thị (màu nền + độ mờ) rồi áp cho dialog + preview."""
        visual = paper_theme(
            self._base_theme(),
            self._opacity_slider.value() / 100.0,
            self._current_bg(),
        )
        self.set_theme_preview(visual)

    def _update_meta(self) -> None:
        background = self._current_bg()
        background_text = background if background else "nền theo giao diện"
        self._preview_meta.setText(
            f"{self._base_theme().display_name} · {background_text}"
            f" · mờ {self._opacity_slider.value()}%"
            f" · cỡ {self._scale_slider.value()}%"
        )

    # ----- thu thập dữ liệu ------------------------------------------------ #
    def _collect(self) -> Settings:
        settings = self._draft.copy()
        theme_name = self._theme_combo.currentData()
        if isinstance(theme_name, str):
            settings.theme = theme_name
        settings.opacity = self._opacity_slider.value() / 100.0
        settings.scale = self._scale_slider.value() / 100.0
        settings.show_month = self._chk_show_month.isChecked()
        settings.show_quote = self._chk_quote.isChecked()
        settings.show_auspicious = self._chk_auspicious.isChecked()
        settings.show_tiet_khi = self._chk_tiet_khi.isChecked()
        quote_mode = self._quote_combo.currentData()
        if isinstance(quote_mode, str):
            settings.quote_mode = quote_mode
        placement = self._placement_combo.currentData()
        if isinstance(placement, str):
            settings.placement = placement
        settings.always_on_top = self._chk_on_top.isChecked()
        settings.lock_position = self._chk_lock.isChecked()
        settings.run_at_startup = self._chk_autostart.isChecked()
        settings.bg_color = self._current_bg()
        engine = self._engine_combo.currentData()
        if isinstance(engine, str):
            try:  # sẵn sàng cho khi Settings bổ sung trường lunar_engine
                setattr(settings, "lunar_engine", engine)
            except AttributeError:
                pass
        settings.clamp()
        self._draft = settings
        return settings.copy()

    # ----- API công khai --------------------------------------------------- #
    def settings(self) -> Settings:
        """Cấu hình hiện tại trong hộp thoại (trên bản sao)."""
        return self._collect()

    @staticmethod
    def edit(
        settings: Settings,
        parent: QWidget | None = None,
        **kwargs,
    ) -> Settings | None:
        """Mở hộp thoại; trả cấu hình mới nếu Lưu, ``None`` nếu Huỷ."""
        dialog = SettingsDialog(settings, parent, **kwargs)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            return dialog.settings() if accepted else None
        finally:
            dialog.deleteLater()
