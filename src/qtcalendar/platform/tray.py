"""Icon khay hệ thống và menu ngữ cảnh.

Đây là module **duy nhất** của tầng ``platform`` dùng Qt (vì khay hệ thống
của Qt là ``QSystemTrayIcon``). Phần giao diện thật của menu vẫn khai báo
bằng ``QMenu``/``QAction`` thuần, không cần file ``.ui``.

Hợp đồng API
------------

``class TrayIcon(QObject)``
    Tín hiệu (``Signal``) mà ``app.py`` kết nối:

    ==========================  ==============================  =====================
    Tín hiệu                    Tham số                         Ý nghĩa
    ==========================  ==============================  =====================
    ``toggled_visibility``      –                               ẩn/hiện widget
    ``settings_requested``      –                               mở hộp thoại cài đặt
    ``quit_requested``          –                               thoát ứng dụng
    ``view_requested``          ``str`` ("bloc"/"month")        đổi chế độ xem
    ``opacity_requested``       ``float``                       đặt độ trong suốt
    ``pin_toggled``             ``bool``                        ghim/bỏ ghim desktop
    ``topmost_toggled``         ``bool``                        luôn nổi trên cùng
    ``lock_toggled``            ``bool``                        khoá vị trí
    ``autostart_toggled``       ``bool``                        khởi động cùng Windows
    ``today_requested``         –                               về hôm nay
    ``reset_position_requested``–                               đặt lại vị trí
    ==========================  ==============================  =====================

    Phương thức:

    ``__init__(icon: QIcon | str | Path | None = None, parent=None)``
    ``set_state(settings)``
        Đồng bộ dấu tick/trạng thái menu theo ``Settings`` hiện tại.
    ``set_visibility_checked(bool)``
    ``show_message(title, text, msecs=3000)``
        Balloon/tooltip hệ thống (dùng khi ẩn cửa sổ).
    ``show()`` / ``hide()``
    ``is_available() -> bool``
        ``QSystemTrayIcon.isSystemTrayAvailable()``.

Cấu trúc menu bắt buộc::

    Hiện/Ẩn lịch                      (Ctrl+Alt+L)
    ─────────────
    Chế độ xem            ▸  Lịch ngày (bloc) / Lịch tháng
    Độ trong suốt        ▸  100% 90% 80% 70% 60% 50% 40% 30% 20%
    ─────────────
    ☑ Ghim sát Desktop               (mặc định bật)
    ☐ Luôn nổi trên cùng
    ☐ Khoá vị trí
    ☑ Khởi động cùng Windows
    ─────────────
    Về hôm nay
    Đặt lại vị trí
    Cài đặt…
    ─────────────
    Thoát

Ghi chú triển khai
------------------
* Icon mặc định lấy từ ``<gốc dự án>/assets/icon.ico`` (fallback
  ``assets/icon.png``). Khi chưa có file nào, dùng ``QIcon()`` rỗng và ghi
  log – app có thể gọi lại với icon thật sau.
* Toàn bộ thao tác dựng menu/khay được bọc ``try/except``: nếu Qt không có
  khay hệ thống (môi trường offscreen/CI), đối tượng vẫn tạo được và các
  phương thức trả ``False`` thay vì ném lỗi.
* ``set_state()`` chặn tín hiệu bằng cờ ``_syncing`` để việc đồng bộ menu
  không phát ngược tín hiệu về ``app.py`` (tránh vòng lặp sự kiện).
"""

from __future__ import annotations

import logging
import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import APP_NAME
from . import autostart

__all__ = ["TrayIcon", "OPACITY_STEPS"]

log = logging.getLogger(__name__)

#: Các mức độ trong suốt hiển thị trong menu (giảm dần).
OPACITY_STEPS: tuple[float, ...] = (
    1.00,
    0.90,
    0.80,
    0.70,
    0.60,
    0.50,
    0.40,
    0.30,
    0.20,
)

_SHORTCUT_TOGGLE = "Ctrl+Alt+L"


# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------


def _asset_root() -> Path | None:
    """Thư mục gốc để tìm ``assets/`` (khi chạy nguồn hoặc khi đóng gói)."""
    try:
        meipass = getattr(sys, "_MEIPASS", None)  # PyInstaller
        if meipass:
            return Path(meipass)
        if getattr(sys, "frozen", False):  # pragma: no cover - khi đóng gói
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[3]
    except (OSError, IndexError):
        return None


