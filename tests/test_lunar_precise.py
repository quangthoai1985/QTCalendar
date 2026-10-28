"""Kiểm chứng ĐỘC LẬP engine âm lịch chính xác (``lunar_precise``).

Bộ test này cố ý **không lặp lại thuật toán trong ``src/``** mà so kết quả
với dữ liệu bên ngoài, độc lập với mã nguồn:

* Bảng ngày Tết Nguyên Đán 1985–2040 theo lịch Việt Nam (múi giờ UTC+7),
  trong đó có ba mốc đặc biệt:

  - 1985-01-21: Việt Nam đón Tết sớm hơn Trung Quốc (20/02) gần một tháng
    vì quy tắc tháng nhuận của năm 1984 khác nhau.
  - 2007-02-17 và 2030-02-02: điểm sóc rơi sát nửa đêm giờ Hà Nội nên
    Việt Nam lệch Trung Quốc đúng một ngày.

* Danh sách 18 tháng nhuận giai đoạn 1990–2036 của lịch Việt Nam, cùng ngày
  bắt đầu của một số tháng nhuận đã biết rõ (2020 tháng 4 nhuận bắt đầu
  23/05; 2023 tháng 2 nhuận bắt đầu 22/03; 2033 tháng 11 nhuận bắt đầu
  22/12…).
* Các ngày lễ âm lịch quen thuộc hằng năm: Tết Trung Thu (15/8), Giỗ Tổ
  Hùng Vương (10/3), Tết Đoan Ngọ (5/5).
* Các mốc thiên văn độc lập: sóc 06/01/2000 lúc 18:14 TT (ví dụ 49.a trong
  *Astronomical Algorithms* của Meeus), ΔT năm 2000 ≈ 63,8 giây, các điểm
  phân/chí năm 2026 và Đông chí.
* Tính tự nhất quán nội tại: quét từng ngày 1900-01-01 → 2200-12-31 (chuỗi
  ngày âm không được đứt quãng), round-trip Dương ↔ Âm, độ dài năm âm chỉ
  thuộc {353, 354, 355, 383, 384, 385}, tháng âm dài 29 hoặc 30 ngày.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from qtcalendar.core import lunar, lunar_precise
from qtcalendar.core.canchi_constants import TIET_KHI
from qtcalendar.core.types import LunarDate

# ===========================================================================
# Dữ liệu đối chứng bên ngoài
# ===========================================================================
#: Ngày Tết Nguyên Đán theo lịch Việt Nam, 1985–2040: năm -> (tháng, ngày).
TET_VN: dict[int, tuple[int, int]] = {
    1985: (1, 21),
    1986: (2, 9),
    1987: (1, 29),
    1988: (2, 17),
    1989: (2, 6),
    1990: (1, 27),
    1991: (2, 15),
    1992: (2, 4),
    1993: (1, 23),
    1994: (2, 10),
    1995: (1, 31),
    1996: (2, 19),
    1997: (2, 7),
    1998: (1, 28),
    1999: (2, 16),
    2000: (2, 5),
    2001: (1, 24),
    2002: (2, 12),
    2003: (2, 1),
    2004: (1, 22),
    2005: (2, 9),
    2006: (1, 29),
    2007: (2, 17),
    2008: (2, 7),
    2009: (1, 26),
    2010: (2, 14),
    2011: (2, 3),
    2012: (1, 23),
    2013: (2, 10),
    2014: (1, 31),
    2015: (2, 19),
    2016: (2, 8),
    2017: (1, 28),
    2018: (2, 16),
    2019: (2, 5),
    2020: (1, 25),
    2021: (2, 12),
    2022: (2, 1),
    2023: (1, 22),
    2024: (2, 10),
    2025: (1, 29),
    2026: (2, 17),
    2027: (2, 6),
    2028: (1, 26),
    2029: (2, 13),
    2030: (2, 2),
    2031: (1, 23),
    2032: (2, 11),
    2033: (1, 31),
    2034: (2, 19),
    2035: (2, 8),
    2036: (1, 28),
    2037: (2, 15),
    2038: (2, 4),
    2039: (1, 24),
    2040: (2, 12),
}

#: Các năm âm lịch có tháng nhuận, 1990–2036 (lịch Việt Nam): năm -> tháng nhuận.
LEAP_MONTHS: dict[int, int] = {
    1990: 5,
    1993: 3,
    1995: 8,
    1998: 5,
    2001: 4,
    2004: 2,
    2006: 7,
    2009: 5,
    2012: 4,
    2014: 9,
    2017: 6,
    2020: 4,
    2023: 2,
    2025: 6,
    2028: 5,
    2031: 3,
    2033: 11,
    2036: 6,
}

#: Ngày bắt đầu của một số tháng nhuận (đối chiếu lịch vạn niên đã in).
LEAP_START_EXTERNAL: dict[int, tuple[int, int, int]] = {
    # năm: (tháng nhuận, ngày, tháng dương lịch)
    2014: (9, 24, 10),  # tháng 9 nhuận 2014: 24/10 – 21/11
    2017: (6, 23, 7),  # tháng 6 nhuận 2017: 23/07 – 21/08
    2020: (4, 23, 5),  # tháng 4 nhuận 2020: 23/05 – 20/06
    2023: (2, 22, 3),  # tháng 2 nhuận 2023: 22/03 – 19/04
    2025: (6, 25, 7),  # tháng 6 nhuận 2025: 25/07 – 22/08
    2033: (11, 22, 12),  # tháng 11 nhuận 2033: 22/12/2033 – 19/01/2034
}

#: Tết Trung Thu (15/8 âm) – ngày dương lịch đã biết.
TRUNG_THU: dict[int, date] = {
    2020: date(2020, 10, 1),
    2021: date(2021, 9, 21),
    2022: date(2022, 9, 10),
    2023: date(2023, 9, 29),
    2024: date(2024, 9, 17),
    2025: date(2025, 10, 6),
    2026: date(2026, 9, 25),
}

#: Giỗ Tổ Hùng Vương (10/3 âm) – ngày nghỉ lễ đã biết.
GIO_TO: dict[int, date] = {
    2024: date(2024, 4, 18),
    2025: date(2025, 4, 7),
    2026: date(2026, 4, 26),
}

#: Tết Đoan Ngọ (5/5 âm) – ngày dương lịch đã biết.
DOAN_NGO: dict[int, date] = {
    2023: date(2023, 6, 22),
    2024: date(2024, 6, 10),
    2025: date(2025, 5, 31),
    2026: date(2026, 6, 19),
}

#: Tập độ dài năm âm hợp lệ: năm thường 353–355 ngày, năm nhuận 383–385 ngày.
DO_DAI_NAM_AM_HOP_LE = frozenset({353, 354, 355, 383, 384, 385})


# ===========================================================================
# 1. Hợp đồng API tối thiểu (để hoán đổi engine được với ``lunar.py``)
# ===========================================================================
def test_engine_mac_dinh_va_giao_dien_cong_khai():
    """Engine precise phải phơi ra đúng bộ hàm mà ``calendar_service`` dùng."""
    assert lunar_precise.engine_name == "precise"
    assert lunar_precise.TIMEZONE == 7  # giờ Hà Nội, khác Trung Quốc UTC+8
    for ten in (
        "solar_to_lunar",
        "lunar_to_solar",
        "lunar_month_days",
        "lunar_year_months",
        "tiet_khi_index",
        "tiet_khi_name",
    ):
        assert callable(getattr(lunar_precise, ten)), f"thiếu hàm {ten}"
    # Hai engine phải cùng giao diện để hoán đổi được (calendar_service).
    for ten in ("solar_to_lunar", "lunar_to_solar", "lunar_month_days", "lunar_year_months"):
        assert hasattr(lunar, ten), f"engine hnd thiếu hàm {ten}"


# ===========================================================================
# 2. Ngày Tết Nguyên Đán – bảng dữ liệu ngoài 1985–2040
# ===========================================================================
@pytest.mark.parametrize(
    "nam,thang,ngay",
    [(y, m, d) for y, (m, d) in TET_VN.items()],
    ids=[f"Tết-{y}" for y in TET_VN],
)
def test_tet_nguyen_dan_theo_bang_lich_viet_nam(nam: int, thang: int, ngay: int):
    """Mùng 1 tháng Giêng phải rơi đúng ngày Tết đã biết của lịch Việt Nam."""
    duong_lich = date(nam, thang, ngay)
    am = lunar_precise.solar_to_lunar(duong_lich.day, duong_lich.month, duong_lich.year)
    assert am == LunarDate(day=1, month=1, year=nam, leap=False)
    # Chiều ngược lại cũng phải khớp.
    assert lunar_precise.lunar_to_solar(1, 1, nam) == duong_lich


def test_tet_1985_viet_nam_som_hon_trung_quoc():
    """Năm 1985 là ca lệch kinh điển: Việt Nam 21/01, Trung Quốc 20/02.

    Nguyên nhân là quy tắc tháng nhuận của năm 1984 khác nhau giữa hai
    nước, không phải chỉ do chênh múi giờ.
    """
    assert lunar_precise.lunar_to_solar(1, 1, 1985) == date(1985, 1, 21)
    # Ngày 20/02/1985 ở Việt Nam đã là tháng Giêng, không còn là mùng 1.
    am = lunar_precise.solar_to_lunar(20, 2, 1985)
    assert (am.day, am.month, am.year) == (1, 2, 1985)


@pytest.mark.parametrize(
    "nam, ngay_tet",
    [(2007, date(2007, 2, 17)), (2030, date(2030, 2, 2))],
    ids=["2007-lệch-TQ-1-ngày", "2030-lệch-TQ-1-ngày"],
)
def test_soc_sat_nua_dem_nhung_nam_viet_nam_lech_trung_quoc(nam: int, ngay_tet: date):
    """Kiểm tra nguyên nhân lệch: sóc rơi sát nửa đêm giờ Việt Nam.

    Điểm sóc tháng Giêng các năm này rơi vào khoảng 23 giờ ngày hôm trước
    theo giờ UTC+7, nên Việt Nam đón Tết sớm hơn Trung Quốc (UTC+8) đúng
    một ngày. Ta kiểm tra bằng chính tham số ``timezone`` của engine: cùng
    một tuần trăng nhưng UTC+7 và UTC+8 cho hai ngày khác nhau.
    """
    jdn_tet = lunar.jd_from_date(ngay_tet.day, ngay_tet.month, ngay_tet.year)
    k = lunar_precise._lunation_of_day(jdn_tet)
    assert lunar_precise.new_moon_day(k, timezone=7) == jdn_tet, (
        "mùng 1 tháng Giêng phải đúng ngày Tết theo giờ Việt Nam"
    )
    ngay_trung_quoc = lunar_precise.new_moon_day(k, timezone=8)
    assert ngay_trung_quoc == jdn_tet + 1, (
        "với giờ Bắc Kinh, cùng tuần trăng phải sang ngày hôm sau "
        "-> đúng ca lệch Việt Nam/Trung Quốc"
    )


def test_soc_1991_roi_sau_nua_dem_nen_hai_nuoc_cung_ngay():
    """Sóc tháng Giêng 1991 rơi 00:32 giờ Việt Nam nên cả VN và TQ đều 15/02.

    Đây là ca biên rất hẹp (chỉ hơn nửa đêm 32 phút) – dùng để đối chiếu
    với engine xấp xỉ Hồ Ngọc Đức ở ``test_lunar_hnd.py``.
    """
    jdn_tet = lunar.jd_from_date(15, 2, 1991)
    k = lunar_precise._lunation_of_day(jdn_tet)
    assert lunar_precise.new_moon_day(k, timezone=7) == jdn_tet
    assert lunar_precise.new_moon_day(k, timezone=8) == jdn_tet


def test_khoang_cach_giua_hai_tet_ke_nhau_khop_do_dai_nam_am():
    """Bảng Tết bên ngoài phải khớp quy luật: Tết sau − Tết trước = độ dài năm âm.

    Đây là phép kiểm chứng chéo hai nguồn dữ liệu ngoài (bảng Tết 1985–2040
    và bảng 18 tháng nhuận 1990–2036): năm nào có tháng nhuận thì khoảng
    cách giữa hai Tết phải thuộc nhóm dài (383–385 ngày), năm thường thuộc
    nhóm ngắn (353–355 ngày).
    """
    for nam in range(1985, 2040):
        m1, d1 = TET_VN[nam]
        m2, d2 = TET_VN[nam + 1]
        khoang_cach = (date(nam + 1, m2, d2) - date(nam, m1, d1)).days
        assert khoang_cach in DO_DAI_NAM_AM_HOP_LE, (
            f"Tết {nam}->{nam + 1} cách {khoang_cach} ngày (bất thường)"
        )
    # Giai đoạn 1990–2036 có bảng tháng nhuận đầy đủ để đối chiếu chéo.
    for nam in range(1990, 2037):
        m1, d1 = TET_VN[nam]
        m2, d2 = TET_VN[nam + 1]
        khoang_cach = (date(nam + 1, m2, d2) - date(nam, m1, d1)).days
        assert (khoang_cach >= 383) == (nam in LEAP_MONTHS), (
            f"năm {nam}: khoảng cách {khoang_cach} ngày nhưng "
            f"{'có' if nam in LEAP_MONTHS else 'không'} tháng nhuận"
        )


# ===========================================================================
# 3. Tháng nhuận
# ===========================================================================
@pytest.mark.parametrize(
    "nam,thang_nhuan",
    list(LEAP_MONTHS.items()),
    ids=[f"nhuận-{nam}" for nam in LEAP_MONTHS],
)
def test_thang_nhuan_theo_bang_chuan(nam: int, thang_nhuan: int):
    """Mỗi năm nhuận có đúng một tháng nhuận, đúng số tháng đã biết."""
    cac_thang = lunar_precise.lunar_year_months(nam)
    assert len(cac_thang) == 13, f"năm {nam} phải có 13 tháng"
    ds_nhuan = [m for m, la_nhuan in cac_thang if la_nhuan]
    assert ds_nhuan == [thang_nhuan]
    # Chỉ duy nhất một tháng nhuận và nó nằm ngay sau tháng cùng số.
    vi_tri = [i for i, (_, la_nhuan) in enumerate(cac_thang) if la_nhuan][0]
    assert cac_thang[vi_tri - 1] == (thang_nhuan, False)


def test_nhung_nam_khong_nhuan_thi_khong_co_thang_nhuan():
    """Các năm 1990–2036 ngoài bảng nhuận phải có đúng 12 tháng thường.

    Chỉ xét giai đoạn 1990–2036 vì đó là phạm vi có bảng tháng nhuận đầy đủ
    (1985 và 1987 cũng có tháng nhuận nhưng nằm ngoài phạm vi tài liệu này).
    """
    for nam in range(1990, 2037):
        if nam in LEAP_MONTHS:
            continue
        cac_thang = lunar_precise.lunar_year_months(nam)
        assert len(cac_thang) == 12, f"năm {nam} không được có tháng nhuận"
        assert all(not la_nhuan for _, la_nhuan in cac_thang)


@pytest.mark.parametrize(
    "nam,ngay,thang,thang_am",
    [(y, d, m, mn) for y, (mn, d, m) in LEAP_START_EXTERNAL.items()],
    ids=[f"nhuận-{y}-bắt-đầu" for y in LEAP_START_EXTERNAL],
)
def test_ngay_bat_dau_thang_nhuan_theo_lich_van_nien(
    nam: int, ngay: int, thang: int, thang_am: int
):
    """Mùng 1 tháng nhuận rơi đúng ngày đã in trong lịch vạn niên."""
    ngay_mung_mot = lunar_precise.lunar_month_start(nam, thang_am, leap=True)
    assert ngay_mung_mot == date(nam, thang, ngay)
    am = lunar_precise.solar_to_lunar(ngay, thang, nam)
    assert am == LunarDate(day=1, month=thang_am, year=nam, leap=True)
    # Ngày liền trước phải là ngày cuối (29/30) của tháng trước đó.
    hom_truoc = date(nam, thang, ngay) - timedelta(days=1)
    am_truoc = lunar_precise.solar_to_lunar(hom_truoc.day, hom_truoc.month, hom_truoc.year)
    assert am_truoc.day in (29, 30)


def test_thang_11_nhuan_2033_thuoc_dung_nam_2033():
    """Bài toán "năm 2033": tháng Mười Một nhuận phải nằm trong năm âm 2033.

    Đây là ca hiểm nổi tiếng của lịch Trung Quốc/Việt Nam; nhiều thuật toán
    đơn giản (kể cả bản Hồ Ngọc Đức) xử lý sai ca này.
    """
    cac_thang = lunar_precise.lunar_year_months(2033)
    assert len(cac_thang) == 13
    assert (11, True) in cac_thang
    # Mùng 1 tháng 11 nhuận = 22/12/2033, kéo dài 29 ngày tới 19/01/2034.
    assert lunar_precise.lunar_to_solar(1, 11, 2033, leap=True) == date(2033, 12, 22)
    assert lunar_precise.solar_to_lunar(22, 12, 2033) == LunarDate(1, 11, 2033, leap=True)
    assert lunar_precise.lunar_month_days(11, 2033, leap=True) == 29
    # Năm âm 2034 không có tháng nhuận; Tết 2034 = 19/02/2034.
    assert all(not la_nhuan for _, la_nhuan in lunar_precise.lunar_year_months(2034))
    assert lunar_precise.lunar_to_solar(1, 1, 2034) == date(2034, 2, 19)
    # Chuỗi ngày quanh Tết phải liên tục: 30/12/2033 rồi 1/1/2034.
    assert lunar_precise.solar_to_lunar(18, 2, 2034) == LunarDate(30, 12, 2033, False)
    assert lunar_precise.solar_to_lunar(19, 2, 2034) == LunarDate(1, 1, 2034, False)


# ===========================================================================
# 4. Các ngày lễ âm lịch quen thuộc (dữ liệu ngoài)
# ===========================================================================
@pytest.mark.parametrize("nam,ngay_duong", list(TRUNG_THU.items()), ids=[f"Trung-Thu-{y}" for y in TRUNG_THU])
def test_trung_thu_15_thang_8(nam: int, ngay_duong: date):
    """Tết Trung Thu (rằm tháng Tám) – ngày dương lịch đã biết."""
    assert lunar_precise.lunar_to_solar(15, 8, nam) == ngay_duong
    assert lunar_precise.solar_to_lunar(ngay_duong.day, ngay_duong.month, ngay_duong.year) == LunarDate(
        15, 8, nam, False
    )


@pytest.mark.parametrize("nam,ngay_duong", list(GIO_TO.items()), ids=[f"Giỗ-Tổ-{y}" for y in GIO_TO])
def test_gio_to_hung_vuong_10_thang_3(nam: int, ngay_duong: date):
    """Giỗ Tổ Hùng Vương mùng 10 tháng Ba – ngày nghỉ lễ đã biết."""
    assert lunar_precise.lunar_to_solar(10, 3, nam) == ngay_duong


@pytest.mark.parametrize("nam,ngay_duong", list(DOAN_NGO.items()), ids=[f"Đoan-Ngọ-{y}" for y in DOAN_NGO])
def test_tet_doan_ngo_5_thang_5(nam: int, ngay_duong: date):
    """Tết Đoan Ngọ mùng 5 tháng Năm – ngày dương lịch đã biết."""
    assert lunar_precise.lunar_to_solar(5, 5, nam) == ngay_duong


# ===========================================================================
# 5. Thiên văn: sóc, ΔT, phân/chí (đối chứng với niên giám thiên văn)
# ===========================================================================
def test_soc_meeus_vi_du_49a():
    """Ví dụ 49.a (Meeus): sóc thứ 0 = 2000-01-06 18:14 TT (JD ≈ 2451550,2597)."""
    jde = lunar_precise.new_moon_jde(0)
    assert abs(jde - 2451550.2597) < 0.01  # sai số ~15 phút là chấp nhận được


def test_delta_t_nam_2000():
    """ΔT (TT − UT) quanh năm 2000 được đo khoảng 63,8 giây."""
    assert 62.0 < lunar_precise.delta_t_seconds(2000.0) < 65.0
    # ΔT giảm dần khi lùi về quá khứ (năm 1900 khoảng vài giây âm/không đáng kể).
    assert lunar_precise.delta_t_seconds(1900.0) < lunar_precise.delta_t_seconds(2000.0)


@pytest.mark.parametrize(
    "ten_moc,kinh_do,ngay,gio,phut",
    [
        # Các điểm phân/chí năm 2026 theo niên giám thiên văn (giờ UT).
        ("Xuân Phân", 0.0, date(2026, 3, 20), 14, 46),
        ("Hạ Chí", 90.0, date(2026, 6, 21), 8, 24),
        ("Thu Phân", 180.0, date(2026, 9, 23), 0, 5),
        ("Đông Chí", 270.0, date(2026, 12, 21), 20, 50),
    ],
    ids=["Xuân-Phân-2026", "Hạ-Chí-2026", "Thu-Phân-2026", "Đông-Chí-2026"],
)
def test_kinh_do_mat_troi_tai_cac_diem_phan_chi(
    ten_moc: str, kinh_do: float, ngay: date, gio: int, phut: int
):
    """Kinh độ biểu kiến của Mặt Trời tại các mốc phân/chí phải xấp xỉ bội số 90°.

    Sai số cho phép 0,02° ≈ 30 phút thời gian, đủ rộng cho trí nhớ về giờ
    niên giám và đủ hẹp để bắt lỗi công thức.
    """
    jd = lunar.jd_from_date(ngay.day, ngay.month, ngay.year) + (gio + phut / 60 - 12) / 24
    lon = lunar_precise.sun_apparent_longitude(jd)
    lech = abs(((lon - kinh_do + 180.0) % 360.0) - 180.0)
    assert lech < 0.02, f"{ten_moc} {ngay}: lệch {lech:.4f}° (kinh độ = {lon:.4f}°)"


def test_dong_chi_2026_va_thang_11_am_lich():
    """Đông chí 2026 (21/12 20:49 UT = 22/12 03:49 giờ VN) nằm trong tháng 11 âm.

    Đây là định nghĩa của tháng Mười Một: tháng chứa Đông chí.
    """
    jd = lunar_precise.winter_solstice_jd(2026)
    # Ngày UT vẫn là 21/12/2026.
    assert lunar.jd_to_date(int(jd + 0.5)) == (21, 12, 2026)
    # Theo giờ Việt Nam là 22/12/2026 – ngày Đông Chí của lịch ta.
    assert lunar_precise.tiet_khi_name(date(2026, 12, 22)) == "Đông Chí"
    am = lunar_precise.solar_to_lunar(22, 12, 2026)
    assert (am.month, am.leap) == (11, False)
    assert 1 <= am.day <= 30


@pytest.mark.parametrize("nam", [1990, 2000, 2010, 2020, 2026, 2033, 2040])
def test_mung_mot_thang_11_chua_dong_chi(nam: int):
    """Tháng 11 âm phải chứa Đông chí: mùng 1 tháng 11 ≤ ngày Đông chí < mùng 1 tháng sau.

    Đây là định nghĩa thiên văn của tháng Mười Một trong lịch Âm.
    """
    jd_dong_chi = lunar_precise.winter_solstice_jd(nam)
    # Số ngày Julius của ngày địa phương (UTC+7) chứa điểm Đông chí.
    ngay_local = int(jd_dong_chi + 0.5 + 7 / 24.0)
    ngay, thang, nam_duong = lunar.jd_to_date(ngay_local)
    am = lunar_precise.solar_to_lunar(ngay, thang, nam_duong)
    assert am.month == 11 and not am.leap, (
        f"Đông chí {ngay:02d}/{thang:02d}/{nam_duong} phải thuộc tháng 11 âm, "
        f"không phải {am}"
    )
    # Mùng 1 tháng 11 ≤ ngày Đông chí.
    dau_11 = lunar_precise.lunar_month_start(am.year, 11, False)
    assert lunar.jd_from_date(dau_11.day, dau_11.month, dau_11.year) <= ngay_local
    # Ngày Đông chí < mùng 1 của tháng kế tiếp tháng 11.
    cac_thang = lunar_precise.lunar_year_months(am.year)
    vi_tri = cac_thang.index((11, False))
    thang_ke, nhuận_ke = cac_thang[vi_tri + 1]
    dau_ke = lunar_precise.lunar_month_start(am.year, thang_ke, nhuận_ke)
    assert ngay_local < lunar.jd_from_date(dau_ke.day, dau_ke.month, dau_ke.year)


def test_tiet_khi_ngay_28_10_2026_la_suong_giang():
    """Yêu cầu của task: 28/10/2026 thuộc tiết Sương Giáng."""
    assert lunar_precise.tiet_khi_name(date(2026, 10, 28)) == "Sương Giáng"


def test_lap_xuan_2026_ngay_04_thang_02():
    """Lập Xuân 2026: Mặt Trời đạt 315° lúc 03:02 giờ VN ngày 04/02."""
    assert lunar_precise.tiet_khi_name(date(2026, 2, 3)) == "Đại Hàn"
    assert lunar_precise.tiet_khi_name(date(2026, 2, 4)) == "Lập Xuân"


def test_quy_uoc_tiet_khi_theo_ngay_bat_dau():
    """Quy ước (đã hội ý Lead): ngày nào có tiết khí *bắt đầu* thì ghi tiết khí đó.

    Trước đây engine chốt kinh độ Mặt Trời tại 12:00 ngày nên Xuân Phân 2026
    (bắt đầu 20/03 lúc 21:37 giờ Việt Nam) bị gán nhầm sang ngày 21/03.
    Quy ước mới xét [nửa đêm đầu ngày, nửa đêm cuối ngày]: tiết khí nào bắt
    đầu trong khoảng đó thì ngày đó mang tên tiết khí ấy – khớp cách in của
    lịch vạn niên Việt Nam.
    """
    # Kiểm chứng thiên văn: kinh độ Mặt Trời vượt 0° ngay trong ngày 20/03
    # (giờ Việt Nam), nên ngày 20/03 phải là Xuân Phân.
    nua_dem_dau = lunar.jd_from_date(20, 3, 2026) - 0.5 - 7 / 24
    nua_dem_cuoi = nua_dem_dau + 1
    assert lunar_precise.sun_apparent_longitude(nua_dem_dau) > 359.0  # chưa tới 0°
    assert lunar_precise.sun_apparent_longitude(nua_dem_cuoi) < 1.0  # đã qua 0°
    # Xuân Phân 2026 (0°): 20/03 14:37 UT = 21:37 giờ VN -> ngày 20/03.
    assert lunar_precise.tiet_khi_name(date(2026, 3, 19)) == "Kinh Trập"
    assert lunar_precise.tiet_khi_name(date(2026, 3, 20)) == "Xuân Phân"
    assert lunar_precise.tiet_khi_name(date(2026, 3, 21)) == "Xuân Phân"
    # Lập Xuân 2026 (315°): 03/02 19:55 UT = 04/02 02:55 giờ VN -> ngày 04/02.
    assert lunar_precise.tiet_khi_name(date(2026, 2, 3)) == "Đại Hàn"
    assert lunar_precise.tiet_khi_name(date(2026, 2, 4)) == "Lập Xuân"
    # Đông chí 2026 (270°): 21/12 20:49 UT = 22/12 03:49 giờ VN -> ngày 22/12.
    assert lunar_precise.tiet_khi_name(date(2026, 12, 21)) == "Đại Tuyết"
    assert lunar_precise.tiet_khi_name(date(2026, 12, 22)) == "Đông Chí"


def test_chu_ky_24_tiet_khi_trong_nam_2026():
    """Trong một năm, chỉ số tiết khí chỉ tăng +1 (mod 24) và phủ đủ 24 tiết."""
    ngay_dau = date(2026, 1, 1)
    chi_so = [
        lunar_precise.tiet_khi_index(ngay_dau + timedelta(days=i)) for i in range(365)
    ]
    for truoc, sau in zip(chi_so, chi_so[1:]):
        assert sau == truoc or sau == (truoc + 1) % 24, "bước nhảy tiết khí bất thường"
    assert set(chi_so) == set(range(24)), "phải xuất hiện đủ 24 tiết khí"
    # Tên trả về phải tra đúng bảng TIET_KHI.
    for chi in (0, 7, 15, 23):
        ngay = next(
            ngay_dau + timedelta(days=i)
            for i in range(365)
            if lunar_precise.tiet_khi_index(ngay_dau + timedelta(days=i)) == chi
        )
        assert lunar_precise.tiet_khi_name(ngay) == TIET_KHI[chi]


# ===========================================================================
# 6. Tính tự nhất quán toàn miền 1900–2200
# ===========================================================================
def test_lien_tuc_va_round_trip_toan_mien_1900_2200():
    """Quét từng ngày 1900-01-01 → 2200-12-31.

    Ba điều kiện:
    * Ngày âm tăng đều: hôm sau là ngày +1, hoặc sang mùng 1 của tháng kế
      (mùng 1 tháng nhuận thì trùng số tháng trước, mùng 1 tháng Giêng thì
      sang năm mới).
    * Không ngày âm nào vượt quá 30 hoặc nhỏ hơn 1.
    * Round-trip Dương → Âm → Dương trả lại đúng ngày ban đầu.
    """
    ngay_dau = date(1900, 1, 1)
    ngay_cuoi = date(2200, 12, 31)
    truoc = lunar_precise.solar_to_lunar(ngay_dau.day, ngay_dau.month, ngay_dau.year)
    loi: list[str] = []
    ngay = ngay_dau
    for _ in range((ngay_cuoi - ngay_dau).days):
        ngay += timedelta(days=1)
        hien_tai = lunar_precise.solar_to_lunar(ngay.day, ngay.month, ngay.year)

        if hien_tai.day == 1:
            if hien_tai.month == 1 and not hien_tai.leap:
                # Mùng 1 tháng Giêng: phải sang năm âm mới.
                if not (truoc.month == 12 and hien_tai.year == truoc.year + 1):
                    loi.append(f"{ngay}: mùng 1 tháng Giêng nhưng trước là {truoc}")
            elif hien_tai.leap:
                # Mùng 1 tháng nhuận: cùng số tháng, cùng năm, tiếp sau tháng đủ.
                if not (
                    hien_tai.month == truoc.month
                    and hien_tai.year == truoc.year
                    and truoc.day >= 29
                ):
                    loi.append(f"{ngay}: mùng 1 tháng nhuận nhưng trước là {truoc}")
            else:
                # Mùng 1 tháng thường: tháng kế tiếp trong năm.
                if not (hien_tai.month == truoc.month % 12 + 1 and hien_tai.year == truoc.year):
                    loi.append(f"{ngay}: mùng 1 tháng {hien_tai.month} nhưng trước là {truoc}")
        else:
            if not (
                hien_tai.day == truoc.day + 1
                and hien_tai.month == truoc.month
                and hien_tai.leap == truoc.leap
                and hien_tai.year == truoc.year
            ):
                loi.append(f"{ngay}: ngày âm nhảy từ {truoc} sang {hien_tai}")

        if not (1 <= hien_tai.day <= 30 and 1 <= hien_tai.month <= 12):
            loi.append(f"{ngay}: giá trị âm lịch không hợp lệ {hien_tai}")

        if lunar_precise.lunar_to_solar(
            hien_tai.day, hien_tai.month, hien_tai.year, hien_tai.leap
        ) != ngay:
            loi.append(f"{ngay}: round-trip sai (âm {hien_tai})")

        if loi:
            break
        truoc = hien_tai

    assert not loi, "Phát hiện lỗi liên tục/round-trip:\n" + "\n".join(loi)


def test_do_dai_nam_am_va_cau_truc_thang():
    """Độ dài năm âm chỉ thuộc tập chuẩn; tháng âm dài 29 hoặc 30 ngày."""
    for nam in range(1900, 2200):
        cac_thang = lunar_precise.lunar_year_months(nam)
        assert cac_thang[0] == (1, False) and cac_thang[-1] == (12, False), (
            f"năm {nam} phải bắt đầu tháng Giêng và kết thúc tháng Chạp"
        )
        assert len(cac_thang) in (12, 13)
        so_nhuan = sum(1 for _, la_nhuan in cac_thang if la_nhuan)
        assert so_nhuan == (1 if len(cac_thang) == 13 else 0), (
            f"năm {nam}: {len(cac_thang)} tháng nhưng {so_nhuan} tháng nhuận"
        )
        tong_ngay = 0
        for m, la_nhuan in cac_thang:
            so_ngay = lunar_precise.lunar_month_days(m, nam, la_nhuan)
            assert so_ngay in (29, 30), f"tháng {m}{' nhuận' if la_nhuan else ''}/{nam} dài {so_ngay} ngày"
            tong_ngay += so_ngay
        assert tong_ngay in DO_DAI_NAM_AM_HOP_LE, f"năm âm {nam} dài {tong_ngay} ngày"


def test_mung_mot_cac_thang_lien_tuc_va_dai_thang():
    """Ngày mùng 1 tháng sau phải cách mùng 1 tháng trước đúng số ngày của tháng."""
    for nam in (1900, 1950, 2000, 2023, 2024, 2026, 2033, 2099, 2199):
        cac_thang = lunar_precise.lunar_year_months(nam)
        for i, (m, la_nhuan) in enumerate(cac_thang):
            dau = lunar_precise.lunar_month_start(nam, m, la_nhuan)
            so_ngay = lunar_precise.lunar_month_days(m, nam, la_nhuan)
            assert so_ngay in (29, 30)
            if i + 1 < len(cac_thang):
                m_ke, nhuận_ke = cac_thang[i + 1]
                dau_ke = lunar_precise.lunar_month_start(nam, m_ke, nhuận_ke)
                assert (dau_ke - dau).days == so_ngay


# ===========================================================================
# 7. API báo lỗi đúng chỗ
# ===========================================================================
@pytest.mark.parametrize(
    "tham_so",
    [
        (1, 0, 2026),  # tháng 0
        (1, 13, 2026),  # tháng 13
        (0, 1, 2026),  # ngày 0
        (31, 1, 2026),  # ngày 31 âm (không bao giờ có)
        (1, 1, 2026, True),  # năm 2026 không có tháng Giêng nhuận
    ],
    ids=["tháng-0", "tháng-13", "ngày-0", "ngày-31", "tháng-nhuận-không-tồn-tại"],
)
def test_lunar_to_solar_bao_loi_voi_tham_so_khong_hop_le(tham_so: tuple):
    """Đầu vào vô lý phải ném ``ValueError`` chứ không trả ngày sai."""
    with pytest.raises(ValueError):
        lunar_precise.lunar_to_solar(*tham_so)


def test_ngay_30_cua_thang_thieu_phai_bao_loi():
    """Tháng âm 29 ngày thì yêu cầu ngày 30 phải bị từ chối."""
    # Tìm một tháng 29 ngày để kiểm tra (tháng 2 nhuận 2023 là 29 ngày).
    assert lunar_precise.lunar_month_days(2, 2023, leap=True) == 29
    with pytest.raises(ValueError):
        lunar_precise.lunar_to_solar(30, 2, 2023, leap=True)


def test_leap_offset_nhan_dien_thang_11_nhuan_2033():
    """Vị trí tháng nhuận tính từ tháng 11/2033 phải là 1 (ngay sau tháng 11)."""
    a11 = lunar_precise.month11_start(2033)
    assert lunar_precise.leap_offset(a11) == 1
    # Các năm mà khoảng "tháng 11 năm y → tháng 11 năm y+1" không có tháng
    # nhuận (2021–2022, 2029–2030, 2037–2038 đều là năm thường) phải trả 0.
    for nam in (2021, 2029, 2037):
        assert lunar_precise.leap_offset(lunar_precise.month11_start(nam)) == 0
