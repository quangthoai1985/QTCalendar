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
def widget(qapp, monkeypatch):
    settings = Settings()
    settings.x, settings.y = 100, 100
    view = CalendarWidget(settings)
    # Màn hình ``offscreen`` chỉ 800×800 – nhỏ hơn màn hình thật, khiến lịch
    # tháng mở ra bị thu nhỏ cho vừa. Giả lập vùng làm việc của màn hình
    # Full HD; các test về vừa màn hình tự đặt kích thước riêng.
    monkeypatch.setattr(view, "_available_rect", lambda: QRect(0, 0, 1920, 1040))
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


# --------------------------------------------------------------------------- #
# Tab kéo ở chân widget
# --------------------------------------------------------------------------- #
def test_tab_dong_cham_mep_duoi_bloc(widget):
    tab = widget._tab
    assert tab.isVisible()
    assert tab.label() == "THÁNG"
    assert tab.geometry().top() == widget._bloc.geometry().bottom() + 1
    assert abs(tab.geometry().center().x() - widget._bloc.geometry().center().x()) <= 1
    assert widget.rect().contains(tab.geometry())


def test_tab_mo_cham_mep_duoi_lich_thang(widget):
    widget.set_show_month(True)
    tab = widget._tab
    assert tab.label() == "ẨN"
    assert tab.geometry().top() == widget._month.geometry().bottom() + 1
    assert widget.rect().contains(tab.geometry())


def test_bam_tab_bat_tat(widget):
    QTest.mouseClick(widget._tab, Qt.LeftButton)
    assert widget._settings.show_month is True
    QTest.mouseClick(widget._tab, Qt.LeftButton)
    assert widget._settings.show_month is False


def test_khong_con_nut_noi_thang(widget):
    assert not hasattr(widget, "_view_btn")


def test_doi_theme_khi_mo_cap_nhat_tab_va_lich_thang(widget):
    from qtcalendar.core.theme import alpha_of

    widget.set_show_month(True)
    widget.set_theme_name("dem_sao")
    assert widget._tab._theme.name == "dem_sao"
    assert widget._month._theme.name == "dem_sao"
    widget.set_opacity(0.4)
    assert alpha_of(widget._tab._theme.paper) == pytest.approx(0.4, abs=0.02)


# --------------------------------------------------------------------------- #
# Kéo giãn / vừa màn hình khi lịch tháng đang mở
# --------------------------------------------------------------------------- #
def _gia_man_hinh(monkeypatch, view, rect):
    monkeypatch.setattr(view, "_available_rect", lambda: QRect(*rect))


def test_keo_khi_mo_luu_kich_thuoc_bloc(widget):
    widget.set_show_month(True)
    widget.begin_resize(QPoint(0, 0))
    widget.drag_resize(QPoint(60, 40))
    widget.end_resize()
    assert widget._settings.width == BASE_WIDTH + 60
    assert widget._settings.height == BASE_HEIGHT + 40
    assert widget.height() == widget._settings.height + month_extra_height(
        widget.width(), widget._settings.scale
    )


def test_cham_day_man_hinh_thi_doi_len(widget, monkeypatch):
    _gia_man_hinh(monkeypatch, widget, (0, 0, 1920, 1040))
    widget.move(100, 600)
    widget.set_show_month(True)
    assert widget.pos().y() + widget.height() - SHADOW_MARGIN <= 1040
    assert widget._settings.width == BASE_WIDTH  # chỉ dời, không thu nhỏ


def test_cao_hon_man_hinh_thi_thu_nho(widget, monkeypatch):
    _gia_man_hinh(monkeypatch, widget, (0, 0, 1366, 700))
    widget.move(100, 0)
    widget.set_show_month(True)
    assert widget.height() - 2 * SHADOW_MARGIN <= 700
    assert widget._settings.width < BASE_WIDTH
    assert widget._settings.width / widget._settings.height == pytest.approx(
        BASE_WIDTH / BASE_HEIGHT, rel=0.03
    )


