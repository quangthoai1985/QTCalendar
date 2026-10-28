"""Tự động cập nhật ngầm QT Calendar — điều phối trên nền `core/update_check.py`.

Khi tự kiểm tra lúc khởi động thấy bản mới:
1. `auto_install_blocker()` kiểm tra xem ứng dụng có thể tự thay thế được không: phải là bản
   đóng gói (`QTCalendar.exe` chạy trong `%LOCALAPPDATA%\\Programs\\QT Calendar`),
   thư mục cài đặt ghi được và bản phát hành có `QTCalendar_Update.zip`.
2. `download_and_prepare()` tải ngầm `QTCalendar_Update.zip` về `%LOCALAPPDATA%\\QTCalendar\\updates\\`,
   kiểm tra SHA-256, giải nén vào `staging\\` và sinh script `apply_update.ps1`.
3. Ứng dụng giữ `InstallPlan`; khi người dùng bấm «Khởi động lại ngay» hoặc khi đóng ứng dụng,
   `update_check.launch_install()` sẽ chạy script PowerShell tách rời để hoàn tất việc cập nhật.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import update_check as uc


@dataclass
class PreparedUpdate:
    """Bản cập nhật đã tải và giải nén xong, sẵn sàng thay thế."""

    release: uc.ReleaseInfo
    zip_path: Path
    plan: uc.InstallPlan

    @property
    def version(self) -> str:
        return self.release.version


def auto_install_blocker(
    release: uc.ReleaseInfo,
    install_dir: Optional[Path] = None,
    frozen: Optional[bool] = None,
) -> str:
    """Lý do không tự tải & cài ngầm được (chuỗi rỗng = hoàn toàn hợp lệ để tự cập nhật)."""
    frozen = uc.is_frozen() if frozen is None else frozen
    install_dir = install_dir if install_dir is not None else uc.current_install_dir()
    if not frozen or install_dir is None:
        return "Đang chạy từ mã nguồn — có thể tải bộ cài mới từ GitHub."
    if release.asset is None:
        return f"Bản v{release.version} chưa có tệp {uc.UPDATE_ASSET_NAME}."
    if not uc.can_write_install_dir(Path(install_dir)):
        return f"Không thể ghi vào thư mục cài đặt «{install_dir}»."
    return ""


def download_and_prepare(
    release: uc.ReleaseInfo,
    install_dir: Path,
    should_cancel: Optional[uc.CancelCheck] = None,
    progress_cb: Optional[uc.ProgressCallback] = None,
) -> PreparedUpdate:
    """Tải tệp cập nhật, kiểm tra hash và sinh kịch bản cài đặt."""
    if release.asset is None:
        raise uc.UpdateError(f"Bản v{release.version} chưa có tệp {uc.UPDATE_ASSET_NAME}.")
    zip_path = uc.download_asset(release.asset, progress_cb=progress_cb, should_cancel=should_cancel)
    plan = uc.prepare_install(
        zip_path,
        release.version,
        Path(install_dir),
        should_cancel=should_cancel,
        progress_cb=progress_cb,
    )
    return PreparedUpdate(release=release, zip_path=zip_path, plan=plan)
