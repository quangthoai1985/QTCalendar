"""Kiểm chứng Can Chi và giờ hoàng đạo theo quy tắc cổ truyền.

Dữ liệu đối chứng bên ngoài:

* 1984 = **Giáp Tý** (khởi đầu một vòng 60 năm), 2000 = Canh Thìn,
  2023 = Quý Mão, 2024 = Giáp Thìn, 2025 = Ất Tỵ, 2026 = Bính Ngọ.
* Ngày 01/01/2000 (JDN 2451545) = **Mậu Ngọ** – mốc neo của phép tính ngày.
* Ngày 10/02/2024 (mùng 1 Tết Giáp Thìn) = ngày **Giáp Thìn**.
* Ngày 28/10/2026 = ngày **Ất Hợi** (yêu cầu của task).
* Quy tắc "ngũ hổ độn" lập tháng: Giáp – Kỷ khởi Bính Dần, Ất – Canh khởi
  Mậu Dần, Bính – Tân khởi Canh Dần, Đinh – Nhâm khởi Nhâm Dần,
  Mậu – Quý khởi Giáp Dần.
* Bảng giờ hoàng đạo dân gian: ngày Tý/Ngọ có giờ hoàng đạo Tý, Sửu, Mão,
  Ngọ, Thân, Dậu; ngày Tỵ/Hợi có Sửu, Thìn, Ngọ, Mùi, Tuất, Hợi.
* "Tháng Giêng ngày hoàng đạo là Tý, Sửu, Thìn, Tỵ, Mùi, Tuất" (tháng
  Giêng và tháng Bảy cùng bộ ngày hoàng đạo).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from qtcalendar.core import canchi
from qtcalendar.core.canchi_constants import CAN, CHI, HOUR_GODS, ZODIAC
from qtcalendar.core.types import CanChi

#: Các mốc Can Chi của năm âm lịch đã biết.
MOC_NAM: dict[int, tuple[str, str]] = {
    1984: ("Giáp", "Tý"),  # khởi đầu vòng 60 năm Giáp Tý
    1990: ("Canh", "Ngọ"),
    2000: ("Canh", "Thìn"),
    2010: ("Canh", "Dần"),
    2020: ("Canh", "Tý"),
    2023: ("Quý", "Mão"),
    2024: ("Giáp", "Thìn"),
    2025: ("Ất", "Tỵ"),
    2026: ("Bính", "Ngọ"),
}

#: Quy tắc ngũ hổ độn: can năm -> can của tháng Giêng (chi luôn là Dần).
NGU_HO_DON: dict[str, str] = {
    "Giáp": "Bính",
    "Kỷ": "Bính",
    "Ất": "Mậu",
    "Canh": "Mậu",
    "Bính": "Canh",
    "Tân": "Canh",
    "Đinh": "Nhâm",
    "Nhâm": "Nhâm",
    "Mậu": "Giáp",
    "Quý": "Giáp",
}

#: Năm đại diện cho từng can (2024 = Giáp, 2025 = Ất, …).
NAM_DAI_DIEN_CAN: dict[str, int] = {
    "Giáp": 2024,
    "Ất": 2025,
    "Bính": 2026,
    "Đinh": 2027,
    "Mậu": 2028,
    "Kỷ": 2029,
    "Canh": 2030,
    "Tân": 2031,
    "Nhâm": 2032,
    "Quý": 2033,
}


# ===========================================================================
# 1. Can Chi của năm
# ===========================================================================
@pytest.mark.parametrize("nam,can,chi", [(y, c, ch) for y, (c, ch) in MOC_NAM.items()])
def test_nam_can_chi_theo_moc_da_biet(nam: int, can: str, chi: str):
    """Can Chi của năm phải khớp các mốc lịch vạn niên đã biết."""
    assert canchi.year_can_chi(nam) == CanChi(can, chi)
    assert canchi.year_can_chi(nam).text == f"{can} {chi}"


def test_chu_ky_60_nam_lap_lai():
    """Sau đúng 60 năm, Can Chi của năm lặp lại y nguyên."""
    for nam in range(1900, 2100):
        assert canchi.year_can_chi(nam) == canchi.year_can_chi(nam + 60)
    # Hai năm liên tiếp phải tiến đúng một bậc can và một bậc chi.
    for nam in range(1950, 2050):
        truoc = canchi.year_can_chi(nam)
        sau = canchi.year_can_chi(nam + 1)
        assert sau.can == CAN[(CAN.index(truoc.can) + 1) % 10]
        assert sau.chi == CHI[(CHI.index(truoc.chi) + 1) % 12]


@pytest.mark.parametrize(
    "nam,con_giap",
    [
        (2020, "Chuột"),
        (2021, "Trâu"),
        (2022, "Hổ"),
        (2023, "Mèo"),  # Việt Nam gọi Mão là Mèo, không phải Thỏ
        (2024, "Rồng"),
        (2025, "Rắn"),
        (2026, "Ngựa"),
    ],
)
def test_con_giap_theo_cach_goi_viet_nam(nam: int, con_giap: str):
    """Con giáp phải theo cách gọi Việt Nam (Mão = Mèo)."""
    assert canchi.zodiac_animal(nam) == con_giap
    assert canchi.zodiac_animal(nam) in ZODIAC


# ===========================================================================
# 2. Can Chi của tháng (quy tắc ngũ hổ độn)
# ===========================================================================
def test_thang_gieng_2024_la_binh_dan():
    """Yêu cầu của task: tháng Giêng năm Giáp Thìn 2024 = Bính Dần."""
    assert canchi.month_can_chi(1, 2024) == CanChi("Bính", "Dần")


@pytest.mark.parametrize("can_nam,can_thang_gieng", list(NGU_HO_DON.items()))
def test_quy_tac_ngu_ho_don(can_nam: str, can_thang_gieng: str):
    """Tháng Giêng luôn là chi Dần; can khởi theo cặp can của năm."""
    nam = NAM_DAI_DIEN_CAN[can_nam]
    assert canchi.year_can_chi(nam).can == can_nam, "bảng đại diện năm bị lệch"
    thang_gieng = canchi.month_can_chi(1, nam)
    assert thang_gieng == CanChi(can_thang_gieng, "Dần")


def test_chi_cua_thang_theo_thu_tu_dan_mao_ty_ngo():
    """12 tháng âm mang 12 chi liên tiếp: Giêng = Dần, …, Chạp = Sửu."""
    ky_vong = ["Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi", "Tý", "Sửu"]
    for thang, chi in enumerate(ky_vong, start=1):
        assert canchi.month_can_chi(thang, 2024).chi == chi
    assert canchi.month_can_chi(11, 2024).chi == "Tý"
    assert canchi.month_can_chi(12, 2024).chi == "Sửu"


@pytest.mark.parametrize("thang", [0, 13, -1])
def test_thang_can_chi_bao_loi_voi_thang_sai(thang: int):
    """Tháng âm ngoài 1..12 phải ném ``ValueError``."""
    with pytest.raises(ValueError):
        canchi.month_can_chi(thang, 2024)


# ===========================================================================
# 3. Can Chi của ngày
# ===========================================================================
@pytest.mark.parametrize(
    "ngay,can,chi",
    [
        (date(2000, 1, 1), "Mậu", "Ngọ"),  # mốc JDN 2451545
        (date(2024, 2, 10), "Giáp", "Thìn"),  # mùng 1 Tết 2024
        (date(2026, 10, 28), "Ất", "Hợi"),  # yêu cầu của task
        (date(2024, 1, 1), "Giáp", "Tý"),
        (date(2000, 1, 7), "Giáp", "Tý"),
    ],
)
def test_ngay_can_chi_theo_moc_da_biet(ngay: date, can: str, chi: str):
    """Can Chi của ngày theo các mốc đã biết (mốc neo: 01/01/2000 = Mậu Ngọ)."""
    assert canchi.day_can_chi(ngay) == CanChi(can, chi)


def test_chu_ky_60_ngay_lien_tuc():
    """Ngày liên tiếp tiến 1 can + 1 chi; đúng 60 ngày lặp lại y nguyên."""
    ngay_dau = date(2026, 1, 1)
    for i in range(400):
        ngay = ngay_dau + timedelta(days=i)
        hien_tai = canchi.day_can_chi(ngay)
        sau = canchi.day_can_chi(ngay + timedelta(days=1))
        assert sau.can == CAN[(CAN.index(hien_tai.can) + 1) % 10]
        assert sau.chi == CHI[(CHI.index(hien_tai.chi) + 1) % 12]
        assert canchi.day_can_chi(ngay + timedelta(days=60)) == hien_tai


def test_ngay_can_chi_khop_voi_so_ngay_julius():
    """Công thức JDN → Can Chi phải khớp với chuỗi 60 ngày tính từ mốc 2000."""
    # 01/01/2000 = Mậu Ngọ (JDN 2451545); đếm tiến/lùi từ mốc này.
    moc = date(2000, 1, 1)
    for lech in (-1000, -366, -12, -1, 1, 12, 366, 1000, 5000):
        ngay = moc + timedelta(days=lech)
        # Mỗi 60 ngày Can Chi lặp lại; phần dư quyết định cặp mới.
        chi_so = lech % 60
        can = CAN[(4 + chi_so) % 10]  # Mậu = chỉ số 4
        chi = CHI[(6 + chi_so) % 12]  # Ngọ = chỉ số 6
        assert canchi.day_can_chi(ngay) == CanChi(can, chi), f"lệch tại {ngay}"


# ===========================================================================
# 4. Giờ hoàng đạo
# ===========================================================================
def test_gio_hoang_dao_ngay_ty_dung_bang_dan_gian():
    """Ngày Tý: 6 giờ hoàng đạo là Tý, Sửu, Mão, Ngọ, Thân, Dậu (bảng dân gian)."""
    # 07/01/2000 là ngày Giáp Tý (probe bằng Can Chi ngày).
    ngay = date(2000, 1, 7)
    assert canchi.day_can_chi(ngay).chi == "Tý"
    gio = {h.chi for h in canchi.auspicious_hours(ngay)}
    assert gio == {"Tý", "Sửu", "Mão", "Ngọ", "Thân", "Dậu"}


def test_gio_hoang_dao_ngay_hoi_dung_bang_dan_gian():
    """Ngày Hợi: 6 giờ hoàng đạo là Sửu, Thìn, Ngọ, Mùi, Tuất, Hợi."""
    ngay = date(2026, 10, 28)
    assert canchi.day_can_chi(ngay).chi == "Hợi"
    gio = {h.chi for h in canchi.auspicious_hours(ngay)}
    assert gio == {"Sửu", "Thìn", "Ngọ", "Mùi", "Tuất", "Hợi"}


def test_moi_ngay_co_dung_6_gio_hoang_dao_hop_le():
    """Mọi ngày trong một năm: đúng 6 canh giờ, mỗi canh 2 tiếng, không trùng."""
    ngay_dau = date(2026, 1, 1)
    for i in range(0, 366, 11):
        ngay = ngay_dau + timedelta(days=i)
        cac_gio = canchi.auspicious_hours(ngay)
        assert len(cac_gio) == 6, f"{ngay}: {len(cac_gio)} giờ hoàng đạo"
        assert len({h.chi for h in cac_gio}) == 6, "các canh phải khác nhau"
        for h in cac_gio:
            chi_so = CHI.index(h.chi)
            assert h.start == (23 + 2 * chi_so) % 24
            assert h.end == (h.start + 2) % 24
            assert h.god in HOUR_GODS
        # Thứ tự trả về phải theo thời gian trong ngày (bắt đầu từ Tý 23h).
        chi_so = [CHI.index(h.chi) for h in cac_gio]
        assert chi_so == sorted(chi_so)
        # 6 vị thần tốt phải nằm trong nhóm hoàng đạo của bảng 12 thần.
        assert all(h.god in {"Thanh Long", "Minh Đường", "Kim Quỹ", "Bảo Quang", "Ngọc Đường", "Tư Mệnh"} for h in cac_gio)


def test_bo_gio_hoang_dao_chi_phu_thuoc_chi_cua_ngay():
    """Hai ngày cùng chi (cách nhau 12 ngày) có cùng bộ giờ hoàng đạo."""
    for ngay in (date(2026, 10, 28), date(2024, 2, 10), date(2000, 1, 7)):
        bo_goc = [h.chi for h in canchi.auspicious_hours(ngay)]
        bo_sau = [h.chi for h in canchi.auspicious_hours(ngay + timedelta(days=12))]
        assert bo_goc == bo_sau


def test_hour_of_day_anh_xa_dung_canh_gio():
    """Giờ đồng hồ → canh: Tý 23–01, Sửu 01–03, …, Hợi 21–23."""
    ngay = date(2026, 10, 28)
    cac_gio_hoang_dao = {h.chi for h in canchi.auspicious_hours(ngay)}
    for gio in range(24):
        chi_so, muc = canchi.hour_of_day(ngay, gio)
        assert chi_so == ((gio + 1) % 24) // 2
        assert CHI[chi_so] == CHI[((gio + 1) % 24) // 2]
        if muc is None:
            assert CHI[chi_so] not in cac_gio_hoang_dao
        else:
            assert muc.chi == CHI[chi_so]
            assert muc.chi in cac_gio_hoang_dao
    with pytest.raises(ValueError):
        canchi.hour_of_day(ngay, 24)


# ===========================================================================
# 5. Ngày hoàng đạo / hắc đạo theo tháng âm
# ===========================================================================
def _cac_chi_hoang_dao(thang_am: int) -> set[str]:
    """Tập chi của những ngày được coi là hoàng đạo trong tháng âm."""
    ket_qua = set()
    for chi_so, chi in enumerate(CHI):
        # Can bất kỳ cùng tính chẵn lẻ với chi để tạo cặp Can Chi hợp lệ.
        can = CAN[chi_so % 10]
        if canchi.is_auspicious_day(thang_am, CanChi(can, chi)):
            ket_qua.add(chi)
    return ket_qua


def test_ngay_hoang_dao_thang_gieng_dung_cau_dan_gian():
    """"Tháng Giêng ngày hoàng đạo là Tý, Sửu, Thìn, Tỵ, Mùi, Tuất"."""
    assert _cac_chi_hoang_dao(1) == {"Tý", "Sửu", "Thìn", "Tỵ", "Mùi", "Tuất"}


def test_ngay_hoang_dao_thang_bay_giong_thang_gieng():
    """Tháng Bảy (chi Dần/Thân) có cùng bộ ngày hoàng đạo với tháng Giêng."""
    assert _cac_chi_hoang_dao(7) == _cac_chi_hoang_dao(1)


def test_moi_thang_am_co_dung_6_chi_hoang_dao():
    """Mỗi tháng âm có đúng 6/12 chi là ngày hoàng đạo (nửa vòng 12 thần)."""
    for thang in range(1, 13):
        assert len(_cac_chi_hoang_dao(thang)) == 6


@pytest.mark.parametrize("thang", [0, 13])
def test_ngay_hoang_dao_bao_loi_voi_thang_sai(thang: int):
    """Tháng âm ngoài 1..12 phải ném ``ValueError``."""
    with pytest.raises(ValueError):
        canchi.is_auspicious_day(thang, CanChi("Giáp", "Tý"))


# ===========================================================================
# 6. Nhãn hiển thị
# ===========================================================================
@pytest.mark.parametrize(
    "thang,la_nhuan,ky_vong",
    [
        (1, False, "Tháng Giêng"),
        (2, True, "Tháng Hai (nhuận)"),
        (11, False, "Tháng Mười Một"),
        (12, False, "Tháng Chạp"),
    ],
)
def test_nhan_thang_am(thang: int, la_nhuan: bool, ky_vong: str):
    """Nhãn tháng âm theo cách gọi dân gian Việt Nam."""
    assert canchi.lunar_month_label(thang, la_nhuan) == ky_vong


@pytest.mark.parametrize("thang", [0, 13])
def test_nhan_thang_am_bao_loi(thang: int):
    """Nhãn tháng với tháng sai phải ném ``ValueError``."""
    with pytest.raises(ValueError):
        canchi.lunar_month_label(thang)
