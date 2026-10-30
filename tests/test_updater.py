# -*- coding: utf-8 -*-
"""Unit tests cho module update_check và updater."""

import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qtcalendar.core.update_check import (
    AssetInfo,
    InstallPlan,
    ReleaseInfo,
    cleanup_previous_update,
    format_size,
    is_newer,
    launch_install,
    parse_release,
    parse_version,
    update_script_text,
    write_update_script,
)


class TestUpdateSemver:
    def test_parse_version_valid(self):
        v1 = parse_version("1.0.0")
        assert v1 is not None
        assert v1.major == 1 and v1.minor == 0 and v1.patch == 0
        assert v1.core == "1.0.0"

        v2 = parse_version("v1.2.3")
        assert v2 is not None
        assert v2.major == 1 and v2.minor == 2 and v2.patch == 3

        v3 = parse_version("v2.10.5-beta")
        assert v3 is not None
        assert v3.major == 2 and v3.minor == 10 and v3.patch == 5
        assert v3.prerelease == "beta"
        assert v3.is_prerelease is True

    def test_parse_version_invalid(self):
        assert parse_version("invalid") is None
        assert parse_version("") is None

    def test_is_newer(self):
        assert is_newer("1.0.1", "1.0.0") is True
        assert is_newer("v1.1.0", "1.0.9") is True
        assert is_newer("2.0.0", "1.9.9") is True
        assert is_newer("1.0.0", "1.0.0") is False
        assert is_newer("0.9.9", "1.0.0") is False
        assert is_newer("invalid", "1.0.0") is False


class TestReleasePayloadParsing:
    def test_parse_release(self):
        payload = {
            "tag_name": "v1.0.1",
            "published_at": "2026-10-28T12:00:00Z",
            "html_url": "https://github.com/quangthoai1985/QTCalendar/releases/tag/v1.0.1",
            "body": "Fix layout bug",
            "assets": [
                {
                    "name": "QTCalendar_Update.zip",
                    "browser_download_url": "https://github.com/quangthoai1985/QTCalendar/releases/download/v1.0.1/QTCalendar_Update.zip",
                    "size": 10240,
                },
                {
                    "name": "QTCalendar_Setup.exe",
                    "browser_download_url": "https://github.com/quangthoai1985/QTCalendar/releases/download/v1.0.1/QTCalendar_Setup.exe",
                    "size": 20480,
                },
            ],
        }
        rel = parse_release(payload)
        assert rel is not None
        assert rel.version == "1.0.1"
        assert rel.tag_name == "v1.0.1"
        assert rel.asset is not None
        assert rel.asset.name == "QTCalendar_Update.zip"
        assert rel.setup_asset is not None
        assert rel.setup_asset.name == "QTCalendar_Setup.exe"

    def test_format_size(self):
        assert format_size(500) == "500 B"
        assert "KB" in format_size(2048)
        assert "MB" in format_size(10 * 1024 * 1024)


class TestUpdaterScript:
    def test_update_script_text(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            target = tmp / "App"
            staging = tmp / "Stage"

            content = update_script_text(
                staging_app_dir=staging,
                install_dir=target,
                target_version="1.0.1",
                pid=1234,
            )
            assert "QTCalendar.exe" in content
            assert "1.0.1" in content
            assert "unins*" in content
            assert "DisplayVersion" in content
            assert "1234" in content
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @pytest.mark.skipif(os.name != "nt", reason="Kịch bản cập nhật chạy bằng PowerShell trên Windows")
    def test_launch_install_swaps_dir_when_app_cwd_is_install_dir(self):
        # Shortcut Start Menu/Startup đặt "Start in" = thư mục cài đặt → app có cwd nằm trong
        # thư mục sẽ bị đổi tên; tiến trình PowerShell không được kế thừa cwd này.
        tmp = Path(tempfile.mkdtemp())
        old_cwd = os.getcwd()
        try:
            install = tmp / "QT Calendar"
            install.mkdir()
            (install / "QTCalendar.exe").write_text("old", encoding="utf-8")
            staging = tmp / "staging" / "QTCalendar"
            staging.mkdir(parents=True)
            (staging / "QTCalendar.exe").write_text("new", encoding="utf-8")

            with patch("qtcalendar.core.update_check.updates_dir", return_value=tmp):
                # AppId giả: không được ghi DisplayVersion vào khoá gỡ cài đặt thật.
                script = write_update_script(
                    update_script_text(
                        staging, install, "9.9.9", pid=0, relaunch=False,
                        inno_app_id="{00000000-0000-0000-0000-QTCALTEST000}",
                    )
                )
                plan = InstallPlan(staging, install, script, "9.9.9", relaunch=False)
                os.chdir(install)
                try:
                    launch_install(plan)
                finally:
                    os.chdir(old_cwd)  # tương đương app cũ thoát

            exe = install / "QTCalendar.exe"
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if exe.is_file() and exe.read_text(encoding="utf-8") == "new":
                    break
                time.sleep(0.5)
            assert exe.read_text(encoding="utf-8") == "new"
            assert (tmp / "QT Calendar.old" / "QTCalendar.exe").is_file()
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cleanup_previous_update(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            old_backup = tmp.parent / (tmp.name + ".old")
            old_backup.mkdir(parents=True, exist_ok=True)
            dummy_file = old_backup / "dummy.txt"
            dummy_file.write_text("test")

            with patch("qtcalendar.core.update_check.current_install_dir", return_value=tmp):
                cleanup_previous_update()
                assert not old_backup.exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
