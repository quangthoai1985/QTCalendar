"""Hộp thoại và bộ điều phối kiểm tra & tự động cập nhật QT Calendar từ GitHub Release."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __github_repo__, __version__
from ..core import update_check as uc
from ..core import updater
from ..core.theme import Theme, get_theme
from .styles import build_stylesheet, px, qcolor


def _format_date(iso_text: str) -> str:
    try:
        return datetime.fromisoformat(iso_text.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y")
    except Exception:
        return ""


class UpdateCheckWorker(QThread):
    """Luồng nền kiểm tra bản phát hành mới nhất từ GitHub."""

    checked = Signal(object)  # Optional[uc.ReleaseInfo]
    failed = Signal(str)

    def run(self) -> None:
        try:
            rel = uc.check_for_update(__version__)
            self.checked.emit(rel)
        except uc.UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Không thể kiểm tra cập nhật: {exc}")


class UpdateDownloadWorker(QThread):
    """Luồng nền tải tệp cập nhật và chuẩn bị kịch bản cài đặt."""

    progress = Signal(object, object)  # (downloaded, total)
    stage = Signal(str)
    finishedOk = Signal(object)  # updater.PreparedUpdate | Path
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, release: uc.ReleaseInfo, install_dir: Optional[Path], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.release = release
        self.install_dir = install_dir
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        assert self.release.asset is not None
        try:
            self.stage.emit("Đang tải bản cập nhật...")

            def progress_cb(cur: int, tot: int) -> None:
                self.progress.emit(cur, tot)

            def cancel_check() -> bool:
                return self._cancel

            if self.install_dir is not None and not updater.auto_install_blocker(self.release, self.install_dir):
                prepared = updater.download_and_prepare(
                    self.release,
                    self.install_dir,
                    should_cancel=cancel_check,
                    progress_cb=progress_cb,
                )
                self.finishedOk.emit(prepared)
            else:
                zip_path = uc.download_asset(
                    self.release.asset,
                    progress_cb=progress_cb,
                    should_cancel=cancel_check,
                )
                self.finishedOk.emit(zip_path)
        except uc.UpdateCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateDialog(QDialog):
    """Hộp thoại thông báo và tải bản cập nhật mới."""

    def __init__(
        self,
        release: uc.ReleaseInfo,
        parent: QWidget | None = None,
        theme: Theme | None = None,
        scale: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._theme = theme or get_theme(None)
        self._scale = scale
        self._worker: Optional[UpdateDownloadWorker] = None
        self._prepared: Optional[updater.PreparedUpdate] = None

        self.setWindowTitle(f"Cập nhật {APP_NAME}")
        self.setMinimumWidth(int(px(460, scale)))
        self.resize(int(px(480, scale)), int(px(380, scale)))
        self.setStyleSheet(build_stylesheet(self._theme, self._scale))

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(int(px(12, self._scale)))
        layout.setContentsMargins(
            int(px(18, self._scale)),
            int(px(18, self._scale)),
            int(px(18, self._scale)),
            int(px(18, self._scale)),
        )

        # Tiêu đề
        header_layout = QHBoxLayout()
        icon_lbl = QLabel("🎉", self)
        f_icon = QFont()
        f_icon.setPixelSize(int(px(28, self._scale)))
        icon_lbl.setFont(f_icon)
        header_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_lbl = QLabel(f"Đã có phiên bản mới: v{self._release.version}", self)
        f_title = QFont(self._theme.font_ui, int(px(14, self._scale)))
        f_title.setBold(True)
        title_lbl.setFont(f_title)
        title_box.addWidget(title_lbl)

        sub_text = f"Phiên bản hiện tại: v{__version__}"
        date_str = _format_date(self._release.published_at)
        if date_str:
            sub_text += f" · Phát hành: {date_str}"
        sub_lbl = QLabel(sub_text, self)
        sub_lbl.setStyleSheet(f"color: {self._theme.ink_soft};")
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box, 1)
        layout.addLayout(header_layout)

        # Khung nhật ký thay đổi (Changelog)
        cl_label = QLabel("Nội dung cập nhật:", self)
        cl_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(cl_label)

        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(True)
        if self._release.body:
            self._browser.setMarkdown(self._release.body)
        else:
            self._browser.setText("Bản cập nhật cải tiến hiệu năng và sửa lỗi.")
        layout.addWidget(self._browser, 1)

        # Thanh tiến trình
        self._status_lbl = QLabel("", self)
        self._status_lbl.hide()
        layout.addWidget(self._status_lbl)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Nút bấm hành động
        btn_layout = QHBoxLayout()
        self._btn_github = QPushButton("Xem trên GitHub", self)
        self._btn_github.clicked.connect(self._open_github)
        btn_layout.addWidget(self._btn_github)

        btn_layout.addStretch()

        self._btn_later = QPushButton("Để sau", self)
        self._btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_later)

        self._btn_action = QPushButton("Cập nhật ngay", self)
        self._btn_action.setDefault(True)
        self._btn_action.setStyleSheet(f"background-color: {self._theme.accent}; color: {self._theme.accent_ink}; font-weight: bold;")
        self._btn_action.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self._btn_action)

        layout.addLayout(btn_layout)

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(self._release.html_url))

    def _on_action_clicked(self) -> None:
        if self._prepared is not None:
            # Khởi động lại ngay
            uc.launch_install(self._prepared.plan)
            self.accept()
            return

        install_dir = uc.current_install_dir()
        blocker = updater.auto_install_blocker(self._release, install_dir)
        if blocker:
            # Không thể tự thay thế (ví dụ chạy từ source) -> mở link tải bộ cài
            QDesktopServices.openUrl(QUrl(self._release.html_url))
            self.accept()
            return

        # Bắt đầu tải ngầm
        self._btn_action.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._status_lbl.setText("Đang chuẩn bị tải về...")
        self._status_lbl.show()
        self._progress_bar.show()

        self._worker = UpdateDownloadWorker(self._release, install_dir, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.stage.connect(self._status_lbl.setText)
        self._worker.finishedOk.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            percent = int((current / total) * 100)
            self._progress_bar.setValue(percent)
            self._status_lbl.setText(f"Đang tải: {uc.format_size(current)} / {uc.format_size(total)} ({percent}%)")

    def _on_finished(self, result: object) -> None:
        self._progress_bar.setValue(100)
        if isinstance(result, updater.PreparedUpdate):
            self._prepared = result
            self._status_lbl.setText("Đã tải xong và sẵn sàng cập nhật!")
            self._btn_action.setText("Khởi động lại ngay")
            self._btn_action.setEnabled(True)
            self._btn_later.setText("Cập nhật khi thoát")
            self._btn_later.setEnabled(True)
            self._btn_later.clicked.disconnect()
            self._btn_later.clicked.connect(self._schedule_on_exit)
        else:
            self._status_lbl.setText("Đã tải tệp cập nhật thành công!")
            self._btn_action.setText("Đóng")
            self._btn_action.setEnabled(True)
            self._btn_action.clicked.disconnect()
            self._btn_action.clicked.connect(self.accept)

    def _schedule_on_exit(self) -> None:
        if self._prepared:
            # Cài đặt tự động khi ứng dụng đóng
            pass
        self.accept()

    def _on_failed(self, error_msg: str) -> None:
        self._status_lbl.setText(f"Lỗi: {error_msg}")
        self._btn_action.setEnabled(True)
        self._btn_action.setText("Thử lại")
        self._btn_later.setEnabled(True)
        QMessageBox.warning(self, "Lỗi cập nhật", f"Không thể hoàn tất cập nhật:\n{error_msg}")
