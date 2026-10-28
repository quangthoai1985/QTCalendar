"""Kiểm chứng bảng ngày lễ Dương lịch + Âm lịch (``core/holidays.py``).

Bảng ngày lễ là dữ liệu thuần, có thể kiểm tra trực tiếp:

* 12 ngày lễ Dương lịch quen thuộc của Việt Nam (01/01, 03/02, 08/03, 30/04,
  01/05, 19/05, 01/06, 02/09, 20/10, 20/11, 22/12, 24/12).
* 11 ngày lễ Âm lịch (Tết Nguyên Đán 3 ngày, Nguyên Tiêu, Hàn Thực, Giỗ Tổ,
  Phật Đản, Đoan Ngọ, Vu Lan, Trung Thu, Ông Công Ông Táo).
* Ngày lễ Âm lịch **không** áp dụng cho tháng nhuận (rằm tháng Tám nhuận
  không phải Tết Trung Thu).
* Nếu trùng cả Dương lịch và Âm lịch thì nối bằng ``" · "``.
"""

from __future__ import annotations

from datetime import date

import pytest

from qtcalendar.core import lunar_precise
from qtcalendar.core.holidays import (
    LUNAR_HOLIDAYS,
    SOLAR_HOLIDAYS,
    holiday_for,
    lunar_holiday,
    solar_holiday,
)
from qtcalendar.core.types import LunarDate


# ===========================================================================
# 1. Tính toàn vẹn của bảng dữ liệu
# ===========================================================================
def test_bang_ngay_le_du_so_luong_va_khoa_hop_le():
    """Hai bảng phải đủ số lượng và mọi khoá (tháng, ngày) đều dùng được."""
    assert len(SOLAR_HOLIDAYS) == 12
    assert len(LUNAR_HOLIDAYS) == 11
    for thang, ngay in SOLAR_HOLIDAYS:
        assert 1 <= thang <= 12 and 1 <= ngay <= 31
        # Ngày thực tế phải tồn tại trong lịch Dương (bắt lỗi 31/04, 30/02…).
        date(2026, thang, ngay)
    for thang, ngay in LUNAR_HOLIDAYS:
        assert 1 <= thang <= 12 and 1 <= ngay <= 30  # tháng âm tối đa 30 ngày
    # Không có tên lễ rỗng.
    assert all(ten.strip() for ten in SOLAR_HOLIDAYS.values())
    assert all(ten.strip() for ten in LUNAR_HOLIDAYS.values())


# ===========================================================================
# 2. Ngày lễ Dương lịch
# ===========================================================================
@pytest.mark.parametrize(
    "ngay,ten_le",
    [
        (date(2026, 1, 1), "Tết Dương lịch"),
        (date(2026, 2, 3), "Thành lập Đảng"),
        (date(2026, 3, 8), "Quốc tế Phụ nữ"),
        (date(2026, 4, 30), "Giải phóng miền Nam"),
        (date(2026, 5, 1), "Quốc tế Lao động"),
        (date(2026, 5, 19), "Sinh nhật Bác Hồ"),
        (date(2026, 6, 1), "Quốc tế Thiếu nhi"),
        (date(2026, 9, 2), "Quốc khánh"),
        (date(2026, 10, 20), "Phụ nữ Việt Nam"),
        (date(2026, 11, 20), "Nhà giáo Việt Nam"),
        (date(2026, 12, 22), "Thành lập QĐND Việt Nam"),
        (date(2026, 12, 24), "Giáng sinh"),
    ],
)
def test_solar_holiday_theo_bang(ngay: date, ten_le: str):
    """Từng ngày lễ Dương lịch trong bảng phải tra ra đúng tên."""
    assert solar_holiday(ngay) == ten_le


def test_solar_holiday_ngay_thuong_tra_none():
    """Ngày không phải lễ Dương lịch phải trả ``None``."""
    assert solar_holiday(date(2026, 10, 28)) is None
    assert solar_holiday(date(2026, 2, 17)) is None  # Tết âm, không phải lễ dương


