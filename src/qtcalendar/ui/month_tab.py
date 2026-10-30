"""Tab kéo dưới chân lịch – bật/tắt lịch tháng hiện ngay dưới lịch bloc.

Tab là một mẩu giấy nhỏ treo dưới mép tờ lịch cuối cùng (tờ bloc khi lịch
tháng đóng, tờ lịch tháng khi đang mở): góc trên vuông chạm mép giấy, hai góc
dưới bo tròn, kèm mũi tên chevron và chữ ``THÁNG`` / ``ẨN``.

Mũi tên được **vẽ tay** bằng ``QPainterPath``. Không dùng ký tự tượng hình
(▾, ▴…): khi font hiện tại thiếu glyph, DirectWrite nạp cả bộ font dự phòng –
tốn thêm ~85 MB RAM (đã đo thực nghiệm, xem ``widget_window.py``).

Tab không biết gì về cấu hình hay cửa sổ: :class:`CalendarWidget` đặt vị trí,
trạng thái (:meth:`MonthTab.set_open`) và theme cho nó; tab chỉ phát
:attr:`MonthTab.toggled` khi người dùng bấm.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..core.theme import Theme, alpha_of, get_theme
from .styles import px, qcolor

__all__ = ["MonthTab"]

#: Chữ trên tab theo trạng thái.
_LABEL_CLOSED = "THÁNG"
_LABEL_OPEN = "ẨN"


class MonthTab(QWidget):
    """Tab giấy bật/tắt lịch tháng.

    Tín hiệu ``toggled`` phát khi người dùng bấm chuột trái lên tab.
    """

    toggled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open = False
        self._hover = False
        self._theme: Theme = get_theme(None)
        self._scale = 1.0
        self.setObjectName("MonthTab")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._sync_tooltip()

    # ------------------------------------------------------------ trạng thái
    def set_open(self, flag: bool) -> None:
        """``False`` → ``THÁNG`` + mũi tên xuống; ``True`` → ``ẨN`` + mũi tên lên."""
        flag = bool(flag)
        if flag == self._open:
            return
        self._open = flag
        self._sync_tooltip()
        self.update()

    def is_open(self) -> bool:
        return self._open

    def label(self) -> str:
        return _LABEL_OPEN if self._open else _LABEL_CLOSED

    def arrow_points_down(self) -> bool:
        return not self._open

    def apply_theme(self, theme: Theme, scale: float) -> None:
        """Màu theo bảng màu đang vẽ (đã gồm độ mờ nền), cỡ theo hệ số phóng."""
        self._theme = theme if theme is not None else get_theme(None)
        self._scale = max(0.5, float(scale))
        self.updateGeometry()
        self.update()

    def _sync_tooltip(self) -> None:
        self.setToolTip("Ẩn lịch tháng" if self._open else "Hiện lịch tháng")

    # ------------------------------------------------------------- kích thước
    def sizeHint(self) -> QSize:  # noqa: N802 (Qt API)
        return QSize(px(78, self._scale), px(22, self._scale))

    def _font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(px(10, self._scale))
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        return font

    # ------------------------------------------------------------------ vẽ
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        theme = self._theme
        rect = QRectF(self.rect()).adjusted(0.5, 0.0, -0.5, -0.5)
        if rect.width() <= 4 or rect.height() <= 4:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # --- nền giấy: chỉ nền mờ theo độ trong suốt, chữ luôn đục ----------
        radius = min(rect.height() * 0.45, float(px(8, self._scale)))
        path = QPainterPath()
        path.moveTo(rect.topLeft())
        path.lineTo(rect.topRight())
        path.lineTo(rect.right(), rect.bottom() - radius)
        path.quadTo(rect.bottomRight(), QPointF(rect.right() - radius, rect.bottom()))
        path.lineTo(rect.left() + radius, rect.bottom())
        path.quadTo(rect.bottomLeft(), QPointF(rect.left(), rect.bottom() - radius))
        path.closeSubpath()

        paper_alpha = alpha_of(theme.paper)
        painter.save()
        if paper_alpha < 0.999:
            painter.setOpacity(paper_alpha)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, qcolor(theme.paper_2))
        gradient.setColorAt(1.0, qcolor(theme.paper))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(qcolor(theme.paper_edge), 1.0))
        painter.drawPath(path)
        painter.restore()

        # --- mũi tên chevron + chữ, căn giữa cả cụm --------------------------
        ink = qcolor(theme.accent if self._hover else theme.ink_soft)
        font = self._font()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text = self.label()
        text_w = metrics.horizontalAdvance(text)
        arrow_w = max(5.0, px(7, self._scale) * 1.0)
        gap = max(3.0, px(4, self._scale) * 1.0)
        total = arrow_w + gap + text_w
        left = rect.center().x() - total / 2.0
        mid_y = rect.center().y()

        arrow_h = arrow_w * 0.5
        top = mid_y - arrow_h / 2.0
        bottom = mid_y + arrow_h / 2.0
        chevron = QPainterPath()
        if self.arrow_points_down():
            chevron.moveTo(left, top)
            chevron.lineTo(left + arrow_w / 2.0, bottom)
            chevron.lineTo(left + arrow_w, top)
        else:
            chevron.moveTo(left, bottom)
            chevron.lineTo(left + arrow_w / 2.0, top)
            chevron.lineTo(left + arrow_w, bottom)
        pen = QPen(ink)
        pen.setWidthF(max(1.2, 1.4 * self._scale))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(chevron)

        painter.setPen(ink)
        text_rect = QRectF(left + arrow_w + gap, rect.top(), text_w + 2, rect.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.end()

    # ------------------------------------------------------------- chuột
    def enterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            event.accept()
            self.toggled.emit()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        # Nháy đúp lên tab = hai lần bấm; không để sự kiện lan lên cửa sổ
        # (cửa sổ cũng bật/tắt lịch tháng khi nháy đúp ⇒ bị đảo ba lần).
        event.accept()
