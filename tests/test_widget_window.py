"""Kiểm thử cửa sổ widget: kéo giãn kích thước, giới hạn và lưu cấu hình.

Chạy trên nền tảng Qt ``offscreen`` nên không cần màn hình thật, không mở
cửa sổ nào. Mục tiêu là khoá lại hợp đồng của tay nắm kéo giãn (góc dưới
phải) mà người dùng yêu cầu: kéo được to/nhỏ, có giới hạn, lưu vào
``settings.json`` và có thao tác trả về kích thước chuẩn.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtcalendar.core.config import Settings  # noqa: E402
from qtcalendar.ui.widget_window import (  # noqa: E402
    BASE_HEIGHT,
    BASE_WIDTH,
    MAX_HEIGHT,
    MAX_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    SHADOW_MARGIN,
    CalendarWidget,
    month_extra_height,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def widget(qapp):
    settings = Settings()
    settings.x, settings.y = 100, 100
    view = CalendarWidget(settings)
    view.resize(settings.width, settings.height)
    view.show()          # nền tảng offscreen: không mở cửa sổ thật
    qapp.processEvents()
    yield view
    view.close()
    view.deleteLater()


# --------------------------------------------------------------------------- #
# Hằng số giới hạn
# --------------------------------------------------------------------------- #
def test_gioi_han_kich_thuoc_hop_ly():
    assert MIN_WIDTH < BASE_WIDTH < MAX_WIDTH
    assert MIN_HEIGHT < BASE_HEIGHT < MAX_HEIGHT
    assert MIN_WIDTH >= 240  # vẫn đọc được nội dung
    assert MAX_WIDTH >= 700


# --------------------------------------------------------------------------- #
# Kéo giãn
# --------------------------------------------------------------------------- #
def test_mac_dinh_dung_bang_kich_thuoc_chuan(widget):
    assert (widget.width(), widget.height()) == (BASE_WIDTH, BASE_HEIGHT)


def test_keo_to_them_dung_delta(widget):
    widget.begin_resize(QPoint(1000, 1000))
    widget.drag_resize(QPoint(1120, 1100))
    widget.end_resize()
    assert (widget.width(), widget.height()) == (BASE_WIDTH + 120, BASE_HEIGHT + 100)


def test_keo_thu_nho_bi_kep_o_min(widget):
    widget.begin_resize(QPoint(1000, 1000))
    widget.drag_resize(QPoint(-2000, -2000))
    widget.end_resize()
    # Kẹp ở mức nhỏ nhất: hằng số thiết kế hoặc nhu cầu tối thiểu của layout.
    assert widget.width() == max(MIN_WIDTH, widget.minimumSizeHint().width())
    assert widget.height() == max(MIN_HEIGHT, widget.minimumSizeHint().height())
    assert widget.width() <= BASE_WIDTH
    assert widget.height() <= BASE_HEIGHT


def test_keo_to_bi_kep_o_max(widget):
    widget.begin_resize(QPoint(0, 0))
    widget.drag_resize(QPoint(9000, 9000))
    widget.end_resize()
    assert widget.width() <= MAX_WIDTH
    assert widget.height() <= MAX_HEIGHT
    assert widget.width() >= MIN_WIDTH and widget.height() >= MIN_HEIGHT


def test_tha_tay_nam_luu_kich_thuoc_va_phat_tin_hieu(widget):
    emitted: list[bool] = []
    widget.settings_changed.connect(lambda: emitted.append(True))

    widget.begin_resize(QPoint(0, 0))
    widget.drag_resize(QPoint(80, 60))
    widget.end_resize()

    assert emitted, "phải phát settings_changed để app.py lưu cấu hình"
    assert widget._settings.width == widget.width()
    assert widget._settings.height == widget.height()


def test_khong_keo_thi_khong_doi_kich_thuoc(widget):
    widget.drag_resize(QPoint(400, 400))  # chưa begin_resize
    assert (widget.width(), widget.height()) == (BASE_WIDTH, BASE_HEIGHT)


# --------------------------------------------------------------------------- #
# Trả về mặc định + hệ số phóng nội dung
# --------------------------------------------------------------------------- #
def test_dat_lai_kich_thuoc(widget):
    widget.resize(500, 620)
    widget.reset_size()
    assert (widget.width(), widget.height()) == (BASE_WIDTH, BASE_HEIGHT)


def test_he_so_phong_tang_khi_cua_so_to(widget):
    nho = widget.content_scale()
    widget.resize(520, 700)
    assert widget.content_scale() > nho
    assert widget.content_scale() <= 2.6


def test_he_so_phong_giam_khi_cua_so_nho(widget):
    widget.resize(MIN_WIDTH, MIN_HEIGHT)
    assert 0.5 <= widget.content_scale() < 1.0


def test_tay_nam_nam_trong_long_widget(widget):
    for kich_thuoc in ((MIN_WIDTH, MIN_HEIGHT), (BASE_WIDTH, BASE_HEIGHT), (520, 700)):
        widget.resize(*kich_thuoc)
        grip = widget._grip
        assert grip.x() + grip.width() <= widget.width()
        assert grip.y() + grip.height() <= widget.height()
        assert grip.x() >= 0 and grip.y() >= 0


def test_tay_nam_co_tooltip_va_con_tro(widget):
    from PySide6.QtCore import Qt

    assert widget._grip.cursor().shape() == Qt.SizeFDiagCursor
    assert "Kéo" in widget._grip.toolTip()


# --------------------------------------------------------------------------- #
# Chế độ ghim desktop: cửa sổ PHẢI chuyển sang vẽ đục (nếu không sẽ vô hình)
# --------------------------------------------------------------------------- #
def test_che_do_ghim_giu_trong_suot_khong_quang_den(widget, monkeypatch):
    """Cơ chế Rainmeter Top-Level: Giữ nguyên WA_TranslucentBackground và lề bóng đổ.
    
    Điều này loại bỏ hoàn toàn lỗi quầng đen bao quanh 4 góc bo tròn của tờ lịch.
    """
    from PySide6.QtCore import Qt
    from qtcalendar.ui import widget_window as ww
    from qtcalendar.core.theme import alpha_of

    monkeypatch.setattr(ww.desktop_pin, "pin", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "unpin", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "is_pinned", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "update_z_order", lambda hwnd: None)

    widget.set_placement("desktop")
    widget.set_opacity(0.5)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget.layout().contentsMargins().left() == ww.SHADOW_MARGIN
    # Nền giấy giữ độ mờ 50%, 4 góc bo tròn có alpha ngoài viền trong suốt
    assert 0.45 < alpha_of(widget._visual_theme.paper) < 0.55


def test_bo_ghim_tro_lai_trong_suot(widget, monkeypatch):
    from PySide6.QtCore import Qt
    from qtcalendar.ui import widget_window as ww
    from qtcalendar.core.theme import alpha_of

    monkeypatch.setattr(ww.desktop_pin, "pin", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "unpin", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "is_pinned", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "update_z_order", lambda hwnd: None)

    widget.set_opacity(0.5)
    widget.set_placement("desktop")
    widget.set_placement("floating")

    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget.layout().contentsMargins().left() == ww.SHADOW_MARGIN
    assert 0.45 < alpha_of(widget._visual_theme.paper) < 0.55


# --------------------------------------------------------------------------- #
# Lịch tháng dưới chân bloc
# --------------------------------------------------------------------------- #
def test_mo_lich_thang_cao_them_dung_extra(widget):
    w, h = widget.width(), widget.height()
    widget.set_show_month(True)
    assert widget.width() == w
    assert widget.height() == h + month_extra_height(w, widget._settings.scale)
    assert widget._settings.show_month is True


def test_dong_lich_thang_ve_kich_thuoc_cu(widget):
    widget.set_show_month(True)
    widget.set_show_month(False)
    assert (widget.width(), widget.height()) == (BASE_WIDTH, BASE_HEIGHT)
    assert widget._settings.show_month is False


def test_bat_tat_khong_doi_he_so_phong(widget):
    truoc = widget.content_scale()
    widget.set_show_month(True)
    assert widget.content_scale() == pytest.approx(truoc)
    widget.set_show_month(False)
    assert widget.content_scale() == pytest.approx(truoc)


def test_chua_mo_thi_chua_tao_lich_thang(widget):
    assert widget._month is None


def test_hai_to_giay_khi_mo(widget, qapp):
    assert len(widget._sheet_rects()) == 1
    widget.set_show_month(True)
    qapp.processEvents()
    bloc, month = widget._sheet_rects()
    assert month.top() > bloc.bottom()
    assert month.width() == bloc.width()


def test_nhay_dup_bat_tat_lich_thang(widget):
    QTest.mouseDClick(widget, Qt.LeftButton, pos=widget.rect().center())
    assert widget._settings.show_month is True


def test_khoi_dong_voi_show_month_true(qapp):
    s = Settings(show_month=True)
    w = CalendarWidget(s)  # app.py không gọi apply_settings lúc khởi động
    try:
        assert w._month is not None
        assert w.height() == s.height + month_extra_height(s.width, s.scale)
    finally:
        w.deleteLater()


def test_bat_tat_khi_dang_ghim_khong_bo_ghim(widget, monkeypatch):
    from qtcalendar.ui import widget_window as ww

    calls: list[int] = []
    monkeypatch.setattr(ww.desktop_pin, "pin", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "is_pinned", lambda hwnd: True)
    monkeypatch.setattr(ww.desktop_pin, "update_z_order", lambda hwnd: None)
    monkeypatch.setattr(
        ww.desktop_pin, "unpin", lambda hwnd: calls.append(hwnd) or True
    )
    widget.set_placement("desktop")
    calls.clear()
    widget.set_show_month(True)
    widget.set_show_month(False)
    assert calls == []
