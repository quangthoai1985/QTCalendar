"""Kiểm thử tab kéo :class:`MonthTab` – nút bật/tắt lịch tháng dưới chân bloc.

Chạy trên nền tảng Qt ``offscreen``: tab chỉ cần đúng chữ, đúng hướng mũi
tên theo trạng thái, phát tín hiệu khi bấm chuột trái và co giãn theo hệ số
phóng nội dung.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtcalendar.core.theme import get_theme  # noqa: E402
from qtcalendar.ui.month_tab import MonthTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def tab(qapp):
    widget = MonthTab()
    widget.apply_theme(get_theme(None), 1.0)
    widget.resize(widget.sizeHint())
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


def test_mac_dinh_dong_ghi_thang_mui_ten_xuong(tab):
    assert tab.is_open() is False
    assert tab.label() == "THÁNG"
    assert tab.arrow_points_down() is True


def test_mo_doi_chu_va_mui_ten(tab):
    tab.set_open(True)
    assert tab.is_open() is True
    assert tab.label() == "ẨN"
    assert tab.arrow_points_down() is False


def test_bam_chuot_trai_phat_toggled_mot_lan(tab):
    hits: list[int] = []
    tab.toggled.connect(lambda: hits.append(1))
    QTest.mouseClick(tab, Qt.LeftButton)
    assert hits == [1]


def test_bam_chuot_phai_khong_phat(tab):
    hits: list[int] = []
    tab.toggled.connect(lambda: hits.append(1))
    QTest.mouseClick(tab, Qt.RightButton)
    assert hits == []


def test_chu_khong_dung_ky_tu_tuong_hinh(tab):
    """Ký tự thiếu glyph làm DirectWrite nạp font dự phòng (~85 MB RAM)."""
    for flag in (False, True):
        tab.set_open(flag)
        assert all(ord(ch) < 0x2000 for ch in tab.label())


def test_size_hint_tang_theo_scale(tab):
    tab.apply_theme(get_theme(None), 1.0)
    nho = tab.sizeHint()
    tab.apply_theme(get_theme(None), 2.0)
    assert tab.sizeHint().width() > nho.width()
    assert tab.sizeHint().height() > nho.height()
