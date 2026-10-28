# -*- coding: utf-8 -*-
"""Unit tests cho UpdateDialog."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from qtcalendar.core.update_check import InstallPlan, ReleaseInfo
from qtcalendar.core.updater import PreparedUpdate
from qtcalendar.ui.update_dialog import UpdateDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_update_dialog_outcomes(qapp):
    release = ReleaseInfo(
        version="1.0.1",
        tag_name="v1.0.1",
        published_at="2026-10-28T00:00:00Z",
        html_url="http://example.com",
    )
    dlg = UpdateDialog(release)
    assert dlg.outcome == "dismiss"
    assert dlg.plan is None

    # Giả lập đã tải xong
    dummy_plan = MagicMock(spec=InstallPlan)
    dlg._prepared = PreparedUpdate(release=release, zip_path=MagicMock(), plan=dummy_plan)

    # Bấm khởi động lại ngay
    dlg._on_action_clicked()
    assert dlg.outcome == "restart"
    assert dlg.plan == dummy_plan

    # Bấm cập nhật khi thoát
    dlg.outcome = "dismiss"
    dlg._schedule_on_exit()
    assert dlg.outcome == "on_exit"
    assert dlg.plan == dummy_plan
