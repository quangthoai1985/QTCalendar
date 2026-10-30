"""Kiểm thử lịch tháng :class:`MonthView` khi nằm dưới chân lịch bloc.

* Không còn nút "Ngày" (lịch tháng giờ hiện cùng lúc với bloc).
* Ô của ngày đang xem ở bloc được đánh dấu (:meth:`MonthView.set_selected`),
  khác với ô hôm nay vốn đã tô đầy màu.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from qtcalendar.ui.month_view import MonthView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def view(qapp):
    widget = MonthView()
    widget.resize(344, 420)
    widget.set_today(date(2026, 10, 28))
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


def test_khong_con_nut_ngay_va_tin_hieu_bloc(view):
    assert not hasattr(view, "_btn_bloc")
    assert not hasattr(view, "bloc_requested")


def test_set_selected_danh_dau_dung_mot_o(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 15))
    marked = [c for c in view._cells if c.isVisible() and c.is_selected()]
    assert len(marked) == 1
    assert marked[0]._info.solar == date(2026, 10, 15)
    assert view.selected() == date(2026, 10, 15)


def test_set_selected_none_bo_danh_dau(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 15))
    view.set_selected(None)
    assert not any(c.is_selected() for c in view._cells)
    assert view.selected() is None


def test_doi_thang_giu_ngay_chon(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 11, 2))
    view.set_month(2026, 11)
    assert any(
        c.is_selected() and c._info.solar == date(2026, 11, 2) for c in view._cells
    )


def test_o_hom_nay_khong_tinh_la_dang_chon(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 28))
    cell = next(c for c in view._cells if c._info.solar == date(2026, 10, 28))
    assert cell.is_selected() is False  # hôm nay đã tô đầy, không vẽ thêm viền
