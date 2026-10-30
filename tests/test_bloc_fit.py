"""Kiểm thử chữ trên lịch bloc tự thu nhỏ cho vừa khung thay vì bị cắt.

Khoá lại các lỗi ``scripts/preview_bloc.py`` từng bắt được:

1. Nhãn cột chân lịch chỉ thu nhỏ một lần theo advance nên vẫn lố 1–8px.
2. "MÙNG 1" cỡ cố định tràn khỏi cột giữa, chạm vạch phân cột.
3. Châm ngôn 2 dòng trên dải hoa văn mất chân chữ (khung chỉ cao ``h - 6``).
4. Dòng nguồn dính sát ca dao khi dòng cuối có chân chữ (g, y, dấu nặng).
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QRegion  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from _fonts import load_family  # noqa: E402
from qtcalendar.core.calendar_service import get_day_info  # noqa: E402
from qtcalendar.core.theme import get_theme  # noqa: E402
from qtcalendar.core.types import Quote  # noqa: E402
from qtcalendar.ui.bloc_view import (  # noqa: E402
    _DEFAULT_MOTTO,
    BlocView,
    _ink_extent,
    _LunarPill,
    _TopArtBanner,
)
from qtcalendar.ui.styles import px  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="font hệ thống Windows"
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    for family in ("Segoe UI", "Segoe UI Black", "Palatino Linotype"):
        load_family(family)
    yield app


def _ink_rows(widget: QWidget) -> tuple[int, int] | None:
    """Hàng điểm ảnh đầu/cuối có mực của ``widget`` (toạ độ trong widget cha)."""
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag(0))
    rows = [
        y
        for y in range(image.height())
        if any(image.pixelColor(x, y).alpha() >= 64 for x in range(image.width()))
    ]
    return (widget.y() + rows[0], widget.y() + rows[-1]) if rows else None


def test_nhan_nhieu_dong_thu_nho_toi_khi_moi_dong_lot(qapp):
    view = BlocView()
    text = "Tháng Mậu Tuất\nNgày Nhâm Tuất\nNăm Bính Ngọ"
    font = view._fit_label_font(text, "Segoe UI", 10, 55, 6, QFont.Weight.Medium)
    assert font.pixelSize() < 10
    metrics = QFontMetricsF(font)
    for line in text.split("\n"):
        assert _ink_extent(metrics, line) <= 55 - 2


def test_thu_nho_thi_khoang_gian_chu_co_theo(qapp):
    view = BlocView()
    font = view._fit_label_font("GIỜ HOÀNG ĐẠO", "Segoe UI", 9, 50, 6, QFont.Weight.Bold, spacing=1.0)
    assert font.pixelSize() < 9
    # Qt lưu khoảng giãn chữ theo đơn vị 1/64 px
    assert font.letterSpacing() == pytest.approx(font.pixelSize() / 9, abs=1 / 64)


def test_du_cho_thi_giu_nguyen_co_chu(qapp):
    view = BlocView()
    font = view._fit_label_font("THỨ TƯ", "Segoe UI", 19, 200, 10, QFont.Weight.Black, spacing=2.0)
    assert font.pixelSize() == 19
    assert font.letterSpacing() == pytest.approx(2.0)


def test_mung_1_thu_nho_cho_lot_cot_giua(qapp):
    pill = _LunarPill()
    font = QFont("Segoe UI")
    font.setPixelSize(28)
    font.setWeight(QFont.Weight.Bold)
    pill.configure("MÙNG 1", font, ink=QColor("#1E7E34"))

    pill.resize(95, 100)
    tight = QFontMetricsF(pill.font_for_paint()).tightBoundingRect("MÙNG 1")
    assert tight.width() <= 95 - 4

    pill.resize(300, 100)
    assert pill.font_for_paint().pixelSize() == 28


def test_cham_ngon_lot_khung_chu_cua_dai_hoa_van(qapp):
    banner = _TopArtBanner()
    font = QFont("Palatino Linotype")
    font.setPixelSize(13)
    ink = QColor("#6B5946")
    banner.configure(_DEFAULT_MOTTO, accent=ink, accent_2=ink, line=ink, ink_soft=ink, font=font)
    flags = Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value
    for width, height in ((304, 40), (230, 30)):
        banner.resize(width, height)
        rect = banner._text_rect()
        block = QFontMetricsF(banner.font_for_paint()).boundingRect(rect, flags, _DEFAULT_MOTTO)
        assert block.height() <= rect.height() - 1
        assert block.width() <= rect.width()


def test_cham_ngon_khong_tach_chu_xa_hoi():
    assert "xã hội" in _DEFAULT_MOTTO


@pytest.mark.parametrize(
    ("text", "author"),
    [
        ("Trăm năm trong cõi người ta, chữ tài chữ mệnh khéo là ghét nhau.", "Nguyễn Du"),
        ("Uống nước nhớ nguồn.", "Tục ngữ Việt Nam"),
    ],
)
def test_dong_nguon_cach_ca_dao_it_nhat_6px(qapp, text, author):
    view = BlocView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.apply_theme(get_theme("giay_do"), 1.0)
    view.set_day(get_day_info(date(2026, 10, 28)))
    view.set_quote(Quote(text=text, author=author, topic="ca-dao"))
    view.resize(344, 468)
    view.show()
    qapp.processEvents()
    view.refresh()
    qapp.processEvents()

    quote = _ink_rows(view.findChild(QLabel, "QuoteLabel"))
    credit = _ink_rows(view.findChild(QLabel, "CreditLabel"))
    assert quote and credit
    assert credit[0] - quote[1] - 1 >= px(6, view._eff)
    view.hide()
    view.deleteLater()
