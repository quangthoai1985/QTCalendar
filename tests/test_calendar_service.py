"""Kiểm chứng tầng dịch vụ ``calendar_service`` (DayInfo + lưới tháng).

Các mốc đối chứng bên ngoài dùng ở đây:

* Ngày **28/10/2026**: âm lịch **19/9 năm Bính Ngọ**, ngày Can Chi **Ất Hợi**,
  tiết khí **Sương Giáng**, thứ Tư.
* Ngày **17/02/2026** là mùng 1 Tết Bính Ngọ.
* Ngày **22/03/2023** là mùng 1 tháng Hai nhuận (Quý Mão).
* Lưới lịch tháng phải đúng hình học: 7 cột, mỗi tuần 7 ngày liên tiếp,
  số hàng tối thiểu đủ chứa tháng, ô rìa thuộc tháng trước/sau.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from qtcalendar.core import calendar_service, lunar, lunar_precise
from qtcalendar.core.types import LunarDate


# ===========================================================================
# 1. DayInfo cho các ngày cụ thể
# ===========================================================================
def test_day_info_28_10_2026_day_du_thong_tin():
    """Yêu cầu của task: 28/10/2026 = âm 19/9, ngày Ất Hợi, tiết Sương Giáng."""
    info = calendar_service.get_day_info(date(2026, 10, 28))
    assert info.solar == date(2026, 10, 28)
    assert info.lunar == LunarDate(19, 9, 2026, False)
    # Thứ Tư (index 2 theo quy ước date.weekday()).
    assert info.weekday_index == 2
    assert info.weekday_name == "Thứ Tư"
    assert info.weekday_short == "T4"
    assert info.is_sunday is False
    # Can Chi năm/tháng/ngày.
    assert info.year_can_chi.text == "Bính Ngọ"
    assert info.month_can_chi.text == "Mậu Tuất"  # tháng Chín năm Bính
    assert info.day_can_chi.text == "Ất Hợi"
    assert info.zodiac == "Ngựa"
    # Tiết khí và giờ hoàng đạo.
    assert info.tiet_khi == "Sương Giáng"
    assert len(info.auspicious_hours) == 6
    # Ngày Hợi tháng Chín là ngày hoàng đạo theo quy tắc dân gian.
    assert info.is_auspicious_day is True
    assert info.holiday is None
    # Dòng chữ hiển thị trên bloc.
    assert info.lunar_day_text == "Ngày 19"
    assert info.lunar_line == "Ngày 19 tháng Chín"


def test_day_info_ngay_tet_2026():
    """17/02/2026 là mùng 1 Tết Bính Ngọ (thứ Ba), có ghi chú ngày lễ."""
    info = calendar_service.get_day_info(date(2026, 2, 17))
    assert info.lunar == LunarDate(1, 1, 2026, False)
    assert info.is_lunar_new_year is True
    assert info.is_month_start is True
    assert info.weekday_name == "Thứ Ba"
    assert info.holiday == "Tết Nguyên Đán"
    assert info.year_can_chi.text == "Bính Ngọ"


def test_day_info_chu_nhat_va_thu_bay():
    """Chủ nhật được đánh dấu đúng để UI tô màu cuối tuần."""
    chu_nhat = calendar_service.get_day_info(date(2026, 10, 25))
    assert chu_nhat.weekday_index == 6
    assert chu_nhat.weekday_name == "Chủ Nhật"
    assert chu_nhat.weekday_short == "CN"
    assert chu_nhat.is_sunday is True
    thu_bay = calendar_service.get_day_info(date(2026, 10, 24))
    assert thu_bay.weekday_index == 5
    assert thu_bay.weekday_short == "T7"


def test_day_info_thang_nhuan_2023():
    """22/03/2023 là mùng 1 tháng Hai nhuận – phải hiện đúng chữ "(nhuận)"."""
    info = calendar_service.get_day_info(date(2023, 3, 22))
    assert info.lunar == LunarDate(1, 2, 2023, True)
    assert info.is_month_start is True
    assert info.lunar_day_text == "Mùng 1"
    assert info.lunar_line == "Mùng 1 tháng Hai (nhuận)"


def test_day_info_ram_va_mung_mot():
    """Rằm (15 âm) và mùng 1 được nhận diện để UI đánh dấu."""
    ram = calendar_service.get_day_info(date(2026, 9, 25))  # 15/8 Trung Thu
    assert ram.lunar == LunarDate(15, 8, 2026, False)
    assert ram.is_full_moon is True
    assert ram.lunar_day_text == "Rằm"
    assert ram.holiday == "Tết Trung Thu"
    mung_mot = calendar_service.get_day_info(date(2026, 10, 10))  # 1/9
    assert mung_mot.lunar == LunarDate(1, 9, 2026, False)
    assert mung_mot.is_month_start is True


@pytest.mark.parametrize(
    "ngay,ten_le",
    [
        (date(2026, 1, 1), "Tết Dương lịch"),
        (date(2026, 9, 2), "Quốc khánh"),
        (date(2026, 4, 26), "Giỗ Tổ Hùng Vương"),  # 10/3 âm
        (date(2026, 6, 19), "Tết Đoan Ngọ"),  # 5/5 âm
    ],
)
def test_day_info_co_ghi_chu_ngay_le(ngay: date, ten_le: str):
    """``DayInfo.holiday`` lấy đúng bảng ngày lễ của ``holidays.py``."""
    assert calendar_service.get_day_info(ngay).holiday == ten_le


def test_get_day_info_duoc_cache():
    """Cùng ngày + cùng engine trả về đúng một đối tượng (cache theo ngày)."""
    assert calendar_service.get_day_info(date(2026, 10, 28)) is calendar_service.get_day_info(
        date(2026, 10, 28)
    )


# ===========================================================================
# 2. Lưới lịch tháng
# ===========================================================================
def test_luoi_thang_10_2026_hinh_hoc_dung():
    """Lưới 10/2026: 7 cột; 01/10/2026 là Thứ Năm nên lưới tối thiểu 5 hàng.

    Ghi chú QA: mô tả task ghi "6 hàng" nhưng theo hình học lịch, tháng bắt
    đầu Thứ Năm và có 31 ngày chỉ cần 5 hàng (35 ô). Nếu UI muốn luôn đủ
    6 hàng thì view phải tự đệm thêm — service cố tình trả số hàng tối thiểu.
    """
    assert date(2026, 10, 1).weekday() == 3  # Thứ Năm
    luoi = calendar_service.build_month_grid(2026, 10)
    assert luoi.year == 2026 and luoi.month == 10
    assert luoi.title == "Tháng 10 / 2026"
    assert luoi.lunar_month_title == "Tháng Chín"
    assert len(luoi.weeks) == 5
    assert all(len(tuan) == 7 for tuan in luoi.weeks)
    # Ô đầu là 28/09 (thứ Hai), ô cuối là 01/11 (Chủ Nhật).
    assert luoi.weeks[0][0].solar == date(2026, 9, 28)
    assert luoi.weeks[-1][-1].solar == date(2026, 11, 1)


def test_luoi_thang_can_6_hang_thi_tra_6_hang():
    """Tháng 8/2026 bắt đầu Thứ Bảy + 31 ngày => đủ 6 hàng (42 ô)."""
    luoi = calendar_service.build_month_grid(2026, 8)
    assert date(2026, 8, 1).weekday() == 5  # Thứ Bảy
    assert len(luoi.weeks) == 6


@pytest.mark.parametrize(
    "nam,thang",
    [(2026, 10), (2026, 8), (2023, 3), (2023, 2), (2024, 2), (2020, 5), (2033, 12), (2026, 2)],
    ids=["10/2026", "08/2026", "03/2023", "02/2023", "02/2024", "05/2020", "12/2033", "02/2026"],
)
def test_moi_tuan_dung_7_ngay_lien_tuc_va_du_ngay_trong_thang(nam: int, thang: int):
    """Lưới phải là các ngày liên tiếp, mỗi tuần 7 ngày, phủ đủ tháng, đúng thứ."""
    luoi = calendar_service.build_month_grid(nam, thang)
    tat_ca = [info for tuan in luoi.weeks for info in tuan]
    assert len(tat_ca) == 7 * len(luoi.weeks)
    # Các ngày liên tiếp nhau, không thiếu không lặp.
    for truoc, sau in zip(tat_ca, tat_ca[1:]):
        assert sau.solar == truoc.solar + timedelta(days=1)
    # Mọi ngày trong tháng xuất hiện đúng một lần, đúng thứ tự tăng dần.
    trong_thang = [info.solar.day for info in tat_ca if info.solar.month == thang]
    assert trong_thang == list(range(1, calendar.monthrange(nam, thang)[1] + 1))
    # Căn cột: ô thứ j trong tuần có weekday_index == j (tuần bắt đầu Thứ Hai).
    for tuan in luoi.weeks:
        for j, info in enumerate(tuan):
            assert info.weekday_index == j
    # Số hàng tối thiểu đủ chứa tháng (công thức hình học độc lập với impl).
    dau_thang = date(nam, thang, 1)
    o_dem = dau_thang.weekday()  # số ô trống đầu lưới khi tuần bắt đầu Thứ Hai
    so_ngay = calendar.monthrange(nam, thang)[1]
    so_hang_ky_vong = -(-(o_dem + so_ngay) // 7)
    assert len(luoi.weeks) == so_hang_ky_vong


def test_luoi_bat_dau_bang_chu_nhat():
    """``first_day_of_week=6``: cột đầu là Chủ Nhật, mọi ô lệch đúng 1 cột."""
    luoi = calendar_service.build_month_grid(2026, 10, first_day_of_week=6)
    assert luoi.weeks[0][0].solar == date(2026, 9, 27)  # Chủ Nhật
    for tuan in luoi.weeks:
        for j, info in enumerate(tuan):
            assert info.weekday_index == (6 + j) % 7


@pytest.mark.parametrize("thang", [0, 13, -1])
def test_luoi_bao_loi_voi_thang_duong_sai(thang: int):
    """Tháng dương ngoài 1..12 phải ném ``ValueError``."""
    with pytest.raises(ValueError):
        calendar_service.build_month_grid(2026, thang)


@pytest.mark.parametrize("ngay_dau_tuan", [-1, 7])
def test_luoi_bao_loi_voi_first_day_of_week_sai(ngay_dau_tuan: int):
    """``first_day_of_week`` ngoài 0..6 phải ném ``ValueError``."""
    with pytest.raises(ValueError):
        calendar_service.build_month_grid(2026, 10, first_day_of_week=ngay_dau_tuan)


def test_week_header_theo_ngay_dau_tuan():
    """Nhãn 7 cột đổi đúng thứ tự khi tuần bắt đầu Chủ Nhật."""
    assert calendar_service.week_header() == ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
    assert calendar_service.week_header(6) == ("CN", "T2", "T3", "T4", "T5", "T6", "T7")
    assert calendar_service.week_header(3) == ("T5", "T6", "T7", "CN", "T2", "T3", "T4")


def test_month_grid_days_duyet_theo_thu_tu_doc():
    """``MonthGrid.days`` duyệt đủ 7 × số tuần ô theo thứ tự đọc."""
    luoi = calendar_service.build_month_grid(2026, 10)
    ds = list(luoi.days)
    assert len(ds) == 7 * len(luoi.weeks)
    assert ds[0].solar == luoi.weeks[0][0].solar
    assert ds[-1].solar == luoi.weeks[-1][-1].solar


# ===========================================================================
# 3. Chuyển tháng và dựng lưới từ chuỗi neo
# ===========================================================================
@pytest.mark.parametrize(
    "nam,thang,delta,ky_vong",
    [
        (2026, 10, 1, (2026, 11)),
        (2026, 10, -1, (2026, 9)),
        (2026, 12, 1, (2027, 1)),
        (2026, 1, -1, (2025, 12)),
        (2026, 10, 0, (2026, 10)),
        (2026, 10, 12, (2027, 10)),
        (2026, 10, -22, (2024, 12)),
    ],
)
def test_shift_month(nam: int, thang: int, delta: int, ky_vong: tuple[int, int]):
    """Dịch tháng phải xử lý đúng cả khi vượt qua ranh giới năm."""
    assert calendar_service.shift_month(nam, thang, delta) == ky_vong


def test_month_grid_from_anchor_hop_le():
    """Chuỗi neo ``YYYY-MM`` hợp lệ dựng đúng lưới tháng đó."""
    luoi = calendar_service.month_grid_from_anchor("2026-10")
    assert (luoi.year, luoi.month) == (2026, 10)
    luoi = calendar_service.month_grid_from_anchor("2023-03")
    assert luoi.lunar_month_title == "Tháng Hai (nhuận)"


@pytest.mark.parametrize("anchor", ["", "khong-hop-le", "2026-13", "1800-01", "2026-1x"])
def test_month_grid_from_anchor_khong_hop_le_dung_thang_hien_tai(
    anchor: str, monkeypatch: pytest.MonkeyPatch
):
    """Neo rỗng/hỏng phải lùi về tháng hiện tại (qua ``today()``)."""
    ngay_gia = date(2026, 10, 28)
    monkeypatch.setattr(calendar_service, "today", lambda: ngay_gia)
    luoi = calendar_service.month_grid_from_anchor(anchor)
    assert (luoi.year, luoi.month) == (2026, 10)


# ===========================================================================
# 4. Engine
# ===========================================================================
def test_get_engine_mac_dinh_va_theo_ten():
    """Mặc định là engine ``precise``; tên lạ cũng lùi về precise."""
    assert calendar_service.DEFAULT_ENGINE == "precise"
    assert calendar_service.get_engine() is lunar_precise
    assert calendar_service.get_engine("precise") is lunar_precise
    assert calendar_service.get_engine("hnd") is lunar
    assert calendar_service.get_engine("khong-ton-tai") is lunar_precise
    assert set(calendar_service.ENGINES) == {"precise", "hnd"}


def test_doi_engine_cho_ket_qua_khac_o_ngay_bien():
    """Ngày 22/03/2023: precise = 1/2 nhuận, HND = 2/2 (đã biết, xem test_lunar_hnd)."""
    chuan = calendar_service.get_day_info(date(2023, 3, 22), "precise")
    hnd = calendar_service.get_day_info(date(2023, 3, 22), "hnd")
    assert chuan.lunar == LunarDate(1, 2, 2023, True)
    assert hnd.lunar == LunarDate(2, 2, 2023, False)


def test_iter_days_sinh_ngay_lien_tiep():
    """``iter_days`` sinh đúng số ngày, liên tiếp, không trùng."""
    ds = list(calendar_service.iter_days(date(2026, 10, 28), 5))
    assert [d.day for d in ds] == [28, 29, 30, 31, 1]
    assert ds[-1] == date(2026, 11, 1)
    assert list(calendar_service.iter_days(date(2026, 10, 28), 0)) == []
