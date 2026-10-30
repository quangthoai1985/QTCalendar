"""Cửa sổ widget chính – không viền, kéo thả tự do, ghim sát Desktop.

Trách nhiệm
===========

* Dựng khung cửa sổ trong suốt, không viền, không thanh tiêu đề.
* Xếp dọc :class:`~qtcalendar.ui.bloc_view.BlocView` (lịch ngày) và – khi
  người dùng bật – :class:`~qtcalendar.ui.month_view.MonthView` (lịch tháng)
  ngay dưới chân tờ bloc; widget dài thêm xuống dưới.
* Kéo thả bằng chuột trái, tự lưu toạ độ khi thả, tự kẹp vào màn hình.
* Áp dụng độ trong suốt, bảng màu, tỉ lệ nội dung.
* Ghim cửa sổ xuống mặt bàn Desktop (``SetParent(Progman)``) và có watchdog
  tự ghim lại nếu Explorer khởi động lại.
* Menu ngữ cảnh chuột phải + nút menu nổi ở góc trên; tab kéo ở chân để
  bật/tắt lịch tháng (:class:`~qtcalendar.ui.month_tab.MonthTab`).

Việc mở hộp thoại cài đặt, lưu tệp cấu hình, khay hệ thống do ``app.py``
(tầng điều phối) đảm nhận – widget chỉ phát tín hiệu.

Tín hiệu
========

``settings_changed``
    Có thay đổi cần lưu (vị trí, độ mờ, bật/tắt lịch tháng, ghim…).
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

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
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
from .month_tab import MonthTab
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
    "MONTH_RATIO",
    "MONTH_GAP_BASE",
    "TAB_STRIP_BASE",
    "month_extra_height",
    "tab_strip_height",
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

#: Lịch tháng dưới chân bloc: chiều cao tờ lịch tháng = bề rộng giấy × hệ số.
#: Không phụ thuộc tháng có 5 hay 6 hàng ⇒ widget không nhảy cỡ khi đổi tháng.
MONTH_RATIO = 1.15

#: Khe giữa tờ bloc và tờ lịch tháng (design-pixel, phóng theo bề rộng).
MONTH_GAP_BASE = 6

#: Dải đáy dành cho tab kéo bật/tắt lịch tháng (design-pixel). Nằm trong
#: ``Settings.height`` nên khi lịch tháng đóng, khung widget không đổi cỡ.
TAB_STRIP_BASE = 12

#: Các mức độ trong suốt trong menu nhanh.
OPACITY_STEPS = (1.00, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20)

#: Cạnh của tay nắm kéo giãn ở góc dưới phải (pixel logic).
GRIP_SIZE = 18

#: Độ đục tối đa khi đã ghim desktop (254/255). Phải < 1.0 để Qt giữ
#: ``WS_EX_LAYERED`` – điều kiện bắt buộc để cửa sổ con của Progman hiển thị
#: trên Windows 11 24H2 trở lên.
_PINNED_MAX_OPACITY = 254.0 / 255.0


def _width_ratio(width: int, scale: float) -> float:
    """Hệ số phóng chỉ theo bề rộng – dùng cho khe và dải đáy.

    Không dùng :meth:`CalendarWidget.content_scale` (phụ thuộc chiều cao bloc,
    mà chiều cao bloc lại phụ thuộc dải đáy ⇒ vòng lặp khi kéo giãn).
    """
    return max(0.5, min(2.6, float(scale) * width / float(BASE_WIDTH)))


def _month_gap_height(width: int, scale: float) -> int:
    """Khe giữa hai tờ giấy."""
    return styles.px(MONTH_GAP_BASE, _width_ratio(width, scale))


def _month_sheet_height(width: int) -> int:
    """Chiều cao tờ lịch tháng theo bề rộng tờ giấy."""
    return int(round((width - 2 * SHADOW_MARGIN) * MONTH_RATIO))


def month_extra_height(width: int, scale: float) -> int:
    """Phần widget cao thêm khi mở lịch tháng (khe + tờ lịch tháng)."""
    return _month_gap_height(width, scale) + _month_sheet_height(width)


def tab_strip_height(content_scale: float) -> int:
    """Chiều cao dải đáy dành cho tab kéo."""
    return styles.px(TAB_STRIP_BASE, content_scale)


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
        self._resize_to_settings()
        self.set_show_month(self._settings.show_month)

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
        """Dựng cột dọc bloc → (khe → lịch tháng) → dải đáy + hai nút nổi."""
        margin = SHADOW_MARGIN
        layout = QVBoxLayout(self)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(0)

        self._bloc = BlocView(self)
        layout.addWidget(self._bloc, 1)

        # Khe giữa hai tờ giấy – chỉ hiện khi lịch tháng mở.
        self._month_gap = QWidget(self)
        self._month_gap.setObjectName("MonthGap")
        self._month_gap.setFixedHeight(0)
        self._month_gap.hide()
        layout.addWidget(self._month_gap)

        # Lịch tháng được tạo **lười** ở lần đầu người dùng mở nó (chèn vào
        # layout ở vị trí 2). Lý do: dựng 42 ô ngày khiến Qt khởi tạo cache đo
        # chữ/elide của Windows, tốn thêm ~70 MB – không đáng phải trả khi đa
        # số người dùng chỉ dùng lịch ngày.
        self._month: MonthView | None = None

        # Dải đáy cho tab kéo bật/tắt lịch tháng.
        self._tab_strip = QWidget(self)
        self._tab_strip.setObjectName("TabStrip")
        self._tab_strip.setFixedHeight(tab_strip_height(1.0))
        layout.addWidget(self._tab_strip)

        # Nút nổi menu nhanh (bật/tắt lịch tháng nay do tab kéo ở chân đảm nhận)
        self._overlay = QWidget(self)
        self._overlay.setObjectName("Overlay")
        overlay_layout = QHBoxLayout(self._overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(6)

        # Dấu ba chấm dùng U+2026 (có sẵn trong Segoe UI). TUYỆT ĐỐI không dùng
        # các ký tự tượng hình như U+22EF "⋯", U+25B8 "▸", U+2699 "⚙": khi
        # Windows không tìm thấy glyph trong font hiện tại, DirectWrite phải
        # nạp cả bộ font dự phòng – tốn thêm ~85 MB RAM (đã đo thực nghiệm).
        self._menu_btn = QPushButton("\u2026", self._overlay)
        self._menu_btn.setObjectName("MenuButton")
        self._menu_btn.setCursor(Qt.PointingHandCursor)
        self._menu_btn.setToolTip("Menu nhanh")
        self._menu_btn.clicked.connect(self._show_menu_at_button)

        overlay_layout.addWidget(self._menu_btn)
        self._overlay.adjustSize()
        self._overlay.hide()  # chỉ hiện khi rê chuột lên widget

        # Tay nắm kéo giãn ở góc dưới phải – luôn hiện để người dùng dễ thấy.
        self._grip = _ResizeGrip(self)
        self._grip.setObjectName("ResizeGrip")

        # Tab kéo bật/tắt lịch tháng – treo dưới mép tờ giấy cuối cùng, đặt
        # tuyệt đối (không nằm trong layout). Theo dõi vị trí/kích thước của
        # các tờ giấy để luôn bám đúng mép, kể cả khi layout cập nhật trễ.
        self._tab = MonthTab(self)
        self._tab.toggled.connect(self.toggle_month)
        self._bloc.installEventFilter(self)

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
            self.bloc_height() / float(BASE_HEIGHT),
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
        """Độ mờ áp vào **màu giấy** (nền trong suốt, chữ đục 100%)."""
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
        self._tab.apply_theme(visual, scale)
        self._apply_sheet_heights()
        self._layout_overlay()
        self._layout_grip()

    # ------------------------------------------------------- lịch tháng (lười)
    def _ensure_month(self) -> MonthView:
        """Tạo lịch tháng ở lần dùng đầu tiên rồi nối tín hiệu."""
        if self._month is not None:
            return self._month
        month = MonthView(self)
        month.hide()
        month.installEventFilter(self)
        self.layout().insertWidget(2, month)
        self._month = month

        month.day_activated.connect(self._on_day_activated)
        month.month_changed.connect(self._on_month_changed)
        month.today_requested.connect(self.go_today)

        month.apply_theme(self._visual(), self.content_scale())
        month.set_selected(self._selected)
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
        if self._month is not None:
            # Ô của ngày đang xem ở bloc được viền nhấn (None = hôm nay).
            self._month.set_selected(self._selected)

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
    def set_show_month(self, flag: bool) -> None:
        """Bật/tắt lịch tháng ngay dưới chân lịch bloc.

        Mọi lối vào (tab, nháy đúp, menu chuột phải, khay, Cài đặt) đều đi về
        đây. So với trạng thái **hiển thị thực tế** chứ không so với
        ``settings.show_month``: lúc khởi động và khi áp Cài đặt, giá trị đó đã
        được ghi trước khi gọi hàm này.
        """
        flag = bool(flag)
        shown = self._month is not None and not self._month.isHidden()
        if shown == flag and self._settings.show_month == flag:
            return
        self._settings.show_month = flag
        if flag:
            self._ensure_month()
            self._sync_month_view()
        if self._month is not None:
            self._month.setVisible(flag)
        self._month_gap.setVisible(flag)
        self._tab.set_open(flag)
        self._apply_sheet_heights()
        # Kích hoạt layout trước để cửa sổ nhận kích thước tối thiểu mới (khi
        # đóng lịch tháng, nếu không làm vậy Qt kẹp resize ở mức tối thiểu cũ).
        self.layout().activate()
        self._resize_to_settings()
        self.layout().activate()
        if flag and self.isVisible():
            self._fit_into_screen()
        self._layout_overlay()
        self.update()
        self.settings_changed.emit()

    def toggle_month(self) -> None:
        self.set_show_month(not self._settings.show_month)

    # ------------------------------------------------------------- hình học
    def extra_height(self) -> int:
        """Phần widget cao thêm do lịch tháng (0 khi lịch tháng đóng)."""
        if not self._settings.show_month:
            return 0
        return month_extra_height(self.width(), self._settings.scale)

    def bloc_height(self) -> int:
        """Chiều cao phần bloc (gồm lề bóng) = ``Settings.height`` khi lưu."""
        return self.height() - self.extra_height()

    def _apply_sheet_heights(self, width: int | None = None) -> None:
        """Đặt chiều cao cố định cho dải đáy, khe và tờ lịch tháng.

        Truyền ``width`` (bề rộng sắp resize tới) rồi ``layout().activate()``
        *trước* khi resize: kích thước tối thiểu của cửa sổ phụ thuộc các chiều
        cao này, nếu để cũ Qt sẽ kẹp resize ở mức tối thiểu cũ.
        """
        if not hasattr(self, "_tab_strip"):
            return
        width = self.width() if width is None else int(width)
        self._tab_strip.setFixedHeight(
            tab_strip_height(_width_ratio(width, self._settings.scale))
        )
        if self._month is not None and self._settings.show_month:
            self._month_gap.setFixedHeight(
                _month_gap_height(width, self._settings.scale)
            )
            self._month.setFixedHeight(_month_sheet_height(width))

    def _sheet_rects(self) -> list[QRect]:
        """Các tờ giấy đang hiện (toạ độ cửa sổ): bloc, và lịch tháng nếu mở."""
        rects = [self._bloc.geometry()]
        if self._month is not None and not self._month.isHidden():
            rects.append(self._month.geometry())
        return rects

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
        if hasattr(self, "_tab"):
            self._tab.apply_theme(visual, content_scale)
            self._layout_tab()
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
        QPushButton#MenuButton {{
            color: {theme.ink_soft};
            background: {theme.chip_bg};
            border: 1px solid {theme.line};
            border-radius: {radius}px;
            padding: {pad_v}px {pad_h}px;
            font-size: {f}px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QPushButton#MenuButton:hover {{
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
        self._menu_btn.adjustSize()

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
        self.set_show_month(self._settings.show_month)
        self._apply_placement()
        self._refresh_content()

    def _resize_to_settings(self) -> None:
        """Đặt kích thước theo cấu hình: bloc ``width × height`` + lịch tháng nếu mở."""
        w = _clamp_size(self._settings.width, MIN_WIDTH, MAX_WIDTH)
        h = _clamp_size(self._settings.height, MIN_HEIGHT, MAX_HEIGHT)
        self._settings.width = w
        self._settings.height = h
        total = h
        if self._settings.show_month:
            total += month_extra_height(w, self._settings.scale)
        if self.width() != w or self.height() != total:
            self._apply_sheet_heights(w)
            self.layout().activate()
            self.resize(w, total)

    def sizeHint(self) -> QSize:  # pragma: no cover - Qt hint
        return QSize(self._settings.width, self._settings.height)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._layout_overlay()
        self._layout_grip()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._apply_sheet_heights()
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
        self._resize_start_size = QSize(self.width(), self.bloc_height())
        self._resize_start_pos = QPoint(global_pos)
        self._update_overlay_visibility(True)

    def drag_resize(self, global_pos: QPoint) -> None:
        """Kéo tay nắm: đổi kích thước theo độ dịch chuột, có kẹp giới hạn.

        Kéo ngang đổi bề rộng (cả hai lịch to/nhỏ theo); kéo dọc chỉ đổi chiều
        cao **bloc** – phần lịch tháng luôn tính lại từ bề rộng.
        """
        if not self._resizing:
            return
        delta = global_pos - self._resize_start_pos
        min_size = self._min_size()
        avail = self._available_rect()
        max_w = MAX_WIDTH
        if avail is not None:
            max_w = min(max_w, max(MIN_WIDTH, avail.width() - 2 * SHADOW_MARGIN))
        width = _clamp_size(
            self._resize_start_size.width() + delta.x(), min_size.width(), max_w
        )
        # Dải đáy co theo bề rộng ⇒ chiều cao tối thiểu đổi theo; tính lại
        # sau khi đã áp chiều cao dải đáy cho bề rộng mới.
        self._apply_sheet_heights(width)
        self.layout().activate()
        extra = (
            month_extra_height(width, self._settings.scale)
            if self._settings.show_month
            else 0
        )
        min_bloc = max(MIN_HEIGHT, self._min_size().height() - extra)
        max_bloc = MAX_HEIGHT
        if avail is not None:
            max_bloc = min(
                max_bloc, max(min_bloc, avail.height() - 2 * SHADOW_MARGIN - extra)
            )
        bloc_h = _clamp_size(
            self._resize_start_size.height() + delta.y(), min_bloc, max_bloc
        )
        height = bloc_h + extra
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
        """Trả bloc về kích thước chuẩn 344×468 (lịch tháng giữ nguyên trạng thái)."""
        self._settings.width = BASE_WIDTH
        self._settings.height = BASE_HEIGHT
        self._resize_to_settings()
        if self._settings.show_month:
            self._fit_into_screen()
        else:
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
        self._layout_tab()

    def _layout_tab(self) -> None:
        """Treo tab kéo dưới mép tờ giấy cuối cùng (bloc, hoặc lịch tháng nếu mở)."""
        if not hasattr(self, "_tab"):
            return
        last = self._sheet_rects()[-1]
        top = last.bottom() + 1
        height = max(1, self.height() - top)
        width = self._tab.sizeHint().width()
        self._tab.setGeometry(last.center().x() - width // 2 + 1, top, width, height)
        self._tab.raise_()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt API)
        if event.type() in (QEvent.Type.Move, QEvent.Type.Resize) and watched in (
            self._bloc,
            self._month,
        ):
            self._layout_tab()
        return super().eventFilter(watched, event)

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
        visible = hovered or self._dragging
        self._overlay.setVisible(visible)
        if visible:
            self._overlay.raise_()

    def _card_rect(self) -> QRect:
        m = SHADOW_MARGIN
        return QRect(m, m, max(1, self.width() - 2 * m), max(1, self.height() - 2 * m))

    # ------------------------------------------------------------- vẽ bóng
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        """Vẽ bóng đổ mềm quanh từng tờ giấy (rẻ hơn QGraphicsDropShadowEffect)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        radius = self._theme.radius
        shadow = QColor(self._theme.shadow)
        # Bóng đổ cũng mờ đi theo nền (bóng không phải chữ).
        visual = getattr(self, "_visual_theme", self._theme)
        shadow_alpha = alpha_of(visual.paper)
        if shadow_alpha < 0.999:
            painter.setOpacity(shadow_alpha)
        painter.setBrush(Qt.NoBrush)
        for rect in self._sheet_rects():
            for i in range(6, 0, -1):
                alpha = int(6 + (7 - i) * 4)
                pen = QPen(QColor(shadow.red(), shadow.green(), shadow.blue(), alpha))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawRoundedRect(
                    rect.adjusted(-i, -i + 1, i, i + 2), radius + i, radius + i
                )
        painter.end()

    # ------------------------------------------------------------ độ mờ
    def _apply_opacity(self) -> None:
        """Đặt độ trong suốt.

        Cả cửa sổ nổi lẫn ghim Desktop theo chuẩn Rainmeter đều là Top-Level Window:
        độ mờ nhúng thẳng vào **màu giấy**, chữ đục 100%. Qt tự quản lý WS_EX_LAYERED
        + UpdateLayeredWindow (alpha từng điểm ảnh), giữ góc bo tròn và bóng đổ hoàn
        hảo, tuyệt đối không có quầng đen quanh khung lịch.
        """
        for view in (self._bloc, self._month):
            if view is not None and view.graphicsEffect() is not None:
                view.setGraphicsEffect(None)
        self.setWindowOpacity(1.0)

    def _ensure_pinned_layered(self) -> None:
        """Watchdog: bảo đảm cửa sổ giữ nguyên cấu hình hiển thị."""
        pass

    # ------------------------------------------------------- ghim desktop
    def _apply_placement(self) -> None:
        """Ghim/bỏ ghim theo cơ chế Rainmeter Top-Level."""
        screen_pos = self.frameGeometry().topLeft()
        want_pin = self._settings.placement == "desktop"
        hwnd = int(self.winId())

        if want_pin:
            self._pin_look = False
            ok = desktop_pin.pin(hwnd)
            self._pinned = bool(ok)
            if ok:
                self._pin_failures = 0
                desktop_pin.update_z_order(hwnd)
        else:
            if self._pinned:
                desktop_pin.unpin(hwnd)
            self._pinned = False
            self._pin_look = False

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
        """Không thay đổi palette khi ghim vì luôn giữ độ trong suốt tự nhiên."""
        pass

    def _set_pin_look(self, pinned: bool) -> None:
        """Giữ tương thích API: cơ chế Rainmeter luôn giữ nguyên WA_TranslucentBackground."""
        self._pin_look = bool(pinned)

    def _apply_view_embedding(self, pinned: bool) -> None:
        """Giữ tương thích API."""
        pass

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
        """Watchdog định kỳ: duy trì cửa sổ ở vị trí chuẩn theo cơ chế Rainmeter."""
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

        desktop_pin.update_z_order(hwnd)

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
        # Nháy đúp lan lên từ lịch tháng (ô ngày, tiêu đề…) là thao tác trong
        # lịch tháng – không được đóng lịch tháng.
        in_month = self._month is not None and not self._month.isHidden() and (
            self._month.geometry().contains(event.position().toPoint())
        )
        if event.button() == Qt.LeftButton and not self._drag_moved and not in_month:
            self.toggle_month()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _available_rect(self) -> QRect | None:
        """Vùng làm việc (trừ taskbar) của màn hình chứa widget."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def _fit_into_screen(self) -> None:
        """Thu nhỏ (nếu cao hơn màn hình) rồi dời widget vào vùng làm việc.

        Chỉ cần khi lịch tháng đang mở: bề rộng và chiều cao bloc cùng giảm
        theo một tỉ lệ cho tới khi cả hai lịch vừa chiều cao màn hình. Kích
        thước mới được lưu lại.
        """
        avail = self._available_rect()
        if avail is None:
            return
        limit = avail.height()
        if self.height() - 2 * SHADOW_MARGIN > limit:
            w0, h0 = self._settings.width, self._settings.height
            scale = self._settings.scale
            w, h = w0, h0
            factor = 1.0
            while factor > 0.3:
                factor -= 0.01
                w, h = int(round(w0 * factor)), int(round(h0 * factor))
                if w <= MIN_WIDTH or h <= MIN_HEIGHT:
                    w, h = max(w, MIN_WIDTH), max(h, MIN_HEIGHT)
                    break
                if h + month_extra_height(w, scale) <= limit:
                    break
            self._settings.width, self._settings.height = w, h
            self._resize_to_settings()
            self._store_geometry()
        self._clamp_into_screen()

    def _clamp_into_screen(self) -> None:
        avail = self._available_rect()
        if avail is None:
            return
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
        """Lưu vị trí/kích thước (chiều cao = phần bloc, không gồm lịch tháng).

        Ghim kiểu Rainmeter vẫn giữ cửa sổ top-level nên toạ độ Qt luôn là toạ
        độ màn hình **logic** – không dùng ``GetWindowRect`` (pixel vật lý, lớn
        hơn khi Windows đặt tỉ lệ hiển thị 125 % / 150 %).
        """
        pos = self.pos()
        size_w, size_h = self.width(), self.bloc_height()
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
        if self._settings.show_month:
            self._fit_into_screen()
        else:
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

        # --- lịch tháng dưới chân bloc
        act_month = menu.addAction("Hiện lịch tháng")
        act_month.setCheckable(True)
        act_month.setChecked(self._settings.show_month)
        act_month.triggered.connect(self.set_show_month)

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
            (self._settings.width, self._settings.height) != (BASE_WIDTH, BASE_HEIGHT)
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