def _default_icon() -> QIcon:
    """Icon mặc định từ ``assets/``; trả ``QIcon()`` rỗng nếu thiếu."""
    root = _asset_root()
    if root is not None:
        for name in ("icon.ico", "icon.png"):
            try:
                candidate = root / "assets" / name
                if candidate.is_file():
                    icon = QIcon(str(candidate))
                    if not icon.isNull():
                        return icon
            except OSError:
                continue
    log.info("Chưa có assets/icon.ico – dùng QIcon() rỗng (khay có thể vô hình)")
    return QIcon()


def _resolve_icon(icon: object) -> QIcon:
    """Chuẩn hoá tham số ``icon`` (QIcon | str | Path | None) về ``QIcon``."""
    try:
        if isinstance(icon, QIcon):
            return icon
        if icon is not None:
            try:
                path = Path(str(icon))
                if path.is_file():
                    loaded = QIcon(str(path))
                    if not loaded.isNull():
                        return loaded
                log.warning("Không nạp được icon từ %r – dùng icon mặc định", icon)
            except (OSError, ValueError, TypeError):
                log.warning("Đường dẫn icon không hợp lệ: %r", icon)
        return _default_icon()
    except Exception:  # pragma: no cover - phòng hờ
        log.warning("_resolve_icon thất bại", exc_info=True)
        try:
            return QIcon()
        except Exception:
            return None  # type: ignore[return-value]


def _nearest_opacity(value: object) -> float:
    """Chọn mức trong suốt gần nhất trong :data:`OPACITY_STEPS`."""
    try:
        opacity = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.00
    if opacity != opacity:  # NaN
        return 1.00
    return min(OPACITY_STEPS, key=lambda step: abs(step - opacity))


# ---------------------------------------------------------------------------
# TrayIcon
# ---------------------------------------------------------------------------