def test_dat_lai_kich_thuoc_khi_mo(widget):
    widget.set_show_month(True)
    widget.resize(500, 1200)
    widget.reset_size()
    assert widget._settings.show_month is True
    assert (widget._settings.width, widget._settings.height) == (BASE_WIDTH, BASE_HEIGHT)
    assert widget.height() == BASE_HEIGHT + month_extra_height(
        BASE_WIDTH, widget._settings.scale
    )


def test_khoi_dong_mo_san_gan_day_van_vua_man_hinh(qapp, monkeypatch):
    s = Settings(show_month=True, x=100, y=900)
    w = CalendarWidget(s)
    try:
        monkeypatch.setattr(w, "_available_rect", lambda: QRect(0, 0, 1920, 1040))
        w.restore_position()  # đúng thứ tự AppController.start()
        assert w.pos().y() + w.height() - SHADOW_MARGIN <= 1040
    finally:
        w.deleteLater()


# --------------------------------------------------------------------------- #
# Bấm ngày trong lịch tháng
# --------------------------------------------------------------------------- #
def _ngay_khac_hom_nay() -> date:
    from qtcalendar.core import calendar_service

    hom_nay = calendar_service.today()
    return hom_nay.replace(day=15 if hom_nay.day != 15 else 16)


def test_bam_ngay_doi_bloc_va_giu_lich_thang(widget):
    ngay = _ngay_khac_hom_nay()
    widget.set_show_month(True)
    widget._on_day_activated(ngay)
    assert widget._settings.show_month is True
    assert widget._month.isHidden() is False
    assert widget._bloc.current_day.solar == ngay
    assert widget._month.selected() == ngay


def test_ve_hom_nay_bo_chon(widget):
    ngay = _ngay_khac_hom_nay()
    widget.set_show_month(True)
    widget._on_day_activated(ngay)
    assert widget._month.selected() == ngay
    widget.go_today()
    assert widget._month.selected() is None


def test_qua_nua_dem_bo_chon(widget):
    ngay = _ngay_khac_hom_nay()
    widget.set_show_month(True)
    widget._on_day_activated(ngay)
    assert widget._month.selected() == ngay
    widget._midnight_timer.stop()
    widget._on_new_day()
    assert widget._selected is None
    assert widget._month.selected() is None


# --------------------------------------------------------------------------- #
# Hồi quy từ review toàn nhánh
# --------------------------------------------------------------------------- #
def test_nhay_dup_o_ngay_khong_dong_lich_thang(widget):
    widget.set_show_month(True)
    cell = next(c for c in widget._month._cells if c.isVisible())
    QTest.mouseDClick(cell, Qt.LeftButton)
    assert widget._settings.show_month is True
    assert widget._month.isHidden() is False


def test_dat_lai_kich_thuoc_khi_mo_tren_man_hinh_thap(widget, monkeypatch):
    _gia_man_hinh(monkeypatch, widget, (0, 0, 1280, 672))
    widget.move(100, 0)
    widget.set_show_month(True)  # bị thu nhỏ cho vừa ⇒ "Đặt lại" vẫn bật
    widget.reset_size()
    assert widget.pos().y() + SHADOW_MARGIN >= 0
    assert widget.pos().y() + widget.height() - SHADOW_MARGIN <= 672


def test_luu_kich_thuoc_khi_ghim_dung_don_vi_logic(widget, monkeypatch):
    """Ghim kiểu Rainmeter vẫn là cửa sổ top-level: toạ độ Qt đã là logic.

    ``GetWindowRect`` trả pixel vật lý (ở 125 % lớn hơn 1,25 lần) – không
    được dùng để lưu kích thước.
    """
    from qtcalendar.platform import win32

    widget.set_show_month(True)
    widget._pinned = True
    g = widget.geometry()
    monkeypatch.setattr(
        win32,
        "get_window_rect",
        lambda hwnd: (
            int(g.x() * 1.25),
            int(g.y() * 1.25),
            int((g.x() + g.width()) * 1.25),
            int((g.y() + g.height()) * 1.25),
        ),
    )
    widget._store_geometry()
    widget._pinned = False
    assert (widget._settings.width, widget._settings.height) == (BASE_WIDTH, BASE_HEIGHT)
