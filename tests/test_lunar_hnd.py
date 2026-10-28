"""Ghi nhận các điểm engine Hồ Ngọc Đức (``lunar.py``) lệch lịch chuẩn.

``lunar.py`` là bản chuyển nguyên thuật toán gốc của Hồ Ngọc Đức (chuỗi
Fourier rút gọn cho sóc và kinh độ Mặt Trời, sai số ~±50 phút). Đây là
engine thứ hai (``engine="hnd"``), **không phải engine mặc định**.

Cập nhật 2026-10-28 (sau khi Lead sửa ``src``): Lead đã viết lại
``lunar_month_days``/``lunar_year_months`` để suy ra từ chính
``solar_to_lunar``/``lunar_to_solar``, nên các lỗi số ngày âm và ca 2033
đã được khắc phục. Vì vậy các test cũ đánh dấu ``xfail`` cho hai lỗi này
nay chuyển thành **assert hành vi đúng** (test hồi quy chống tái phát).

Cách xử lý khác biệt trong bộ test này:

* Phần lớn dữ liệu vẫn đúng → test thường, phải PASS (Tết 1985–2040 trừ
  1991, tháng nhuận 1990–2036 trừ 2023/2039, ca 2033, tính liên tục
  1990–2040, round-trip, số ngày tháng…).
* Các ca lệch **thuật toán** chưa sửa (Tết 1991, bốn điểm sóc lệch, tên
  tháng nhuận 2023/2039) → một test ``pytest.mark.xfail(strict=True)``
  kèm lý do cụ thể: test đang "đỏ" một cách có kiểm soát. Khi Lead sửa
  engine, các test này chuyển thành XPASS và pytest báo FAIL để nhắc cập
  nhật lại tài liệu/ghi nhận – đúng hành vi mong muốn của QA.
* Ca chưa đủ căn cứ kết luận (ví dụ sóc 08/2035) → test "quan sát" chỉ ghi
  lại rằng hai engine lệch nhau, không khẳng định engine nào sai.

Danh sách phát hiện của QA (chi tiết trong từng test):

1. **Tết 1991** (còn lệch): HND cho 14/02/1991, lịch chuẩn là 15/02/1991.
   Điểm sóc tháng Giêng 1991 rơi 00:32 giờ Việt Nam (chỉ hơn nửa đêm 32
   phút) nên chuỗi rút gọn tính sớm ~40 phút đã đẩy lùi cả ngày. Ca này nằm
   NGOÀI danh sách 4 điểm sóc lệch mà docstring ``lunar_precise.py`` liệt kê
   (docstring chỉ đo giai đoạn 2020–2034).
2. **Tháng nhuận sai tên** (còn lệch): 2023 HND gọi *tháng Giêng nhuận*
   (chuẩn: tháng Hai nhuận); 2039 HND gọi *tháng Tư nhuận* (chuẩn: tháng
   Năm nhuận). Riêng 2033 **đã đúng**: HND có tháng Mười Một nhuận trong
   ``lunar_year_months``, khớp precise.
3. **Bốn điểm sóc lệch 1 ngày** (còn lệch) đúng như docstring
   ``lunar_precise.py``: 05/2020, 03/2023, 08/2026, 04/2031.
4. **Số ngày tháng nhuận** (ĐÃ SỬA bởi Lead): ``lunar_month_days`` giờ khớp
   với chính lịch HND (ví dụ tháng 4 nhuận 2020 = 30 ngày theo HND, vì HND
   tính sóc 22/05 còn chuẩn là 23/05). Test hồi quy kiểm tra mọi tháng dài
   29/30 ngày và khớp hiệu hai ngày mùng 1.
5. **Ngoài danh sách tài liệu**: sóc 08/2035 lệch một ngày (HND: 03/08,
   precise: 04/08) – chưa có đối chứng ngoài nên chỉ quan sát.
6. **Tiết khí**: HND chốt kinh độ Mặt Trời tại **nửa đêm** ngày, còn
   precise (sau khi Lead sửa) gán tiết khí cho **ngày chứa thời điểm bắt
   đầu** theo quy ước lịch vạn niên – nên vài ngày biên lệch tên nhau
   (ví dụ 20/03/2026: HND "Kinh Trập", precise "Xuân Phân").
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from qtcalendar.core import lunar, lunar_precise
from qtcalendar.core.types import LunarDate

# Dùng lại bảng dữ liệu đối chứng bên ngoài của bộ test engine precise để
# tránh chép tay hai lần (cùng một nguồn: lịch Việt Nam UTC+7).
from test_lunar_precise import LEAP_MONTHS, TET_VN

#: Bảng tháng nhuận chuẩn, bổ sung 2039 (ngoài phạm vi bảng 1990–2036)
#: để đối chiếu ca lệch nổi tiếng của engine HND.
LEAP_MONTHS_CHUAN = {**LEAP_MONTHS, 2039: 5}

#: Các năm mà HND cho tên tháng nhuận khác chuẩn (dùng cho xfail).
NAM_NHUAN_HND_SAI = {2023, 2039}


# ===========================================================================
# 1. Ngày Tết: phần lớn đúng, riêng 1991 lệch
# ===========================================================================
TET_PARAMS = [
    pytest.param(
        nam,
        thang,
        ngay,
        marks=(
            pytest.mark.xfail(
                strict=True,
                reason=(
                    "ĐÃ BIẾT: engine HND cho Tết 1991 = 14/02/1991, lịch chuẩn "
                    "là 15/02/1991 (sóc rơi 00:32 giờ VN; chuỗi Fourier rút gọn "
                    "tính sớm ~40 phút nên lùi một ngày)."
                ),
            )
            if nam == 1991
            else ()
        ),
        id=f"Tết-{nam}",
    )
    for nam, (thang, ngay) in TET_VN.items()
]


@pytest.mark.parametrize("nam,thang,ngay", TET_PARAMS)
def test_hnd_tet_nguyen_dan(nam: int, thang: int, ngay: int):
    """HND phải khớp bảng Tết Việt Nam; riêng 1991 đang lệch (xfail có lý do)."""
    am = lunar.solar_to_lunar(ngay, thang, nam)
    assert am == LunarDate(day=1, month=1, year=nam, leap=False)


def test_hnd_tet_1991_lui_mot_ngay_quan_sat():
    """Quan sát chính xác hành vi hiện tại của HND quanh Tết 1991.

    Lịch chuẩn: 15/02/1991 là mùng 1 Tết. HND lại coi 14/02/1991 là mùng 1
    (và 15/02 là mùng 2). Test này không fail – nó ghi lại bằng chứng để
    báo cáo, còn việc "phải là 15/02" nằm ở test xfail phía trên.
    """
    assert lunar.solar_to_lunar(14, 2, 1991) == LunarDate(1, 1, 1991, False)
    assert lunar.solar_to_lunar(15, 2, 1991) == LunarDate(2, 1, 1991, False)
    # Khoảng cách Tết 1990 → Tết (sai) 1991 là 383 ngày thay vì 384 như chuẩn.
    khoang_cach = (lunar.lunar_to_solar(1, 1, 1991) - lunar.lunar_to_solar(1, 1, 1990)).days
    assert khoang_cach == 383


def test_hnd_tet_2030_va_2007_van_dung_moc_lech_trung_quoc():
    """Ngược lại, HND vẫn đúng 2007 (17/02) và 2030 (02/02) – hai ca lệch TQ."""
    assert lunar.lunar_to_solar(1, 1, 2007) == date(2007, 2, 17)
    assert lunar.lunar_to_solar(1, 1, 2030) == date(2030, 2, 2)
    assert lunar.lunar_to_solar(1, 1, 1985) == date(1985, 1, 21)


# ===========================================================================
# 2. Tháng nhuận: 2023 và 2039 sai tên; các năm còn lại (kể cả 2033) đúng
# ===========================================================================
LEAP_PARAMS = [
    pytest.param(
        nam,
        thang_nhuan,
        marks=(
            pytest.mark.xfail(
                strict=True,
                reason={
                    2023: (
                        "ĐÃ BIẾT: HND gọi tháng Giêng nhuận; chuẩn là tháng Hai "
                        "nhuận (điểm sóc 21/03 vs 22/03/2023)."
                    ),
                    2039: (
                        "ĐÃ BIẾT: HND gọi tháng Tư nhuận; chuẩn là tháng Năm "
                        "nhuận 2039."
                    ),
                }[nam]
            )
            if nam in (2023, 2039)
            else ()
        ),
        id=f"nhuận-{nam}",
    )
    for nam, thang_nhuan in LEAP_MONTHS_CHUAN.items()
]


@pytest.mark.parametrize("nam,thang_nhuan", LEAP_PARAMS)
def test_hnd_thang_nhuan_theo_bang_chuan(nam: int, thang_nhuan: int):
    """HND phải có đúng một tháng nhuận và đúng số tháng như lịch chuẩn."""
    cac_thang = lunar.lunar_year_months(nam)
    ds_nhuan = [m for m, la_nhuan in cac_thang if la_nhuan]
    assert ds_nhuan == [thang_nhuan]


def test_hnd_2033_co_thang_11_nhuan_khop_precise():
    """Sau khi Lead sửa: HND xử lý đúng ca 2033 (tháng Mười Một nhuận).

    Trước đây ``lunar_year_months(2033)`` thiếu tháng nhuận (trả 12 tháng)
    dù ``solar_to_lunar`` vẫn ánh xạ đúng; nay hai hàm đã nhất quán và khớp
    engine precise.
    """
    cac_thang = lunar.lunar_year_months(2033)
    assert len(cac_thang) == 13
    assert (11, True) in cac_thang
    # Thứ tự: … tháng Mười Một thường → Mười Một nhuận → tháng Chạp.
    vi_tri = cac_thang.index((11, True))
    assert cac_thang[vi_tri - 1] == (11, False)
    assert cac_thang[vi_tri + 1] == (12, False)
    # Mùng 1 khớp hai chiều và khớp precise (22/12/2033 = 1/11 nhuận).
    assert lunar.lunar_to_solar(1, 11, 2033, True) == date(2033, 12, 22)
    assert lunar.solar_to_lunar(22, 12, 2033) == LunarDate(1, 11, 2033, True)
    assert lunar.lunar_month_days(11, 2033, leap=True) == 29
    assert lunar_precise.lunar_month_days(11, 2033, leap=True) == 29
    # Độ dài năm âm 2033 = 384 ngày = khoảng cách Tết 2033 → Tết 2034.
    tong_ngay = sum(lunar.lunar_month_days(m, 2033, l) for m, l in cac_thang)
    assert tong_ngay == 384
    assert tong_ngay == (
        lunar.lunar_to_solar(1, 1, 2034) - lunar.lunar_to_solar(1, 1, 2033)
    ).days
    assert lunar.lunar_to_solar(1, 12, 2033) == date(2034, 1, 20)
    assert lunar.lunar_to_solar(1, 1, 2034) == date(2034, 2, 19)


@pytest.mark.parametrize(
    "nam",
    [2020, 2022, 2023, 2025, 2031, 2033, 2036, 2039],
    ids=lambda nam: f"năm-{nam}",
)
def test_hnd_lunar_year_months_nhat_quan_voi_solar_to_lunar(nam: int):
    """Hồi quy: danh sách tháng, số ngày tháng và ``solar_to_lunar`` phải khớp nhau.

    Đây là chống tái phát lỗi cũ (``lunar_month_days`` trả số âm / 59 ngày /
    ném ``ValueError``). Với mỗi tháng: mùng 1 đổi sang dương lịch rồi đổi
    ngược phải trả lại đúng tháng đó; số ngày phải bằng hiệu hai ngày mùng 1
    và nằm trong {29, 30}.
    """
    cac_thang = lunar.lunar_year_months(nam)
    assert len(cac_thang) in (12, 13)
    for i, (m, la_nhuan) in enumerate(cac_thang):
        dau = lunar.lunar_to_solar(1, m, nam, la_nhuan)
        assert lunar.solar_to_lunar(dau.day, dau.month, dau.year) == LunarDate(
            1, m, nam, la_nhuan
        ), f"{m}{' nhuận' if la_nhuan else ''}/{nam}: mùng 1 đổi ngược sai"
        if i + 1 < len(cac_thang):
            m_ke, nhuận_ke = cac_thang[i + 1]
            cuoi = lunar.lunar_to_solar(1, m_ke, nam, nhuận_ke)
        else:  # tháng Chạp → mùng 1 tháng Giêng năm sau
            cuoi = lunar.lunar_to_solar(1, 1, nam + 1)
        so_ngay = (cuoi - dau).days
        assert so_ngay in (29, 30), f"{m}{' nhuận' if la_nhuan else ''}/{nam} dài {so_ngay} ngày"
        assert lunar.lunar_month_days(m, nam, la_nhuan) == so_ngay


# ===========================================================================
# 3. Bốn điểm sóc lệch 1 ngày (đã ghi trong docstring lunar_precise)
# ===========================================================================
SOC_LECH_PARAMS = [
    pytest.param(
        date(2020, 5, 23),
        LunarDate(1, 4, 2020, True),
        id="05/2020-mùng-1-tháng-4-nhuận",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "ĐÃ BIẾT: HND cho mùng 1 tháng 4 nhuận 2020 = 22/05/2020; "
                "chuẩn (precise) = 23/05/2020, lệch 1 ngày."
            ),
        ),
    ),
    pytest.param(
        date(2023, 3, 22),
        LunarDate(1, 2, 2023, True),
        id="03/2023-mùng-1-tháng-2-nhuận",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "ĐÃ BIẾT: HND cho mùng 1 tháng 2 = 21/03/2023 (và có tháng Giêng "
                "nhuận); chuẩn = 22/03/2023 là mùng 1 tháng Hai nhuận."
            ),
        ),
    ),
    pytest.param(
        date(2026, 8, 13),
        LunarDate(1, 7, 2026, False),
        id="08/2026-mùng-1-tháng-7",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "ĐÃ BIẾT: HND cho mùng 1 tháng 7/2026 = 12/08/2026; "
                "chuẩn = 13/08/2026 (sóc 13/08 00:36 giờ VN)."
            ),
        ),
    ),
    pytest.param(
        date(2031, 4, 21),
        LunarDate(1, 3, 2031, True),
        id="04/2031-mùng-1-tháng-3-nhuận",
        marks=pytest.mark.xfail(
            strict=True,
            reason=(
                "ĐÃ BIẾT: HND cho 21/04/2031 = 30/3; chuẩn = 1/3 nhuận "
                "(precise), lệch 1 ngày."
            ),
        ),
    ),
]


@pytest.mark.parametrize("ngay_duong,am_chuan", SOC_LECH_PARAMS)
def test_hnd_cac_diem_soc_lech_mot_ngay(ngay_duong: date, am_chuan: LunarDate):
    """Mùng 1 theo chuẩn tại 4 điểm sóc biên mà HND tính lệch một ngày."""
    am = lunar.solar_to_lunar(ngay_duong.day, ngay_duong.month, ngay_duong.year)
    assert am == am_chuan


def test_hnd_va_precise_khop_nhau_o_moc_khong_bien():
    """Ngoài các điểm biên, hai engine phải khớp nhau (kiểm tra chéo)."""
    for ngay in (
        date(2026, 10, 28),  # yêu cầu của task
        date(2024, 2, 10),  # Tết Giáp Thìn
        date(2025, 1, 29),  # Tết Ất Tỵ
        date(2023, 9, 29),  # Trung Thu 2023
        date(2034, 2, 19),  # Tết Giáp Dần
    ):
        a = lunar_precise.solar_to_lunar(ngay.day, ngay.month, ngay.year)
        b = lunar.solar_to_lunar(ngay.day, ngay.month, ngay.year)
        assert a == b, f"{ngay}: precise={a} hnd={b}"


# ===========================================================================
# 4. Số ngày tháng nhuận (ĐÃ SỬA bởi Lead – test hồi quy)
# ===========================================================================
def test_hnd_so_ngay_thang_4_nhuan_2020():
    """``lunar_month_days`` không còn trả số âm: tháng 4 nhuận 2020 của HND = 30 ngày.

    Lưu ý: chuẩn (precise/lịch vạn niên) là **29 ngày** vì mùng 1 chuẩn là
    23/05/2020. Engine HND tính sóc sớm một ngày (22/05) nên tháng của nó
    dài 30 ngày – test khẳng định tính nhất quán nội bộ của HND, không phải
    con số chuẩn.
    """
    dau = lunar.lunar_to_solar(1, 4, 2020, leap=True)
    assert dau == date(2020, 5, 22), "HND có sóc lệch 1 ngày tại ca này"
    assert lunar.lunar_month_days(4, 2020, leap=True) == 30
    # Nhất quán với mùng 1 tháng kế tiếp.
    cuoi = lunar.lunar_to_solar(1, 5, 2020)
    assert (cuoi - dau).days == 30
    # Đối chiếu: engine chuẩn cho 29 ngày (23/05 → 20/06).
    assert lunar_precise.lunar_month_days(4, 2020, leap=True) == 29


def test_hnd_lunar_year_months_2023_dung_cau_truc_hnd():
    """Sau khi sửa: cấu trúc tháng năm 2023 do HND suy ra đúng như engine HND.

    HND vẫn coi tháng nhuận 2023 là *tháng Giêng nhuận* (đặc trưng của engine
    HND, khác chuẩn là tháng Hai nhuận – xem xfail ở trên), nhưng danh sách
    tháng và số ngày giờ đã nhất quán, không còn ném lỗi.
    """
    assert lunar.lunar_year_months(2023) == (
        (1, False),
        (1, True),
        (2, False),
        (3, False),
        (4, False),
        (5, False),
        (6, False),
        (7, False),
        (8, False),
        (9, False),
        (10, False),
        (11, False),
        (12, False),
    )
    tong = sum(lunar.lunar_month_days(m, 2023, l) for m, l in lunar.lunar_year_months(2023))
    assert tong == 384  # năm nhuận
    assert tong == (
        lunar.lunar_to_solar(1, 1, 2024) - lunar.lunar_to_solar(1, 1, 2023)
    ).days


def test_hnd_so_ngay_thang_1_nam_2023():
    """``lunar_month_days(1, 2023)`` không còn ném ``ValueError``.

    HND coi tháng nhuận 2023 là tháng Giêng nhuận (20/02→20/03), nên tháng
    Giêng thường chỉ còn 29 ngày (22/01→19/02).
    """
    assert lunar.lunar_month_days(1, 2023) in (29, 30)
    assert lunar.lunar_month_days(1, 2023) == 29
    dau = lunar.lunar_to_solar(1, 1, 2023)
    cuoi = lunar.lunar_to_solar(1, 1, 2023, leap=True)
    assert (cuoi - dau).days == 29
    # Không còn ngoại lệ với bất kỳ tháng nào của năm 2023.
    for m, la_nhuan in lunar.lunar_year_months(2023):
        assert lunar.lunar_month_days(m, 2023, la_nhuan) in (29, 30)


def test_hnd_moi_thang_dai_29_hoac_30_ngay():
    """Hồi quy 2000–2040: mọi tháng (kể cả tháng nhuận) dài 29/30 ngày, không âm."""
    for nam in range(2000, 2041):
        for m, la_nhuan in lunar.lunar_year_months(nam):
            so_ngay = lunar.lunar_month_days(m, nam, la_nhuan)
            assert so_ngay in (29, 30), (
                f"tháng {m}{' nhuận' if la_nhuan else ''}/{nam} trả {so_ngay} ngày"
            )


# ===========================================================================
# 5. Quan sát thêm (chưa đủ căn cứ kết luận)
# ===========================================================================
def test_hnd_va_precise_lech_nhau_o_soc_08_2035_quan_sat():
    """Ngoài 4 điểm sóc tài liệu, sóc 08/2035 cũng lệch một ngày.

    Docstring ``lunar_precise.py`` chỉ đo 185 tuần trăng 2020–2034 nên ca
    2035 không nằm trong danh sách. Không có lịch in bên ngoài để khẳng
    định engine nào đúng → test chỉ ghi nhận sự lệch.
    """
    assert lunar.solar_to_lunar(3, 8, 2035) == LunarDate(1, 7, 2035, False)
    assert lunar_precise.solar_to_lunar(3, 8, 2035) == LunarDate(30, 6, 2035, False)
    assert lunar_precise.solar_to_lunar(4, 8, 2035) == LunarDate(1, 7, 2035, False)


def test_hnd_tiet_khi_lech_precise_do_quy_uoc_moc_thoi_gian():
    """Ghi nhận: hai engine lệch tên tiết khí ở ngày biên vì mốc tính khác nhau.

    * HND chốt kinh độ Mặt Trời tại **nửa đêm** ngày đang xét (công thức gốc).
    * precise (sau khi Lead sửa) gán tiết khí cho **ngày chứa thời điểm bắt
      đầu** – quy ước của lịch vạn niên Việt Nam.

    Ví dụ:
    * 20/03/2026: Xuân Phân bắt đầu 21:37 giờ VN (trong ngày 20/03) → precise
      "Xuân Phân"; HND (nửa đêm 20/03 chưa qua điểm phân) vẫn "Kinh Trập".
    * 22/12/2026: Đông chí bắt đầu 03:49 giờ VN → precise "Đông Chí"; HND
      (nửa đêm 22/12 chưa qua) còn "Đại Tuyết".
    * 04/02/2026: Lập Xuân bắt đầu 02:55 giờ VN → precise "Lập Xuân"; HND
      "Đại Hàn".
    """
    assert lunar.tiet_khi_name(date(2026, 3, 20)) == "Kinh Trập"
    assert lunar_precise.tiet_khi_name(date(2026, 3, 20)) == "Xuân Phân"
    assert lunar.tiet_khi_name(date(2026, 12, 22)) == "Đại Tuyết"
    assert lunar_precise.tiet_khi_name(date(2026, 12, 22)) == "Đông Chí"
    assert lunar.tiet_khi_name(date(2026, 2, 4)) == "Đại Hàn"
    assert lunar_precise.tiet_khi_name(date(2026, 2, 4)) == "Lập Xuân"


# ===========================================================================
# 6. HND vẫn tự nhất quán trong giai đoạn khuyến nghị
# ===========================================================================
def test_hnd_lien_tuc_va_round_trip_1990_2040():
    """Dù lệch lịch chuẩn, chuỗi ngày của HND vẫn không bị đứt quãng."""
    ngay_dau = date(1990, 1, 1)
    ngay_cuoi = date(2040, 12, 31)
    truoc = lunar.solar_to_lunar(ngay_dau.day, ngay_dau.month, ngay_dau.year)
    loi: list[str] = []
    ngay = ngay_dau
    for _ in range((ngay_cuoi - ngay_dau).days):
        ngay += timedelta(days=1)
        hien_tai = lunar.solar_to_lunar(ngay.day, ngay.month, ngay.year)
        if hien_tai.day == 1:
            if hien_tai.month == 1 and not hien_tai.leap:
                ok = truoc.month == 12 and hien_tai.year == truoc.year + 1
            elif hien_tai.leap:
                ok = (
                    hien_tai.month == truoc.month
                    and hien_tai.year == truoc.year
                    and truoc.day >= 29
                )
            else:
                ok = hien_tai.month == truoc.month % 12 + 1 and hien_tai.year == truoc.year
            if not ok:
                loi.append(f"{ngay}: mùng 1 bất thường, trước là {truoc}")
        elif not (
            hien_tai.day == truoc.day + 1
            and hien_tai.month == truoc.month
            and hien_tai.leap == truoc.leap
            and hien_tai.year == truoc.year
        ):
            loi.append(f"{ngay}: ngày âm nhảy từ {truoc} sang {hien_tai}")
        if lunar.lunar_to_solar(
            hien_tai.day, hien_tai.month, hien_tai.year, hien_tai.leap
        ) != ngay:
            loi.append(f"{ngay}: round-trip sai (âm {hien_tai})")
        if loi:
            break
        truoc = hien_tai
    assert not loi, "HND bị đứt quãng:\n" + "\n".join(loi)


def test_hnd_giao_dien_engine_hop_le():
    """HND giữ đúng giao diện engine: hằng số và các hàm chính."""
    assert lunar.TIMEZONE == 7
    for ten in (
        "solar_to_lunar",
        "lunar_to_solar",
        "lunar_month_days",
        "lunar_year_months",
        "tiet_khi_index",
        "tiet_khi_name",
        "get_new_moon_day",
        "get_leap_month_offset",
    ):
        assert callable(getattr(lunar, ten)), f"thiếu hàm {ten}"