class TrayIcon(QObject):
    """Icon khay hệ thống + menu ngữ cảnh cho QT Calendar."""

    toggled_visibility = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    view_requested = Signal(str)
    opacity_requested = Signal(float)
    pin_toggled = Signal(bool)
    topmost_toggled = Signal(bool)
    lock_toggled = Signal(bool)
    autostart_toggled = Signal(bool)
    today_requested = Signal()
    reset_position_requested = Signal()
    update_check_requested = Signal()

    def __init__(self, icon: QIcon | str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._syncing = False
        self._visible = True

        #: Đối tượng khay Qt (``None`` nếu dựng thất bại).
        self.tray: QSystemTrayIcon | None = None
        #: Menu ngữ cảnh (``None`` nếu dựng thất bại).
        self.menu: QMenu | None = None

        # Các QAction công khai để ``app.py``/hộp thoại có thể tham chiếu.
        self.action_show: QAction | None = None
        self.action_view_bloc: QAction | None = None
        self.action_view_month: QAction | None = None
        self.action_pin: QAction | None = None
        self.action_topmost: QAction | None = None
        self.action_lock: QAction | None = None
        self.action_autostart: QAction | None = None
        self.action_today: QAction | None = None
        self.action_reset: QAction | None = None
        self.action_settings: QAction | None = None
        self.action_quit: QAction | None = None
        #: Danh sách ``(mức_opacity, QAction)`` theo đúng thứ tự menu.
        self.opacity_actions: list[tuple[float, QAction]] = []

        self._view_group: QActionGroup | None = None
        self._opacity_group: QActionGroup | None = None

        self._icon = _resolve_icon(icon)
        self._build_menu()
        self._build_tray()
        self.show()

    # -- dựng giao diện ----------------------------------------------------

    def _make_checkable(
        self,
        parent: QMenu,
        text: str,
        checked: bool = False,
    ) -> QAction:
        action = QAction(text, parent)
        action.setCheckable(True)
        action.setChecked(bool(checked))
        parent.addAction(action)
        return action

    def _build_menu(self) -> None:
        """Dựng cây menu đúng như docstring (chịu lỗi, không ném ra ngoài)."""
        try:
            if QApplication.instance() is None:  # pragma: no cover - dùng sai
                log.warning("TrayIcon cần QApplication trước khi dựng menu")
                return
            menu = QMenu()
            menu.setToolTipsVisible(True)

            # 1) Hiện/Ẩn lịch
            act_show = QAction("Hiện/Ẩn lịch", menu)
            act_show.setShortcut(QKeySequence(_SHORTCUT_TOGGLE))
            act_show.setToolTip(f"Ẩn/hiện cửa sổ lịch ({_SHORTCUT_TOGGLE})")
            act_show.triggered.connect(self._on_toggle_visibility)
            menu.addAction(act_show)
            self.action_show = act_show

            menu.addSeparator()

            # 2) Chế độ xem (radio)
            view_menu = menu.addMenu("Chế độ xem")
            self._view_group = QActionGroup(view_menu)
            self._view_group.setExclusive(True)
            self.action_view_bloc = self._make_checkable(view_menu, "Lịch ngày (bloc)", True)
            self.action_view_month = self._make_checkable(view_menu, "Lịch tháng", False)
            for action, mode in (
                (self.action_view_bloc, "bloc"),
                (self.action_view_month, "month"),
            ):
                self._view_group.addAction(action)
                action.triggered.connect(partial(self._on_view_action, mode))

            # 3) Độ trong suốt nền (radio) – chữ luôn đục 100 %
            opacity_menu = menu.addMenu("Độ trong suốt nền")
            self._opacity_group = QActionGroup(opacity_menu)
            self._opacity_group.setExclusive(True)
            self.opacity_actions = []
            for step in OPACITY_STEPS:
                action = self._make_checkable(
                    opacity_menu, f"{int(round(step * 100))}%", step >= 1.0
                )
                self._opacity_group.addAction(action)
                action.triggered.connect(partial(self._on_opacity_action, step))
                self.opacity_actions.append((step, action))

            menu.addSeparator()

            # 4) Hành vi cửa sổ
            self.action_pin = self._make_checkable(menu, "Ghim sát Desktop", True)
            self.action_pin.setToolTip("Ghim cửa sổ xuống mặt bàn, sống sót qua Win+D")
            self.action_pin.toggled.connect(self._on_pin_toggled)

            self.action_topmost = self._make_checkable(menu, "Luôn nổi trên cùng", False)
            self.action_topmost.toggled.connect(self._on_topmost_toggled)

            self.action_lock = self._make_checkable(menu, "Khoá vị trí", False)
            self.action_lock.toggled.connect(self._on_lock_toggled)

            try:
                autostart_checked = autostart.is_enabled()
            except Exception:  # pragma: no cover - Registry bị chặn
                autostart_checked = False
            self.action_autostart = self._make_checkable(
                menu, "Khởi động cùng Windows", autostart_checked
            )
            self.action_autostart.toggled.connect(self._on_autostart_toggled)

            menu.addSeparator()

            # 5) Điều hướng
            self.action_today = QAction("Về hôm nay", menu)
            self.action_today.triggered.connect(self._on_today)
            menu.addAction(self.action_today)

            self.action_reset = QAction("Đặt lại vị trí", menu)
            self.action_reset.triggered.connect(self._on_reset_position)
            menu.addAction(self.action_reset)

            self.action_settings = QAction("Cài đặt…", menu)
            self.action_settings.triggered.connect(self._on_settings)
            menu.addAction(self.action_settings)

            self.action_update = QAction("Kiểm tra bản cập nhật…", menu)
            self.action_update.triggered.connect(self.update_check_requested.emit)
            menu.addAction(self.action_update)

            menu.addSeparator()

            # 6) Thoát
            self.action_quit = QAction("Thoát", menu)
            self.action_quit.triggered.connect(self._on_quit)
            menu.addAction(self.action_quit)

            self.menu = menu
        except Exception:
            log.warning("Dựng menu khay thất bại", exc_info=True)
            self.menu = None

    def _build_tray(self) -> None:
        """Tạo ``QSystemTrayIcon``; lỗi thì để ``self.tray = None``."""
        try:
            if QApplication.instance() is None:  # pragma: no cover - dùng sai
                return
            tray = QSystemTrayIcon(self._icon, self)
            tray.setToolTip(f"{APP_NAME} – lịch Dương–Âm")
            if self.menu is not None:
                tray.setContextMenu(self.menu)
            tray.activated.connect(self._on_activated)
            self.tray = tray
        except Exception:
            log.warning("Tạo QSystemTrayIcon thất bại", exc_info=True)
            self.tray = None

    # -- tín hiệu ra -------------------------------------------------------

    def _on_toggle_visibility(self, _checked: bool = False) -> None:
        if not self._syncing:
            self.toggled_visibility.emit()

    def _on_view_action(self, mode: str, _checked: bool = False) -> None:
        if not self._syncing:
            self.view_requested.emit(str(mode))

    def _on_opacity_action(self, value: float, _checked: bool = False) -> None:
        if not self._syncing:
            self.opacity_requested.emit(float(value))

    def _on_pin_toggled(self, checked: bool) -> None:
        if not self._syncing:
            self.pin_toggled.emit(bool(checked))

    def _on_topmost_toggled(self, checked: bool) -> None:
        if not self._syncing:
            self.topmost_toggled.emit(bool(checked))

    def _on_lock_toggled(self, checked: bool) -> None:
        if not self._syncing:
            self.lock_toggled.emit(bool(checked))

    def _on_autostart_toggled(self, checked: bool) -> None:
        if not self._syncing:
            self.autostart_toggled.emit(bool(checked))

    def _on_today(self, _checked: bool = False) -> None:
        if not self._syncing:
            self.today_requested.emit()

    def _on_reset_position(self, _checked: bool = False) -> None:
        if not self._syncing:
            self.reset_position_requested.emit()

    def _on_settings(self, _checked: bool = False) -> None:
        if not self._syncing:
            self.settings_requested.emit()

    def _on_quit(self, _checked: bool = False) -> None:
        if not self._syncing:
            self.quit_requested.emit()

    def _on_activated(self, reason) -> None:
        """Click/đúp chuột vào icon khay → ẩn/hiện cửa sổ."""
        try:
            if self._syncing:
                return
            enum = QSystemTrayIcon.ActivationReason
            if reason in (enum.Trigger, enum.DoubleClick):
                self.toggled_visibility.emit()
        except Exception:  # pragma: no cover - enum khác bản Qt
            log.debug("_on_activated bỏ qua", exc_info=True)

    # -- đồng bộ trạng thái ------------------------------------------------

    def set_state(self, settings) -> None:
        """Đồng bộ dấu tick/trạng thái menu theo ``Settings`` hiện tại."""
        if settings is None:
            return
        self._syncing = True
        try:
            # Chế độ xem
            view = str(getattr(settings, "view", "bloc") or "bloc")
            if self.action_view_bloc is not None:
                self.action_view_bloc.setChecked(view != "month")
            if self.action_view_month is not None:
                self.action_view_month.setChecked(view == "month")

            # Độ trong suốt
            step = _nearest_opacity(getattr(settings, "opacity", 1.0))
            for value, action in self.opacity_actions:
                try:
                    action.setChecked(abs(value - step) < 1e-9)
                except Exception:  # pragma: no cover
                    pass

            # Ghim / nổi / khoá
            placement = str(getattr(settings, "placement", "desktop") or "desktop")
            if self.action_pin is not None:
                self.action_pin.setChecked(placement != "floating")
            if self.action_topmost is not None:
                self.action_topmost.setChecked(bool(getattr(settings, "always_on_top", False)))
            if self.action_lock is not None:
                self.action_lock.setChecked(bool(getattr(settings, "lock_position", False)))

            # Khởi động cùng Windows: ưu tiên Settings, thiếu thì đọc Registry.
            run_at_startup = getattr(settings, "run_at_startup", None)
            if not isinstance(run_at_startup, bool):
                try:
                    run_at_startup = autostart.is_enabled()
                except Exception:  # pragma: no cover
                    run_at_startup = False
            if self.action_autostart is not None:
                self.action_autostart.setChecked(bool(run_at_startup))

            # Ẩn/hiện
            hidden = bool(getattr(settings, "hidden", False))
            self.set_visibility_checked(not hidden)
        except Exception:
            log.warning("set_state thất bại", exc_info=True)
        finally:
            self._syncing = False

    def set_visibility_checked(self, visible: bool) -> None:
        """Ghi nhớ cửa sổ đang hiện/ẩn (dùng cho tooltip + trạng thái nội bộ)."""
        try:
            self._visible = bool(visible)
            if self.tray is not None:
                state = "đang hiện" if self._visible else "đang ẩn"
                self.tray.setToolTip(f"{APP_NAME} – lịch Dương–Âm ({state})")
        except Exception:
            log.debug("set_visibility_checked thất bại", exc_info=True)

    # -- balloon / hiển thị ------------------------------------------------

    def show_message(self, title: str, text: str, msecs: int = 3000) -> bool:
        """Hiện balloon/tooltip hệ thống; ``False`` nếu khay không hỗ trợ."""
        try:
            if self.tray is None:
                return False
            if not QSystemTrayIcon.supportsMessages():
                return False
            self.tray.showMessage(
                str(title),
                str(text),
                QSystemTrayIcon.MessageIcon.Information,
                max(0, int(msecs)),
            )
            return True
        except Exception:
            log.debug("show_message thất bại", exc_info=True)
            return False

    def show(self) -> bool:
        """Hiện icon khay; ``False`` nếu không có khay."""
        try:
            if self.tray is None:
                return False
            self.tray.show()
            return True
        except Exception:
            log.debug("TrayIcon.show thất bại", exc_info=True)
            return False

    def hide(self) -> bool:
        """Ẩn icon khay; ``False`` nếu không có khay."""
        try:
            if self.tray is None:
                return False
            self.tray.hide()
            return True
        except Exception:
            log.debug("TrayIcon.hide thất bại", exc_info=True)
            return False

    @staticmethod
    def is_available() -> bool:
        """Máy có khay hệ thống khả dụng hay không."""
        try:
            return bool(QSystemTrayIcon.isSystemTrayAvailable())
        except Exception:
            return False
