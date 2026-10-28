"""Cửa sổ widget chính – không viền, kéo thả tự do, ghim sát Desktop.

Trách nhiệm
===========

* Dựng khung cửa sổ trong suốt, không viền, không thanh tiêu đề.
* Chuyển giữa hai mặt: :class:`~qtcalendar.ui.bloc_view.BlocView` (lịch ngày)
  và :class:`~qtcalendar.ui.month_view.MonthView` (lịch tháng).
* Kéo thả bằng chuột trái, tự lưu toạ độ khi thả, tự kẹp vào màn hình.
* Áp dụng độ trong suốt, bảng màu, tỉ lệ nội dung.
* Ghim cửa sổ xuống mặt bàn Desktop (``SetParent(Progman)``) và có watchdog
  tự ghim lại nếu Explorer khởi động lại.
* Menu ngữ cảnh chuột phải + hai nút nổi ở góc trên (đổi chế độ xem, menu).

Việc mở hộp thoại cài đặt, lưu tệp cấu hình, khay hệ thống do ``app.py``
(tầng điều phối) đảm nhận – widget chỉ phát tín hiệu.

Tín hiệu
========

``settings_changed``
    Có thay đổi cần lưu (vị trí, độ mờ, chế độ xem, ghim…).
``settings_requested``
    Người dùng bấm "Cài đặt…".
``quit_requested``
    Người dùng chọn "Thoát".
``hide_requested``
    Người dùng chọn "Ẩn widget" (đưa về khay hệ thống).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import calendar_service
from ..core.canchi_constants import WEEKDAY_UPPER
from ..core.config import Settings
from ..core.quotes import quote_of_day, random_quote
from ..core.theme import (
    BACKGROUND_PRESETS,
    Theme,
    alpha_of,
    get_theme,
    paper_theme,
)
from ..platform import autostart, desktop_pin
from .bloc_view import BlocView
from .month_view import MonthView
from . import styles

__all__ = [
    "CalendarWidget",
    "BASE_WIDTH",
    "BASE_HEIGHT",
    "MIN_WIDTH",
    "MIN_HEIGHT",
    "MAX_WIDTH",
    "MAX_HEIGHT",
]

#: Kích thước chuẩn của bloc ở tỉ lệ 100 %.
BASE_WIDTH = 344
BASE_HEIGHT = 468

#: Kích thước nhỏ nhất/lớn nhất cho phép khi người dùng kéo tay nắm ở góc.
MIN_WIDTH = 260
MIN_HEIGHT = 330
MAX_WIDTH = 1000
MAX_HEIGHT = 1300

#: Lề trong suốt quanh tấm giấy (để vẽ bóng đổ).
SHADOW_MARGIN = 10

#: Các mức độ trong suốt trong menu nhanh.
OPACITY_STEPS = (1.00, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20)

#: Cạnh của tay nắm kéo giãn ở góc dưới phải (pixel logic).
GRIP_SIZE = 18

#: Độ đục tối đa khi đã ghim desktop (254/255). Phải < 1.0 để Qt giữ
#: ``WS_EX_LAYERED`` – điều kiện bắt buộc để cửa sổ con của Progman hiển thị
#: trên Windows 11 24H2 trở lên.
_PINNED_MAX_OPACITY = 254.0 / 255.0


def _clamp_size(value: int, low: int, high: int) -> int:
    """Kẹp một cạnh của widget trong khoảng cho phép."""
    return int(max(low, min(high, int(value))))


def _win32_module():
    """Import trễ mô-đun win32 (trả ``None`` trên nền tảng không phải Windows)."""
    try:
        from ..platform import win32

        return win32 if getattr(win32, "user32", None) is not None else None
    except Exception:  # pragma: no cover - không phải Windows
        return None


class _ResizeGrip(QWidget):
    """Tay nắm nhỏ ở góc dưới phải để kéo thay đổi kích thước widget.

    Widget con trong suốt, tự vẽ ba nét chéo kiểu "grip" quen thuộc của
    Windows. Nó chuyển sự kiện chuột cho :class:`CalendarWidget` để việc tính
    kích thước/giới hạn nằm một chỗ duy nhất.
    """

    def __init__(self, owner: "CalendarWidget") -> None:
        super().__init__(owner)
        self._owner = owner
        self._color = QColor("#8B7B68")
        self.setObjectName("ResizeGrip")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setToolTip("Kéo để phóng to / thu nhỏ widget")

    def set_color(self, color: QColor) -> None:
        """Đổi màu ba nét vẽ theo theme hiện tại."""
        self._color = QColor(color)
        self.update()

    # ------------------------------------------------------------------ vẽ
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(self._color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        size = min(self.width(), self.height())
        margin = max(3.0, size * 0.22)
        for step in range(3):
            offset = margin + step * (size - 2 * margin) / 2.6
            painter.drawLine(
                int(size - offset), self.height() - int(margin),
                int(size - margin), self.height() - int(offset),
            )
        painter.end()

    # ------------------------------------------------------------- chuột
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton:
            self._owner.begin_resize(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.buttons() & Qt.LeftButton:
            self._owner.drag_resize(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton:
            self._owner.end_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CalendarWidget(QWidget):
    """Widget lịch Dương – Âm không viền, ghim được xuống desktop."""

    settings_changed = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    update_check_requested = Signal()
    hide_requested = Signal()

    # ------------------------------------------------------------------ init
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._theme: Theme = get_theme(settings.theme)
        self._scale: float = settings.scale
        self._selected: date | None = None  # None = hôm nay
        self._dragging = False
        self._drag_offset = QPoint()
        self._drag_moved = False
        self._resizing = False
        self._resize_start_size = QSize(self._settings.width, self._settings.height)
        self._resize_start_pos = QPoint()
        #: Hệ số phóng nội dung đang áp dụng (tự suy ra từ kích thước cửa sổ).
        self._content_scale_applied = 0.0
        self._pinned = False
        self._quote = None
        self._quote_random = False
        self._last_quote_day: date | None = None

        self.setObjectName("CalendarRoot")
        self.setWindowTitle("QT Calendar")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._icon = QIcon(str(self._resolve_asset("icon.ico")))
        if not self._icon.isNull():
            self.setWindowIcon(self._icon)

        self._apply_window_flags()
        self._build_ui()
        self._refresh_content()
        self._apply_theme()
        self._apply_opacity()
        self._start_timers()

    # ------------------------------------------------------------ asset path
    @staticmethod
    def _resolve_asset(name: str):
        from pathlib import Path

        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "assets" / name
            if candidate.is_file():
                return candidate
        return Path(name)

    # ------------------------------------------------------------- cửa sổ
    def _apply_window_flags(self) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if self._settings.always_on_top and self._settings.placement == "floating":
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _build_ui(self) -> None:
        """Dựng QStackedWidget + hai nút nổi góc trên phải."""
        margin = SHADOW_MARGIN
        layout = QVBoxLayout(self)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(0)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("CardStack")
        layout.addWidget(self._stack)

        self._bloc = BlocView(self._stack)
        self._stack.addWidget(self._bloc)

        # Lịch tháng được tạo **lười** ở lần đầu người dùng mở nó. Lý do: dựng
        # 42 ô ngày khiến Qt khởi tạo cache đo chữ/elide của Windows, tốn thêm
        # ~70 MB – không đáng phải trả khi đa số người dùng chỉ dùng lịch ngày.
        self._month: MonthView | None = None
        self._month_placeholder = QWidget(self._stack)
        self._month_placeholder.setObjectName("MonthPlaceholder")
        self._stack.addWidget(self._month_placeholder)

        # Hai nút nổi: đổi chế độ xem + menu nhanh
        self._overlay = QWidget(self)
        self._overlay.setObjectName("Overlay")
        overlay_layout = QHBoxLayout(self._overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(6)

        self._view_btn = QPushButton("THÁNG", self._overlay)
        self._view_btn.setObjectName("ViewSwitch")
        self._view_btn.setCursor(Qt.PointingHandCursor)
        self._view_btn.setToolTip("Chuyển giữa lịch ngày và lịch tháng")
        self._view_btn.clicked.connect(self.toggle_view)

        # Dấu ba chấm dùng U+2026 (có sẵn trong Segoe UI). TUYỆT ĐỐI không dùng
        # các ký tự tượng hình như U+22EF "⋯", U+25B8 "▸", U+2699 "⚙": khi
        # Windows không tìm thấy glyph trong font hiện tại, DirectWrite phải
        # nạp cả bộ font dự phòng – tốn thêm ~85 MB RAM (đã đo thực nghiệm).
        self._menu_btn = QPushButton("\u2026", self._overlay)
        self._menu_btn.setObjectName("MenuButton")
        self._menu_btn.setCursor(Qt.PointingHandCursor)
        self._menu_btn.setToolTip("Menu nhanh")
        self._menu_btn.clicked.connect(self._show_menu_at_button)

        overlay_layout.addWidget(self._view_btn)
        overlay_layout.addWidget(self._menu_btn)
        self._overlay.adjustSize()
        self._overlay.hide()  # chỉ hiện khi rê chuột lên widget

        # Tay nắm kéo giãn ở góc dưới phải – luôn hiện để người dùng dễ thấy.
        self._grip = _ResizeGrip(self)
        self._grip.setObjectName("ResizeGrip")

        # Kết nối view
        self._bloc.quote_clicked.connect(self._on_quote_clicked)

        # Đổi kích thước cửa sổ ⇒ phóng/thu nội dung cho khớp (gộp 90 ms để
        # không phải dựng lại QSS ở mỗi pixel trong lúc người dùng kéo).
        self._content_scale_timer = QTimer(self)
        self._content_scale_timer.setSingleShot(True)
        self._content_scale_timer.setInterval(90)
        self._content_scale_timer.timeout.connect(self._apply_content_scale)

    # ------------------------------------------------ hệ số phóng nội dung
    def content_scale(self) -> float:
        """Hệ số phóng thực tế = ``settings.scale`` × tỉ lệ cửa sổ so với chuẩn.

        Nhờ vậy khi người dùng kéo widget to ra, chữ và các khối nội dung cùng
        lớn theo thay vì để trống một khoảng giấy; khi thu nhỏ thì tự co lại
        (tối thiểu 0,5 – dưới mức đó chữ không đọc được).
        """
        ratio = min(
            self.width() / float(BASE_WIDTH),
            self.height() / float(BASE_HEIGHT),
        )
        return max(0.5, min(2.6, float(self._settings.scale) * ratio))

    def _visual(self) -> Theme:
        """Theme dùng để vẽ: màu nền tuỳ chọn + độ mờ.

        Khi đã ghim desktop, cửa sổ trở thành **cửa sổ con** và Windows không
        ghép kênh alpha từng điểm ảnh cho cửa sổ con (nền trong suốt bị vẽ
        đè lên màu đen). Vì vậy lúc ghim, theme luôn **đục 100 %**; độ mờ được
        làm bằng ``LWA_ALPHA`` cho cả cửa sổ (xem :meth:`_apply_opacity`).
        """
        theme = getattr(self, "_visual_theme", None)
        if theme is None:
            theme = paper_theme(
                self._theme, self._paper_opacity(), self._settings.bg_color
            )
            self._visual_theme = theme
        return theme

    def _paper_opacity(self) -> float:
        """Độ mờ áp vào **màu giấy** (chỉ khác 1.0 khi cửa sổ nổi)."""
        if getattr(self, "_pin_look", False):
            return 1.0
        return float(self._settings.opacity)

    def _apply_content_scale(self) -> None:
        """Áp hệ số phóng mới cho các view đang có (gọi có debounce)."""
        scale = self.content_scale()
        if abs(scale - self._content_scale_applied) < 0.01:
            return
        self._content_scale_applied = scale
        visual = self._visual()
        self._bloc.apply_theme(visual, scale)
        if self._month is not None:
            self._month.apply_theme(visual, scale)
        self._layout_overlay()
        self._layout_grip()

    # ------------------------------------------------------- lịch tháng (lười)
    def _ensure_month(self) -> MonthView:
        """Tạo lịch tháng ở lần dùng đầu tiên rồi nối tín hiệu."""
        if self._month is not None:
            return self._month
        month = MonthView(self._stack)
        self._stack.insertWidget(1, month)
        self._stack.removeWidget(self._month_placeholder)
        self._month_placeholder.deleteLater()
        self._month = month

        month.day_activated.connect(self._on_day_activated)
        month.month_changed.connect(self._on_month_changed)
        month.today_requested.connect(self.go_today)
        # Lịch tháng có nút "Ngày" riêng để quay về bloc (vì hai nút nổi bị ẩn
        # khi đang ở chế độ lịch tháng để không che tiêu đề/nút chuyển tháng).
        if hasattr(month, "bloc_requested"):
            month.bloc_requested.connect(lambda: self.set_view("bloc"))

        month.apply_theme(self._visual(), self.content_scale())
        self._sync_month_view()
        return month

    # --------------------------------------------------------------- timers
    def _start_timers(self) -> None:
        # Cập nhật khi sang ngày mới (đặt chính xác tới nửa đêm)
        self._midnight_timer = QTimer(self)
        self._midnight_timer.setSingleShot(True)
        self._midnight_timer.timeout.connect(self._on_new_day)
        self._schedule_midnight()

        # Đổi ca dao ngẫu nhiên mỗi 30 phút
        self._quote_timer = QTimer(self)
        self._quote_timer.setInterval(30 * 60 * 1000)
        self._quote_timer.timeout.connect(self._on_quote_tick)
        self._quote_timer.start()

        # Watchdog giữ cửa sổ trên desktop
        self._pin_timer = QTimer(self)
        self._pin_timer.setInterval(2000)
        self._pin_timer.timeout.connect(self._watch_pin)
        self._pin_timer.start()

    def _schedule_midnight(self) -> None:
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=3, microsecond=0
        )
        ms = max(1000, int((tomorrow - now).total_seconds() * 1000))
        self._midnight_timer.start(ms)

    def _on_new_day(self) -> None:
        self._selected = None
        if self._month is not None:
            self._month.set_today(date.today())
        self._refresh_content()
        self._schedule_midnight()

    def _on_quote_tick(self) -> None:
        if self._settings.quote_mode == "random":
            self._quote = random_quote()
            self._bloc.set_quote(self._quote)

    # -------------------------------------------------------------- nội dung
    def _current_day(self) -> date:
        return self._selected or calendar_service.today()

    def _refresh_content(self) -> None:
        """Nạp lại ngày đang hiển thị + ca dao + lịch tháng."""
        day = self._current_day()
        info = calendar_service.get_day_info(day, self._settings.lunar_engine)
        self._bloc.set_day(info)
        self._bloc.set_show_auspicious(self._settings.show_auspicious)
        self._bloc.set_show_tiet_khi(self._settings.show_tiet_khi)

        if self._settings.show_quote:
            self._quote = self._pick_quote(day)
        else:
            self._quote = None
        self._bloc.set_quote(self._quote)

        self._sync_month_view()

    def _pick_quote(self, day: date):
        if self._settings.quote_mode == "random":
            if self._last_quote_day != day:
                self._last_quote_day = day
                return random_quote()
            return self._quote if self._quote is not None else random_quote()
        self._last_quote_day = day
        return quote_of_day(day)

    def _on_quote_clicked(self) -> None:
        """Bấm vào khung ca dao để đổi câu khác."""
        self._quote = random_quote()
        self._bloc.set_quote(self._quote)

    # ------------------------------------------------------------ chế độ xem
    def set_view(self, view: str) -> None:
        view = view if view in ("bloc", "month") else "bloc"
        if view == self._settings.view and self._stack.currentIndex() == (
            1 if view == "month" else 0
        ):
            return
        self._settings.view = view
        self._stack.setCurrentIndex(1 if view == "month" else 0)
        if view == "month":
            self._ensure_month()
        self._view_btn.setText("NGÀY" if view == "month" else "THÁNG")
        # Ở chế độ lịch tháng, tiêu đề và nút chuyển tháng nằm sát góc trên phải
        # nên hai nút nổi được ẩn đi (lịch tháng có nút "Ngày" riêng).
        self._overlay.setVisible(view == "bloc" and self.underMouse())
        self._sync_month_view()
        self.settings_changed.emit()

    def toggle_view(self) -> None:
        self.set_view("month" if self._settings.view == "bloc" else "bloc")

    def go_today(self) -> None:
        """Quay về hôm nay (cả bloc lẫn lịch tháng)."""
        self._selected = None
        self._refresh_content()

    # ---------------------------------------------------------- lịch tháng
    def _sync_month_view(self) -> None:
        if self._month is None:
            return
        anchor = self._settings.month_anchor
        year = month = None
        if anchor:
            try:
                year_s, month_s = anchor.split("-", 1)
                year, month = int(year_s), int(month_s)
            except ValueError:
                year = month = None
        if not year or not 1 <= (month or 0) <= 12:
            now = calendar_service.today()
            year, month = now.year, now.month
        self._month.set_month(year, month)
        self._month.set_today(calendar_service.today())

    def _on_month_changed(self, year: int, month: int) -> None:
        self._settings.month_anchor = f"{year:04d}-{month:02d}"
        self.settings_changed.emit()

    def _on_day_activated(self, value) -> None:
        if not isinstance(value, date):
            return
        if value == calendar_service.today():
            self._selected = None
        else:
            self._selected = value
        self._refresh_content()
        self.set_view("bloc")

    # -------------------------------------------------------------- theme
    def apply_theme(self, name: str | None = None) -> None:
        if name:
            self._settings.theme = name
        self._theme = get_theme(self._settings.theme)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Áp bảng màu **đã tính độ mờ của nền và màu nền tuỳ chọn** lên mọi view."""
        theme = self._theme
        visual = paper_theme(
            theme, self._paper_opacity(), self._settings.bg_color
        )
        self._visual_theme = visual
        scale = self._scale
        content_scale = self.content_scale()
        self._content_scale_applied = content_scale
        self._bloc.apply_theme(visual, content_scale)
        if self._month is not None:
            self._month.apply_theme(visual, content_scale)
        qss = styles.build_stylesheet(visual, scale)
        self.setStyleSheet(qss)
        self._apply_overlay_style()
        if hasattr(self, "_grip"):
            self._grip.set_color(QColor(visual.ink_faint))
            self._layout_grip()
        self._apply_pin_palette(visual)
        self.update()

    def _apply_overlay_style(self) -> None:
        """Style riêng cho hai nút nổi (độc lập với QSS toàn cục)."""
        theme = getattr(self, "_visual_theme", self._theme)
        f = styles.px(10.5, self._scale)
        pad_v = styles.px(2, self._scale)
        pad_h = styles.px(8, self._scale)
        radius = styles.px(9, self._scale)
        qss = f"""
        QWidget#Overlay {{ background: transparent; }}
        QPushButton#ViewSwitch, QPushButton#MenuButton {{
            color: {theme.ink_soft};
            background: {theme.chip_bg};
            border: 1px solid {theme.line};
            border-radius: {radius}px;
            padding: {pad_v}px {pad_h}px;
            font-size: {f}px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QPushButton#ViewSwitch:hover, QPushButton#MenuButton:hover {{
            color: {theme.accent_ink};
            background: {theme.accent};
            border-color: {theme.accent};
        }}
        QPushButton#MenuButton {{
            font-size: {styles.px(13, self._scale)}px;
            padding: {pad_v}px {styles.px(6, self._scale)}px;
            letter-spacing: 0px;
        }}
        """
        self._overlay.setStyleSheet(qss)
        for btn in (self._view_btn, self._menu_btn):
            btn.adjustSize()

    # ------------------------------------------------------------ hình học
    def apply_settings(self, rebuild_flags: bool = False) -> None:
        """Áp toàn bộ :class:`Settings` lên giao diện."""
        if rebuild_flags:
            was_visible = self.isVisible()
            self._apply_window_flags()
            if was_visible:
                self.show()
        self._scale = self._settings.scale
        self._theme = get_theme(self._settings.theme)
        self._apply_theme()
        self._resize_to_settings()
        self._apply_opacity()
        self.set_view(self._settings.view)
        self._apply_placement()
        self._refresh_content()

    def _resize_to_settings(self) -> None:
        w = _clamp_size(self._settings.width, MIN_WIDTH, MAX_WIDTH)
        h = _clamp_size(self._settings.height, MIN_HEIGHT, MAX_HEIGHT)
        if self.width() != w or self.height() != h:
            self.resize(w, h)
        self._settings.width = w
        self._settings.height = h

    def sizeHint(self) -> QSize:  # pragma: no cover - Qt hint
        return QSize(self._settings.width, self._settings.height)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._layout_overlay()
        self._layout_grip()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._layout_overlay()
        self._layout_grip()
        if hasattr(self, "_content_scale_timer"):
            self._content_scale_timer.start()

    # ------------------------------------------------- kéo giãn kích thước
    def _min_size(self) -> QSize:
        """Kích thước nhỏ nhất thực tế = giới hạn thiết kế ∪ nhu cầu của layout.

        Nội dung bên trong (lịch bloc/lịch tháng) có kích thước tối thiểu riêng,
        nên đôi khi lớn hơn vài pixel so với hằng số ``MIN_*``; dùng chung một
        chỗ để việc kẹp khi kéo và việc kiểm thử luôn khớp nhau.
        """
        hint = self.minimumSizeHint()
        return QSize(
            max(MIN_WIDTH, hint.width()), max(MIN_HEIGHT, hint.height())
        )

    def begin_resize(self, global_pos: QPoint) -> None:
        """Bắt đầu kéo tay nắm ở góc (gọi từ :class:`_ResizeGrip`)."""
        self._resizing = True
        self._resize_start_size = QSize(self.width(), self.height())
        self._resize_start_pos = QPoint(global_pos)
        self._update_overlay_visibility(True)

    def drag_resize(self, global_pos: QPoint) -> None:
        """Kéo tay nắm: đổi kích thước theo độ dịch chuột, có kẹp giới hạn."""
        if not self._resizing:
            return
        delta = global_pos - self._resize_start_pos
        min_size = self._min_size()
        screen = self.screen() or QGuiApplication.primaryScreen()
        max_w, max_h = MAX_WIDTH, MAX_HEIGHT
        if screen is not None:
            avail = screen.availableGeometry()
            max_w = min(max_w, max(MIN_WIDTH, avail.width() - 2 * SHADOW_MARGIN))
            max_h = min(max_h, max(MIN_HEIGHT, avail.height() - 2 * SHADOW_MARGIN))
        width = _clamp_size(
            self._resize_start_size.width() + delta.x(), min_size.width(), max_w
        )
        height = _clamp_size(
            self._resize_start_size.height() + delta.y(), min_size.height(), max_h
        )
        if width != self.width() or height != self.height():
            self.resize(width, height)

    def end_resize(self) -> None:
        """Thả tay nắm: kẹp vào màn hình, lưu kích thước mới."""
        if not self._resizing:
            return
        self._resizing = False
        self._clamp_into_screen()
        self._store_geometry()
        self.settings_changed.emit()

    def reset_size(self) -> None:
        """Trả widget về kích thước chuẩn 344×468."""
        self.resize(BASE_WIDTH, BASE_HEIGHT)
        self._clamp_into_screen()
        self._store_geometry()
        self.settings_changed.emit()

    def _layout_grip(self) -> None:
        """Đặt tay nắm vào góc dưới phải tấm giấy."""
        if not hasattr(self, "_grip"):
            return
        size = styles.px(GRIP_SIZE, min(1.6, self.content_scale()))
        self._grip.setFixedSize(size, size)
        margin = SHADOW_MARGIN
        pad = styles.px(4, self._scale)
        x = self.width() - margin - pad - size
        y = self.height() - margin - pad - size
        self._grip.move(max(0, x), max(0, y))
        self._grip.raise_()

    def _layout_overlay(self) -> None:
        """Đặt hai nút nổi ở góc trên phải tấm giấy."""
        if not hasattr(self, "_overlay"):
            return
        self._overlay.adjustSize()
        margin = SHADOW_MARGIN
        pad = styles.px(6, self._scale)
        w = self._overlay.width()
        h = self._overlay.height()
        x = self.width() - margin - pad - w
        y = margin + pad
        self._overlay.move(max(margin, x), max(margin, y))
        self._overlay.raise_()
        self._layout_grip()

    # --- hai nút nổi chỉ hiện khi rê chuột lên widget ---------------------
    def enterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._update_overlay_visibility(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._update_overlay_visibility(False)
        super().leaveEvent(event)

    def _update_overlay_visibility(self, hovered: bool) -> None:
        """Hiện nút nổi khi rê chuột, ẩn đi khi chuột rời widget.

        Nhờ vậy các nút không che dải gáy của tờ lịch bloc khi đang ngắm widget.
        Người dùng vẫn chuyển chế độ xem được bằng: nháy đúp chuột vào widget,
        menu chuột phải, hoặc menu khay hệ thống.
        """
        if not hasattr(self, "_overlay"):
            return
        visible = (hovered or self._dragging) and self._settings.view == "bloc"
        self._overlay.setVisible(visible)
        if visible:
            self._overlay.raise_()

    def _card_rect(self) -> QRect:
        m = SHADOW_MARGIN
        return QRect(m, m, max(1, self.width() - 2 * m), max(1, self.height() - 2 * m))

    # ------------------------------------------------------------- vẽ bóng
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        """Vẽ bóng đổ mềm quanh tấm giấy (rẻ hơn QGraphicsDropShadowEffect)."""
        if getattr(self, "_pin_look", False):
            # Chế độ ghim: cửa sổ đục, không có lề bóng nên không vẽ bóng.
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self._card_rect()
        radius = self._theme.radius
        shadow = QColor(self._theme.shadow)
        # Bóng đổ cũng mờ đi theo nền (bóng không phải chữ).
        visual = getattr(self, "_visual_theme", self._theme)
        shadow_alpha = alpha_of(visual.paper)
        if shadow_alpha < 0.999:
            painter.setOpacity(shadow_alpha)
        for i in range(6, 0, -1):
            alpha = int(6 + (7 - i) * 4)
            pen = QPen(QColor(shadow.red(), shadow.green(), shadow.blue(), alpha))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-i, -i + 1, i, i + 2), radius + i, radius + i)
        painter.end()

    # ------------------------------------------------------------ độ mờ
    def _apply_opacity(self) -> None:
        """Đặt độ trong suốt.

        * **Cửa sổ nổi** (top-level): độ mờ nhúng vào **màu giấy**, chữ đục
          100 % → đúng yêu cầu "chỉ nền trong, chữ khoá".
        * **Đã ghim desktop** (cửa sổ con của Progman): Windows không ghép
          alpha từng điểm ảnh cho cửa sổ con, nên cửa sổ phải đục hoàn toàn và
          độ mờ được làm bằng ``LWA_ALPHA`` (cả khối mờ đồng đều). Nếu không
          làm vậy, phần trong suốt bị vẽ đè lên nền đen → lịch "biến mất".
        """
        opacity = max(0.2, min(1.0, float(self._settings.opacity)))
        effect = self._stack.graphicsEffect()
        if effect is not None:  # gỡ hiệu ứng mờ của phiên bản cũ (nếu còn)
            self._stack.setGraphicsEffect(None)

        if not getattr(self, "_pin_look", False):
            # Cửa sổ nổi trong suốt: Qt TỰ quản lý WS_EX_LAYERED +
            # UpdateLayeredWindow (alpha từng điểm ảnh). TUYỆT ĐỐI không gỡ
            # WS_EX_LAYERED ở đây – nếu gỡ, lề bóng đổ và 4 góc bo của tờ lịch
            # bị Windows tô ĐEN (lỗi "khung lịch bị viền đen bao quanh").
            self.setWindowOpacity(1.0)
            return

        # Đã ghim (cửa sổ con của Progman). Từ Windows 11 24H2, Progman mang
        # WS_EX_NOREDIRECTIONBITMAP: cửa sổ con KHÔNG layered sẽ không được DWM
        # trình chiếu (lịch "biến mất" nhưng vẫn nhận chuột). Cửa sổ con phải là
        # WS_EX_LAYERED + LWA_ALPHA. Cửa sổ ghim vẽ đục (không có kênh alpha)
        # nên Qt dùng SetLayeredWindowAttributes thay vì UpdateLayeredWindow –
        # không xung đột. Qt chỉ giữ WS_EX_LAYERED cho cửa sổ đục khi
        # opacity < 1.0 (nếu = 1.0 Qt gỡ cờ ở mỗi lần flush) nên kẹp tối đa
        # 254/255 – mắt thường không phân biệt được.
        level = min(opacity, _PINNED_MAX_OPACITY)
        self.setWindowOpacity(level)
        win32 = _win32_module()
        if win32 is None:
            return
        win32.set_layered_alpha(int(self.winId()), level)

    def _ensure_pinned_layered(self) -> None:
        """Watchdog: bảo đảm cửa sổ đã ghim vẫn còn ``WS_EX_LAYERED``."""
        win32 = _win32_module()
        if win32 is None:
            return
        hwnd = int(self.winId())
        exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
        if not (exstyle & win32.WS_EX_LAYERED):
            self._apply_opacity()

    # ------------------------------------------------------- ghim desktop
    def _apply_placement(self) -> None:
        """Ghim/bỏ ghim và giữ nguyên vị trí màn hình của widget.

        Trước khi ghim phải chuyển cửa sổ sang chế độ **đục** (:meth:`_set_pin_look`):
        cửa sổ trong suốt của Qt khi thành cửa sổ con sẽ bị Windows ghép trên
        nền đen khiến lịch "biến mất" (vẫn nhận chuột) – lỗi người dùng báo.
        """
        screen_pos = self.frameGeometry().topLeft()
        want_pin = self._settings.placement == "desktop"
        hwnd = int(self.winId())

        if want_pin:
            self._set_pin_look(True)
            hwnd = int(self.winId())
            ok = desktop_pin.pin(hwnd)
            self._pinned = bool(ok)
            if ok:
                self._pin_failures = 0
                self._apply_opacity()
                self._restore_screen_position(screen_pos)
                desktop_pin.send_to_bottom(hwnd)
            else:
                self._pinned = False
                self._set_pin_look(False)
                self._apply_opacity()
                self._restore_screen_position(screen_pos)
        else:
            if self._pinned:
                desktop_pin.unpin(hwnd)
            self._pinned = False
            self._set_pin_look(False)
            self._apply_opacity()
            self._restore_screen_position(screen_pos)

    def _pin_seems_visible(self) -> bool:
        """Kiểm tra cửa sổ có đang hiển thị."""
        win32 = _win32_module()
        if win32 is None:
            return True
        hwnd = int(self.winId())
        return win32.is_window_visible(hwnd)

    def _ensure_pin_visible(self, screen_pos: QPoint) -> None:
        """Đảm bảo cửa sổ ghim hiển thị và ở đáy z-order."""
        from ..platform import desktop_pin
        hwnd = int(self.winId())
        desktop_pin.send_to_bottom(hwnd)

    def _apply_pin_palette(self, visual: Theme) -> None:
        """Chế độ ghim: tô nền cửa sổ bằng màu giấy **đục** (áp sau QSS)."""
        if not getattr(self, "_pin_look", False):
            return
        paper = QColor(visual.paper)
        paper.setAlpha(255)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, paper)
        palette.setColor(QPalette.ColorRole.Base, paper)
        self.setPalette(palette)

    def _set_pin_look(self, pinned: bool) -> None:
        """Đổi giao diện theo chế độ ghim: đục hoá cửa sổ + bỏ lề bóng đổ.

        ``WA_TranslucentBackground`` chỉ có hiệu lực khi tạo native window nên
        phải **tạo lại** cửa sổ (Qt làm việc này qua ``setWindowFlags``).
        """
        pinned = bool(pinned)
        if getattr(self, "_pin_look", None) == pinned:
            return
        self._pin_look = pinned
        self._visual_theme = None  # buộc tính lại theme theo chế độ mới
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, not pinned)
        layout = self.layout()
        if layout is not None:
            margin = 0 if pinned else SHADOW_MARGIN
            layout.setContentsMargins(margin, margin, margin, margin)
        self.setAutoFillBackground(pinned)

        was_visible = self.isVisible()
        flags = self.windowFlags()
        # Đổi cờ "rỗng" buộc Qt tạo lại native window với thuộc tính mới.
        self.setWindowFlags(flags | Qt.WindowTitleHint)
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
        self._apply_view_embedding(pinned)
        self._apply_theme()
        self._layout_overlay()
        self._layout_grip()
        self.update()

    def _apply_view_embedding(self, pinned: bool) -> None:
        """Ghim desktop ⇒ view phủ kín cửa sổ, KHÔNG vẽ bóng đổ/mép giấy.

        Nếu vẫn để view vẽ bóng, trên nền **đục** của chế độ ghim phần bóng sẽ
        thành một khung tối/near-black quanh lịch – đúng lỗi người dùng gặp.
        """
        bloc = getattr(self, "_bloc", None)
        setter = getattr(bloc, "set_embedded", None)
        if callable(setter):
            setter(True if pinned else None)

    def _restore_screen_position(self, wanted: QPoint) -> None:
        """Sau SetParent, toạ độ Qt có thể bị lệch – kéo về đúng chỗ cũ."""
        from ..platform import win32

        hwnd = int(self.winId())
        rect = win32.get_window_rect(hwnd)
        if not rect:
            self.move(wanted)
            return
        actual = QPoint(rect[0], rect[1])
        delta = actual - wanted
        if not delta.isNull():
            self.move(self.pos() - delta)

    def _watch_pin(self) -> None:
        """Watchdog định kỳ: duy trì cửa sổ ở đáy Z-order (HWND_BOTTOM) và luôn hiển thị."""
        if self._settings.placement != "desktop":
            return

        from ..platform import desktop_pin, win32

        hwnd = int(self.winId())
        if not win32.is_window(hwnd):
            return

        if not desktop_pin.is_pinned(hwnd):
            desktop_pin.pin(hwnd)
            self._pinned = True

        if not win32.is_window_visible(hwnd):
            win32.show_window(hwnd, win32.SW_SHOWNOACTIVATE)

        desktop_pin.send_to_bottom(hwnd)

    def apply_placement(self) -> None:
        """Áp lại cách neo cửa sổ (ghim desktop hoặc cửa sổ nổi)."""
        self._apply_placement()

    def nativeEvent(self, event_type, message):  # noqa: N802 (Qt API)
        """Can thiệp thông điệp Win32 để chống bị ẩn khi bấm Win + D (Rainmeter style)."""
        if event_type == b"windows_generic_MSG" and getattr(self, "_pinned", False):
            from ctypes import wintypes
            from ..platform import desktop_pin, win32

            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == win32.WM_WINDOWPOSCHANGING:
                    if desktop_pin.handle_windowposchanging(msg.lParam):
                        return True, 0
                elif msg.message == win32.WM_SYSCOMMAND:
                    if (msg.wParam & 0xFFF0) == win32.SC_MINIMIZE:
                        return True, 0
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    # -------------------------------------------------------------- kéo thả
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton and not self._settings.lock_position:
            self._dragging = True
            self._drag_moved = False
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._dragging:
            target = event.globalPosition().toPoint() - self._drag_offset
            if (target - self.pos()).manhattanLength() > 2:
                self._drag_moved = True
            self.move(target)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self._clamp_into_screen()
            self._store_geometry()
            self._update_overlay_visibility(self.underMouse())
            self.settings_changed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.LeftButton and not self._drag_moved:
            self.toggle_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _clamp_into_screen(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        card = self._card_rect().translated(self.pos())
        dx = dy = 0
        if card.left() < avail.left():
            dx = avail.left() - card.left()
        elif card.right() > avail.right():
            dx = avail.right() - card.right()
        if card.top() < avail.top():
            dy = avail.top() - card.top()
        elif card.bottom() > avail.bottom():
            dy = avail.bottom() - card.bottom()
        if dx or dy:
            self.move(self.pos() + QPoint(dx, dy))

    def _store_geometry(self) -> None:
        """Lưu vị trí/kích thước.

        Khi đang ghim, ``QWidget.pos()`` là toạ độ tương đối trong cửa sổ cha
        (Progman) chứ không phải toạ độ màn hình, nên phải hỏi Win32 để có
        toạ độ màn hình thật.
        """
        pos = self.pos()
        size_w, size_h = self.width(), self.height()
        if self._pinned:
            from ..platform import win32

            rect = win32.get_window_rect(int(self.winId()))
            if rect:
                pos = QPoint(rect[0], rect[1])
                size_w, size_h = rect[2] - rect[0], rect[3] - rect[1]
        self._settings.x = int(pos.x())
        self._settings.y = int(pos.y())
        self._settings.width = int(size_w)
        self._settings.height = int(size_h)

    def move_to_default_position(self) -> None:
        """Đặt widget ở góc trên phải màn hình chính (lần chạy đầu)."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        m = SHADOW_MARGIN
        x = avail.right() - self.width() - 28
        y = avail.top() + 28
        self.move(max(avail.left() + m, x), max(avail.top() + m, y))
        self._store_geometry()

    def restore_position(self) -> None:
        """Khôi phục vị trí đã lưu; tự đặt mặc định nếu chưa có."""
        x, y = int(self._settings.x), int(self._settings.y)
        if x < -10000 or y < -10000 or (x == -1 and y == -1):
            self.move_to_default_position()
            return
        self.move(x, y)
        self._clamp_into_screen()
        self._store_geometry()

    # -------------------------------------------------------------- menu
    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._show_menu(event.globalPos())

    def _show_menu_at_button(self) -> None:
        pos = self._menu_btn.mapToGlobal(QPoint(0, self._menu_btn.height()))
        self._show_menu(pos)

    def _show_menu(self, global_pos: QPoint) -> None:
        """Menu ngữ cảnh dùng chung cho chuột phải và nút "⋯"."""
        menu = QMenu(self)
        menu.setAttribute(Qt.WA_DeleteOnClose, True)

        act_hide = menu.addAction("Ẩn widget xuống khay")
        act_hide.triggered.connect(self.hide_requested.emit)
        menu.addSeparator()

        # --- chế độ xem
        view_menu = menu.addMenu("Chế độ xem")
        act_bloc = view_menu.addAction("Lịch ngày (bloc)")
        act_bloc.setCheckable(True)
        act_bloc.setChecked(self._settings.view == "bloc")
        act_bloc.triggered.connect(lambda: self.set_view("bloc"))
        act_month = view_menu.addAction("Lịch tháng")
        act_month.setCheckable(True)
        act_month.setChecked(self._settings.view == "month")
        act_month.triggered.connect(lambda: self.set_view("month"))

        # --- độ trong suốt
        opacity_menu = menu.addMenu("Độ trong suốt (nền)")
        for step in OPACITY_STEPS:
            act = opacity_menu.addAction(f"{int(round(step * 100))} %")
            act.setCheckable(True)
            act.setChecked(abs(self._settings.opacity - step) < 0.01)
            act.triggered.connect(lambda _=False, s=step: self.set_opacity(s))

        # --- màu nền giấy
        bg_menu = menu.addMenu("Màu nền giấy")
        act_theme_bg = bg_menu.addAction("Theo giao diện")
        act_theme_bg.setCheckable(True)
        act_theme_bg.setChecked(not self._settings.bg_color)
        act_theme_bg.triggered.connect(lambda: self.set_bg_color(""))
        bg_menu.addSeparator()
        current_bg = (self._settings.bg_color or "").upper()
        for label, hex_color in BACKGROUND_PRESETS:
            act = bg_menu.addAction(f"{label}   {hex_color}")
            act.setCheckable(True)
            act.setChecked(current_bg == hex_color.upper())
            act.triggered.connect(
                lambda _=False, c=hex_color: self.set_bg_color(c)
            )
        bg_menu.addSeparator()
        act_custom = bg_menu.addAction("Màu tuỳ chọn…")
        act_custom.triggered.connect(self._pick_bg_color)

        menu.addSeparator()

        act_pin = menu.addAction("Ghim sát Desktop")
        act_pin.setCheckable(True)
        act_pin.setChecked(self._settings.placement == "desktop")
        act_pin.triggered.connect(lambda checked: self.set_placement(
            "desktop" if checked else "floating"))

        act_top = menu.addAction("Luôn nổi trên cùng")
        act_top.setCheckable(True)
        act_top.setChecked(self._settings.always_on_top)
        act_top.triggered.connect(self.set_always_on_top)

        act_lock = menu.addAction("Khoá vị trí")
        act_lock.setCheckable(True)
        act_lock.setChecked(self._settings.lock_position)
        act_lock.triggered.connect(self.set_lock_position)

        act_start = menu.addAction("Khởi động cùng Windows")
        act_start.setCheckable(True)
        act_start.setChecked(autostart.is_enabled() or self._settings.run_at_startup)
        act_start.triggered.connect(self.set_run_at_startup)

        menu.addSeparator()
        act_today = menu.addAction("Về hôm nay")
        act_today.setEnabled(self._selected is not None)
        act_today.triggered.connect(self.go_today)
        act_reset = menu.addAction("Đặt lại vị trí")
        act_reset.triggered.connect(self.reset_position)
        act_size = menu.addAction(f"Đặt lại kích thước ({BASE_WIDTH}×{BASE_HEIGHT})")
        act_size.setEnabled(
            (self.width(), self.height()) != (BASE_WIDTH, BASE_HEIGHT)
        )
        act_size.triggered.connect(self.reset_size)
        act_settings = menu.addAction("Cài đặt…")
        act_settings.triggered.connect(self.settings_requested.emit)
        act_update = menu.addAction("Kiểm tra bản cập nhật…")
        act_update.triggered.connect(self.update_check_requested.emit)
        menu.addSeparator()
        act_quit = menu.addAction("Thoát")
        act_quit.triggered.connect(self.quit_requested.emit)

        menu.exec(global_pos)

    def _pick_bg_color(self) -> None:
        """Mở bảng chọn màu cho nền giấy (không chọn alpha – alpha do thanh độ mờ)."""
        from PySide6.QtWidgets import QColorDialog

        visual = getattr(self, "_visual_theme", self._theme)
        start = QColor(self._settings.bg_color or visual.paper)
        color = QColorDialog.getColor(start, self, "Chọn màu nền giấy")
        if color.isValid():
            self.set_bg_color(color.name())

    def reset_position(self) -> None:
        """Đưa widget về góc trên phải màn hình chính."""
        self.move_to_default_position()
        self.settings_changed.emit()

    # ------------------------------------------------- API cho controller
    def set_opacity(self, value: float) -> None:
        """Đổi độ trong suốt **chỉ của phần nền** (chữ luôn đục 100 %)."""
        self._settings.opacity = max(0.2, min(1.0, float(value)))
        self._apply_theme()
        self._apply_opacity()
        self.settings_changed.emit()

    def set_bg_color(self, color: str) -> None:
        """Đổi màu nền giấy (``""`` = theo giao diện đang chọn)."""
        self._settings.bg_color = str(color or "").strip()
        self._settings.clamp()
        self._apply_theme()
        self.settings_changed.emit()

    def set_theme_name(self, name: str) -> None:
        self._settings.theme = name
        self._theme = get_theme(name)
        self._apply_theme()
        self.settings_changed.emit()

    def set_placement(self, placement: str) -> None:
        if placement not in ("desktop", "floating"):
            return
        # Đổi window flags trong lúc đang ghim sẽ làm Windows reset style
        # (mất WS_CHILD) ⇒ luôn bỏ ghim trước rồi ghim lại sau.
        self._unpin_before_flag_change()
        self._settings.placement = placement
        self._apply_window_flags()
        self.show()
        self._apply_placement()
        self._apply_theme()
        self.settings_changed.emit()

    def set_always_on_top(self, checked: bool) -> None:
        """Bật/tắt "luôn nổi trên cùng".

        Chế độ này chỉ có nghĩa với cửa sổ nổi; nếu đang ghim desktop thì
        tự chuyển sang cửa sổ nổi (vì cửa sổ con của Progman không thể nổi
        trên các cửa sổ khác).
        """
        self._unpin_before_flag_change()
        if checked and self._settings.placement == "desktop":
            self._settings.placement = "floating"
        self._settings.always_on_top = bool(checked)
        self._apply_window_flags()
        self.show()
        self._apply_placement()
        self.settings_changed.emit()

    def _unpin_before_flag_change(self) -> None:
        """Bỏ ghim (nếu đang ghim) trước khi Qt thay đổi window flags."""
        if not self._pinned:
            return
        from ..platform import win32

        hwnd = int(self.winId())
        screen_pos = self.frameGeometry().topLeft()
        if win32.get_window_rect(hwnd):
            rect = win32.get_window_rect(hwnd)
            if rect:
                screen_pos = QPoint(rect[0], rect[1])
        desktop_pin.unpin(hwnd)
        self._pinned = False
        self._settings.x = int(screen_pos.x())
        self._settings.y = int(screen_pos.y())

    def set_lock_position(self, checked: bool) -> None:
        self._settings.lock_position = bool(checked)
        self.settings_changed.emit()

    def set_run_at_startup(self, checked: bool) -> None:
        ok = autostart.set_enabled(bool(checked))
        self._settings.run_at_startup = bool(checked) if ok else autostart.is_enabled()
        self.settings_changed.emit()

    def set_quote_mode(self, mode: str) -> None:
        self._settings.quote_mode = "random" if mode == "random" else "daily"
        self._refresh_content()
        self.settings_changed.emit()

    def set_scale(self, scale: float) -> None:
        scale = max(0.75, min(2.0, float(scale)))
        if abs(scale - self._settings.scale) < 0.001:
            return
        ratio = scale / self._settings.scale if self._settings.scale else 1.0
        self._settings.scale = scale
        self._settings.width = int(round(self._settings.width * ratio))
        self._settings.height = int(round(self._settings.height * ratio))
        self._scale = scale
        self._apply_theme()
        self._resize_to_settings()
        self._clamp_into_screen()
        self._store_geometry()
        self.settings_changed.emit()

    def show_message(self, title: str, text: str) -> None:
        """Hiện thông báo nhỏ trong cửa sổ (dùng khi khay hệ thống không có)."""
        from PySide6.QtWidgets import QToolTip

        QToolTip.showText(self.mapToGlobal(QPoint(0, 0)), f"{title}\n{text}", self)

    # --------------------------------------------------------------- đóng
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._settings.hidden = True
        self._store_geometry()
        self.settings_changed.emit()
        event.ignore()  # ứng dụng chỉ ẩn, không thoát
