# -*- coding: utf-8 -*-
"""Kiểm thử icon khay hệ thống: bấm/nháy đúp icon chỉ được *hiện* lịch.

Trên Windows, nháy đúp icon khay phát hai tín hiệu liên tiếp ``Trigger``
(nhả chuột lần đầu) rồi ``DoubleClick``. Nếu cả hai cùng bật/tắt thì lịch
hiện lên rồi bị ẩn ngay.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from qtcalendar.platform.tray import TrayIcon  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def tray(qapp):
    icon = TrayIcon()
    yield icon
    icon.hide()
    icon.deleteLater()


def _spy(signal) -> list:
    calls: list = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def test_nhay_dup_icon_chi_hien_lich(tray):
    shown = _spy(tray.show_requested)
    toggled = _spy(tray.toggled_visibility)
    reason = QSystemTrayIcon.ActivationReason
    tray._on_activated(reason.Trigger)
    tray._on_activated(reason.DoubleClick)
    assert len(shown) == 2
    assert toggled == []


def test_menu_hien_an_van_bat_tat(tray):
    toggled = _spy(tray.toggled_visibility)
    tray._on_toggle_visibility()
    assert len(toggled) == 1
