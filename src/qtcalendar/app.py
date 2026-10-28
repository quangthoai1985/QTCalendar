"""Điều phối toàn bộ ứng dụng QT Calendar.

Tầng này nối bốn mảnh lại:

``core.config``   ↔ đọc/ghi ``settings.json``
``ui``            ↔ cửa sổ widget, hai chế độ xem, hộp thoại cài đặt
``platform``      ↔ khay hệ thống, registry khởi động cùng Windows, ghim desktop

Chế độ dòng lệnh
================

Không tham số
    Chạy ứng dụng bình thường (widget + icon khay hệ thống).

``--smoke <file.png>``
    Dựng widget, chụp ảnh ra PNG, in thông tin ngày dưới dạng JSON rồi thoát.
    Dùng cho kiểm thử tự động / CI (không cần hiện cửa sổ thật).

``--info``
    In thông tin âm lịch của hôm nay dạng JSON rồi thoát.

``--reset``
    Xoá cấu hình, trở về mặc định.

``--version``
    In phiên bản.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, __version__
from .core import calendar_service
from .core.config import ConfigStore, Settings, data_dir
from .core.theme import get_theme
from .platform import autostart
from .ui.settings_dialog import SettingsDialog
from .ui.widget_window import CalendarWidget
from .ui.update_dialog import UpdateCheckWorker, UpdateDialog
from .core import update_check as uc

__all__ = ["main", "AppController"]

_LOG = logging.getLogger("qtcalendar")

#: Đường dẫn icon (tìm ngược từ gói ra gốc dự án).
def icon_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "assets" / "icon.ico"
        if candidate.is_file():
            return candidate
    return Path("assets/icon.ico")


# ===========================================================================
# Logging
# ===========================================================================
def setup_logging(level: str = "INFO") -> None:
    """Ghi log ra ``%LOCALAPPDATA%\\QTCalendar\\qtcalendar.log`` (xoay vòng 64 KB)."""
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger("qtcalendar")
    if root.handlers:
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        log_dir = data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "qtcalendar.log", maxBytes=64 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(fmt)
        root.addHandler(handler)
    except OSError:  # pragma: no cover - đĩa chỉ đọc
        pass
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root.addHandler(stream)


# ===========================================================================
# Bộ điều phối
# ===========================================================================
class AppController(QObject):
    """Giữ vòng đời ứng dụng: widget ↔ khay hệ thống ↔ cấu hình."""

    def __init__(
        self,
        app: QApplication,
        settings: Settings,
        store: ConfigStore,
        lock: QLockFile | None = None,
    ) -> None:
        super().__init__()
        self._app = app
        self._settings = settings
        self._store = store
        self._lock = lock
        self._tray = None
        self._quitting = False

        # Ghi cấu hình có trễ để không đập đĩa khi kéo thả liên tục
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._flush_settings)

        self._widget = CalendarWidget(settings)
        self._widget.resize(settings.width, settings.height)
        self._build_tray()
        self._wire()

    # ------------------------------------------------------------------ tray
    def _build_tray(self) -> None:
        try:
            from .platform.tray import TrayIcon

            tray = TrayIcon(icon_path())
            if not tray.is_available():
                _LOG.warning("Khay hệ thống không khả dụng – chạy không có icon tray")
                return
            self._tray = tray
            tray.set_state(self._settings)
            tray.show()
        except Exception as exc:  # pragma: no cover - phòng hờ Qt lỗi
            _LOG.exception("Không tạo được icon khay hệ thống: %s", exc)

    def _wire(self) -> None:
        w = self._widget
        w.settings_changed.connect(self._on_settings_changed)
        w.settings_requested.connect(self.open_settings)
        w.quit_requested.connect(self.quit_app)
        w.hide_requested.connect(self.hide_widget)
        w.update_check_requested.connect(lambda: self.check_for_updates(silent=False))

        tray = self._tray
        if tray is None:
            return
        tray.toggled_visibility.connect(self.toggle_widget)
        tray.settings_requested.connect(self.open_settings)
        tray.quit_requested.connect(self.quit_app)
        tray.view_requested.connect(w.set_view)
        tray.opacity_requested.connect(w.set_opacity)
        tray.pin_toggled.connect(
            lambda checked: w.set_placement("desktop" if checked else "floating")
        )
        tray.topmost_toggled.connect(w.set_always_on_top)
        tray.lock_toggled.connect(w.set_lock_position)
        tray.autostart_toggled.connect(w.set_run_at_startup)
        tray.today_requested.connect(w.go_today)
        tray.reset_position_requested.connect(w.reset_position)
        tray.update_check_requested.connect(lambda: self.check_for_updates(silent=False))

    # --------------------------------------------------------------- khởi động
    def start(self) -> None:
        """Hiện widget (nếu lần trước không bị ẩn) và đặt đúng vị trí."""
        # Dọn dẹp thư mục sao lưu của bản cập nhật trước
        try:
            uc.cleanup_previous_update()
        except Exception:
            pass

        self._widget.restore_position()
        if self._settings.hidden:
            _LOG.info("Khởi động ở chế độ ẩn (lần chạy trước người dùng đã ẩn)")
        else:
            self._widget.show()
        # Áp dụng ghim/vị trí sau khi cửa sổ đã có HWND
        QTimer.singleShot(0, self._apply_placement_later)
        # Tự động kiểm tra bản cập nhật ngầm sau 3 giây khởi động
        QTimer.singleShot(3000, lambda: self.check_for_updates(silent=True))
        _LOG.info(
            "QT Calendar %s sẵn sàng – theme=%s, view=%s, opacity=%.2f",
            __version__,
            self._settings.theme,
            self._settings.view,
            self._settings.opacity,
        )

    def _apply_placement_later(self) -> None:
        self._widget.apply_placement()
        if self._tray is not None:
            self._tray.set_state(self._settings)

    # -------------------------------------------------------------- sự kiện
    def _on_settings_changed(self) -> None:
        if self._tray is not None:
            try:
                self._tray.set_state(self._settings)
            except Exception:  # pragma: no cover
                pass
        self._save_timer.start()

    def _flush_settings(self) -> None:
        try:
            self._store.save(self._settings)
        except Exception:  # pragma: no cover - không để lỗi lưu làm sập app
            _LOG.exception("Không lưu được cấu hình")

    def toggle_widget(self) -> None:
        if self._widget.isVisible():
            self.hide_widget()
        else:
            self.show_widget()

    def show_widget(self) -> None:
        self._widget.show()
        self._widget.raise_()
        self._widget.apply_placement()
        self._settings.hidden = False
        self._on_settings_changed()

    def hide_widget(self) -> None:
        self._widget.hide()
        self._settings.hidden = True
        self._on_settings_changed()
        if self._tray is not None:
            self._tray.show_message(
                APP_NAME,
                "Lịch đã được ẩn. Bấm đúp vào icon khay hệ thống để hiện lại.",
            )

    def open_settings(self) -> None:
        """Mở hộp thoại cài đặt rồi áp toàn bộ thay đổi."""
        try:
            new_settings = SettingsDialog.edit(self._settings, self._widget)
        except Exception:  # pragma: no cover
            _LOG.exception("Không mở được hộp thoại cài đặt")
            return
        if new_settings is None:
            return

        previous_startup = self._settings.run_at_startup
        previous_engine = self._settings.lunar_engine
        for f in fields(Settings):
            setattr(self._settings, f.name, getattr(new_settings, f.name))

        if self._settings.run_at_startup != previous_startup:
            autostart.set_enabled(self._settings.run_at_startup)
        if self._settings.lunar_engine != previous_engine:
            calendar_service.get_day_info.cache_clear()

        self._widget.apply_settings(rebuild_flags=True)
        self._widget.restore_position()
        self._on_settings_changed()
        _LOG.info("Đã áp dụng cài đặt mới: %s", self._settings.to_dict())

    def check_for_updates(self, silent: bool = False) -> None:
        """Kiểm tra bản cập nhật từ GitHub Release."""
        from PySide6.QtWidgets import QMessageBox

        worker = UpdateCheckWorker(self)

        def on_checked(release) -> None:
            if release is not None:
                dlg = UpdateDialog(
                    release,
                    parent=self._widget,
                    theme=get_theme(self._settings.theme),
                    scale=self._settings.scale,
                )
                dlg.exec()
            elif not silent:
                QMessageBox.information(
                    self._widget,
                    f"Cập nhật {APP_NAME}",
                    f"Bạn đang sử dụng phiên bản mới nhất ({__version__}).",
                )

        def on_failed(error_msg: str) -> None:
            if not silent:
                QMessageBox.warning(
                    self._widget,
                    f"Cập nhật {APP_NAME}",
                    f"Không thể kiểm tra bản cập nhật:\n{error_msg}",
                )

        worker.checked.connect(on_checked)
        worker.failed.connect(on_failed)
        self._update_worker = worker
        worker.start()

    def quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        _LOG.info("Thoát ứng dụng theo yêu cầu")
        self._widget.hide()
        self._flush_settings()
        if self._tray is not None:
            self._tray.hide()
        if self._lock is not None:
            self._lock.unlock()
        self._app.quit()


# ===========================================================================
# Tạo QApplication
# ===========================================================================
def create_application(argv: list[str] | None = None) -> QApplication:
    """Tạo (hoặc lấy) ``QApplication`` với cấu hình chuẩn của ứng dụng."""
    app = QApplication.instance()
    if app is None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(argv or sys.argv[:1])
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)  # ẩn widget không được thoát app
    icon_file = icon_path()
    if icon_file.is_file():
        app.setWindowIcon(QIcon(str(icon_file)))
    return app


# ===========================================================================
# Chế độ dòng lệnh
# ===========================================================================
def _day_info_payload(day=None) -> dict:
    """Thông tin ngày dưới dạng dict (cho ``--info`` và ``--smoke``)."""
    day = day or calendar_service.today()
    info = calendar_service.get_day_info(day)
    return {
        "solar": info.solar.isoformat(),
        "weekday": info.weekday_name,
        "lunar": f"{info.lunar.day}/{info.lunar.month}{' nhuận' if info.lunar.leap else ''}/{info.lunar.year}",
        "lunar_line": info.lunar_line,
        "year_can_chi": info.year_can_chi.text,
        "month_can_chi": info.month_can_chi.text,
        "day_can_chi": info.day_can_chi.text,
        "zodiac": info.zodiac,
        "tiet_khi": info.tiet_khi,
        "holiday": info.holiday,
        "auspicious_day": info.is_auspicious_day,
        "auspicious_hours": [h.compact_text for h in info.auspicious_hours],
    }


def _run_smoke(settings: Settings, out_path: Path, view: str, theme: str | None) -> int:
    """Dựng widget, chụp ảnh PNG và in thông tin – không cần màn hình thật."""
    s = settings.copy()
    s.placement = "floating"
    s.hidden = False
    s.view = view if view in ("bloc", "month") else "bloc"
    if theme:
        s.theme = theme
    s.opacity = 1.0

    out_path = out_path if out_path.is_absolute() else (Path.cwd() / out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    widget = CalendarWidget(s)
    widget.resize(s.width, s.height)
    widget.move(40, 40)
    widget.show()
    QApplication.processEvents()
    widget.set_view(s.view)
    QApplication.processEvents()
    # Áp hệ số phóng theo kích thước ngay (bình thường việc này có debounce
    # 90 ms; ở chế độ chụp ảnh cần kết quả tức thì).
    apply_scale = getattr(widget, "_apply_content_scale", None)
    if callable(apply_scale):
        apply_scale()
        QApplication.processEvents()
    ok = widget.grab().save(str(out_path), "PNG")
    payload = {
        "saved": bool(ok),
        "png": str(out_path),
        "pixels": [widget.width(), widget.height()],
        "view": s.view,
        "theme": s.theme,
        "engine": s.lunar_engine,
        "window_opacity": round(widget.windowOpacity(), 3),
        "card_size": [widget.width(), widget.height()],
        "day": _day_info_payload(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    widget.hide()
    return 0 if ok else 1


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="qtcalendar",
        description="QT Calendar – lịch bloc Dương-Âm cho Windows",
    )
    parser.add_argument("--version", action="version", version=f"QT Calendar {__version__}")
    parser.add_argument(
        "--info", action="store_true", help="in thông tin âm lịch hôm nay rồi thoát"
    )
    parser.add_argument(
        "--smoke",
        metavar="PNG",
        help="dựng widget, chụp ảnh ra tệp PNG rồi thoát (kiểm thử tự động)",
    )
    parser.add_argument(
        "--view",
        choices=("bloc", "month"),
        default="bloc",
        help="chế độ xem khi chạy --smoke",
    )
    parser.add_argument("--theme", help="mã bảng màu khi chạy --smoke")
    parser.add_argument("--reset", action="store_true", help="xoá cấu hình, về mặc định")
    parser.add_argument(
        "--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR")
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Điểm vào của ứng dụng. Trả mã thoát cho ``sys.exit``."""
    args = _parse_args(argv or [])
    setup_logging(args.log_level)

    store = ConfigStore()
    if args.info:
        print(json.dumps(_day_info_payload(), ensure_ascii=False, indent=2))
        return 0

    settings = store.load()
    if args.reset:
        settings = store.reset()
        store.save(settings)
        _LOG.info("Đã đặt lại cấu hình: %s", store.path)

    app = create_application()

    if args.smoke:
        return _run_smoke(settings, Path(args.smoke), args.view, args.theme)

    # ---- chỉ cho chạy một bản ----
    try:
        data_dir().mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(data_dir() / "qtcalendar.lock"))
        lock.setStaleLockTime(10_000)
        if not lock.tryLock(250):
            if lock.error() in (
                QLockFile.LockError.PermissionError,
                QLockFile.LockError.UnknownError,
            ):
                # Không ghi được tệp khoá (thư mục chỉ đọc, sandbox…): vẫn chạy,
                # chỉ mất tính năng "chỉ một bản".
                _LOG.warning(
                    "Không tạo được tệp khoá một-bản (%s) – vẫn tiếp tục chạy",
                    lock.error(),
                )
                lock = None
            else:
                # Tệp khoá còn lại sau khi tiến trình trước bị kill/thoát đột
                # ngột: Qt chỉ tự dọn khi đã quá 10 giây, nên thử dọn ngay.
                removed = lock.removeStaleLockFile()
                if not (removed and lock.tryLock(250)):
                    _LOG.warning("QT Calendar đang chạy ở tiến trình khác – thoát")
                    return 0
                _LOG.info("Đã dọn tệp khoá cũ của lần chạy trước")
    except OSError:  # pragma: no cover
        lock = None

    controller = AppController(app, settings, store, lock)
    controller.start()
    return app.exec()