# ===========================================================================
# 3. Ngày lễ Âm lịch
# ===========================================================================
@pytest.mark.parametrize(
    "am,ten_le",
    [
        (LunarDate(1, 1, 2026, False), "Tết Nguyên Đán"),
        (LunarDate(2, 1, 2026, False), "Mùng 2 Tết"),
        (LunarDate(3, 1, 2026, False), "Mùng 3 Tết"),
        (LunarDate(15, 1, 2026, False), "Tết Nguyên Tiêu"),
        (LunarDate(3, 3, 2026, False), "Tết Hàn Thực"),
        (LunarDate(10, 3, 2026, False), "Giỗ Tổ Hùng Vương"),
        (LunarDate(15, 4, 2026, False), "Lễ Phật Đản"),
        (LunarDate(5, 5, 2026, False), "Tết Đoan Ngọ"),
        (LunarDate(15, 7, 2026, False), "Lễ Vu Lan"),
        (LunarDate(15, 8, 2026, False), "Tết Trung Thu"),
        (LunarDate(23, 12, 2026, False), "Ông Công Ông Táo"),
    ],
)
def test_lunar_holiday_theo_bang(am: LunarDate, ten_le: str):
    """Từng ngày lễ Âm lịch trong bảng phải tra ra đúng tên."""
    assert lunar_holiday(am) == ten_le


def test_lunar_holiday_khong_ap_dung_thang_nhuan():
    """Rằm tháng Tám *nhuận* không được coi là Tết Trung Thu."""
    assert lunar_holiday(LunarDate(15, 8, 2026, True)) is None
    assert lunar_holiday(LunarDate(1, 1, 2026, True)) is None
    # Tháng nhuận vẫn không phải lễ, nhưng tháng thường cùng ngày thì có.
    assert lunar_holiday(LunarDate(15, 8, 2026, False)) == "Tết Trung Thu"


def test_lunar_holiday_ngay_thuong_tra_none():
    """Ngày âm không nằm trong bảng phải trả ``None``."""
    assert lunar_holiday(LunarDate(19, 9, 2026, False)) is None
    assert lunar_holiday(LunarDate(30, 12, 2026, False)) is None


# ===========================================================================
# 4. Gộp hai bảng
# ===========================================================================
def test_holiday_for_tet_2026():
    """17/02/2026 chỉ có lễ âm → trả đúng tên Tết Nguyên Đán."""
    ngay = date(2026, 2, 17)
    am = lunar_precise.solar_to_lunar(ngay.day, ngay.month, ngay.year)
    assert holiday_for(ngay, am) == "Tết Nguyên Đán"


def test_holiday_for_ngay_le_duong_lich():
    """02/09/2026 là Quốc khánh (lễ dương lịch)."""
    ngay = date(2026, 9, 2)
    am = lunar_precise.solar_to_lunar(ngay.day, ngay.month, ngay.year)
    assert holiday_for(ngay, am) == "Quốc khánh"


def test_holiday_for_gop_ca_hai_bang_khi_trung():
    """Ngày vừa là mùng 1 Tết Âm vừa là 01/01 Dương → nối bằng " · "."""
    ngay = date(2026, 1, 1)
    am = LunarDate(1, 1, 2026)
    assert holiday_for(ngay, am) == "Tết Nguyên Đán · Tết Dương lịch"


def test_holiday_for_ngay_khong_le_tra_none():
    """Ngày không có lễ nào phải trả ``None`` (để UI không vẽ nhãn rỗng)."""
    ngay = date(2026, 10, 28)
    am = LunarDate(19, 9, 2026)
    assert holiday_for(ngay, am) is None


# ===========================================================================
# 5. Đối chiếu vài ngày lễ thật qua engine
# ===========================================================================
@pytest.mark.parametrize(
    "duong,am,ten_le",
    [
        # Tết Trung Thu 15/8 âm các năm đã biết.
        ((25, 9, 2026), (15, 8, 2026), "Tết Trung Thu"),
        ((29, 9, 2023), (15, 8, 2023), "Tết Trung Thu"),
        ((17, 9, 2024), (15, 8, 2024), "Tết Trung Thu"),
        # Giỗ Tổ 10/3 âm.
        ((26, 4, 2026), (10, 3, 2026), "Giỗ Tổ Hùng Vương"),
        ((18, 4, 2024), (10, 3, 2024), "Giỗ Tổ Hùng Vương"),
        # Tết Đoan Ngọ 5/5 âm.
        ((19, 6, 2026), (5, 5, 2026), "Tết Đoan Ngọ"),
        ((10, 6, 2024), (5, 5, 2024), "Tết Đoan Ngọ"),
    ],
)
def test_ngay_le_am_lich_tren_lich_that(
    duong: tuple[int, int, int], am: tuple[int, int, int], ten_le: str
):
    """Đổi ngày âm lễ hội ra dương lịch rồi tra ``holiday_for`` phải ra đúng tên."""
    ngay = date(duong[2], duong[1], duong[0])
    am_ngay = lunar_precise.solar_to_lunar(ngay.day, ngay.month, ngay.year)
    assert am_ngay == LunarDate(am[0], am[1], am[2], False)
    assert holiday_for(ngay, am_ngay) == ten_le
