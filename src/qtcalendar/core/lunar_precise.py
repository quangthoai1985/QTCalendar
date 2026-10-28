"""Engine âm lịch chính xác cao – giữ nguyên *triết lý* thuật toán Hồ Ngọc Đức
nhưng thay các nguyên hàm xấp xỉ bằng chuỗi chính xác của Meeus, và thay
phép đánh số tháng bằng một **bảng tháng liên tục**.

Vì sao cần lớp này?
===================

Thuật toán gốc Hồ Ngọc Đức dùng chuỗi Fourier rút gọn cho sóc (``NewMoon``)
và cho kinh độ mặt trời (``SunLongitude``). Sai số của chuỗi này khoảng
**±50 phút**. Phần lớn thời gian không ảnh hưởng gì, nhưng khi điểm sóc rơi
gần nửa đêm (giờ Hà Nội) thì nó làm *lệch hẳn một ngày*, hoặc khi một trung
khí rơi sát mốc chuyển tháng thì nó làm *sai tên tháng nhuận*.

Đo trên 185 tuần trăng (2020–2034) bằng chương trình so sánh:
có **4 lần** ngày mùng 1 theo công thức gốc khác một ngày so với thiên văn thật::

    Tuần trăng   Hồ Ngọc Đức        Chính xác
    05/2020      22/05/2020         23/05/2020
    03/2023      21/03/2023         22/03/2023   ← kéo theo sai *tên* tháng nhuận
    08/2026      12/08/2026         13/08/2026
    04/2031      22/04/2031         21/04/2031

Và trên 1990–2040, hai lần tên tháng nhuận khác nhau: 2023 (HND: tháng Giêng
nhuận – sai; chính xác: tháng Hai nhuận) và 2039.

Engine này xử lý bằng ba thay đổi:

1. **Sóc**: 25 số hạng chính + 14 số hạng nhiễu hành tinh của Meeus
   (Astronomical Algorithms, ch. 49), có hiệu chỉnh ΔT ⇒ sai số dưới 1 phút.
2. **Trung khí**: xét kinh độ mặt trời (Meeus ch. 25) tại **nửa đêm địa
   phương của ngày mùng 1** – đúng với quy ước "tháng âm tính theo ngày".
   Nếu xét tại đúng thời điểm sóc sẽ sai với các tháng mà trung khí rơi cùng
   ngày nhưng trước giờ sóc (ví dụ 小雪 tháng 11/2014).
3. **Đánh số tháng**: dựng bảng tháng liên tục từ các mốc *tháng chứa Đông
   chí* (tháng 11), rồi gán số và đánh dấu nhuận bằng quy tắc "tháng đầu
   tiên không chứa trung khí". Cách này xử lý đúng cả hai trường hợp hiểm
   là **tháng 11 nhuận / tháng 12 nhuận** (bài toán "2033" nổi tiếng của
   lịch Trung Quốc – Việt Nam, năm 2033 có tháng Một nhuận).

API giống hệt :mod:`qtcalendar.core.lunar` nên hai engine hoán đổi được::

    from qtcalendar.core import lunar, lunar_precise
    lunar_precise.solar_to_lunar(28, 10, 2026)

Phạm vi khuyến nghị: **1800 – 2199**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from .lunar import jd_from_date, jd_to_date
from .types import LunarDate

__all__ = [
    "TIMEZONE",
    "engine_name",
    "delta_t_seconds",
    "new_moon_jde",
    "new_moon_jd",
    "sun_apparent_longitude",
    "winter_solstice_jd",
    "new_moon_day",
    "month11_start",
    "leap_offset",
    "solar_to_lunar",
    "lunar_to_solar",
    "lunar_month_days",
    "lunar_year_months",
    "tiet_khi_index",
    "tiet_khi_name",
]

TIMEZONE = 7

#: Tên engine, dùng cho log và hộp thoại cài đặt.
engine_name = "precise"

#: Kỷ nguyên J2000: 12h TT ngày 01/01/2000.
_J2000 = 2451545.0

#: Tốc độ trung bình của mặt trời theo kinh độ (độ/ngày).
_SUN_DEG_PER_DAY = 0.98564736


# ===========================================================================
# 1. ΔT (Terrestrial Time − Universal Time) – đa thức Espenak–Meeus
# ===========================================================================
def delta_t_seconds(year: float) -> float:
    """Chênh lệch TT − UT (giây).

    Sai số vài giây chỉ làm dịch điểm sóc dưới 0,1 phút nên hoàn toàn đủ cho
    lịch pháp.
    """
    y = year
    if 2005 <= y <= 2050:
        t = y - 2000.0
        return 62.92 + 0.32217 * t + 0.005589 * t * t
    if 1986 <= y < 2005:
        t = y - 2000.0
        return (
            63.86
            + 0.3345 * t
            - 0.060374 * t**2
            + 0.0017275 * t**3
            + 0.000651814 * t**4
            + 0.00002373599 * t**5
        )
    if 1961 <= y < 1986:
        t = y - 1975.0
        return 45.45 + 1.067 * t - t * t / 260.0 - t * t * t / 718.0
    if 1941 <= y < 1961:
        t = y - 1950.0
        return 29.07 + 0.407 * t - t * t / 233.0 + t * t * t / 2547.0
    if 1920 <= y < 1941:
        t = y - 1920.0
        return 21.20 + 0.84493 * t - 0.0761 * t**2 + 0.0020936 * t**3
    if 1900 <= y < 1920:
        t = y - 1900.0
        return (
            -2.79
            + 1.494119 * t
            - 0.0598939 * t**2
            + 0.0061966 * t**3
            - 0.000197 * t**4
        )
    if 1860 <= y < 1900:
        t = y - 1860.0
        return (
            7.62
            + 0.5737 * t
            - 0.251754 * t**2
            + 0.01680668 * t**3
            - 0.0004473624 * t**4
            + t**5 / 233174.0
        )
    if 1800 <= y < 1860:
        t = y - 1800.0
        return (
            13.72
            - 0.332447 * t
            + 0.0068612 * t**2
            + 0.0041116 * t**3
            - 0.00037436 * t**4
            + 0.0000121272 * t**5
            - 0.0000001699 * t**6
            + 0.000000000875 * t**7
        )
    if 2050 < y <= 2150:
        u = (y - 1820.0) / 100.0
        return -20.0 + 32.0 * u * u - 0.5628 * (2150.0 - y)
    u = (y - 1820.0) / 100.0
    return -20.0 + 32.0 * u * u


# ===========================================================================
# 2. Sóc chính xác (Meeus ch. 49) và kinh độ mặt trời (Meeus ch. 25)
# ===========================================================================
#: Nhiễu của các hành tinh tác động lên pha mặt trăng (Meeus, bảng 49.A).
_PLANET_TERMS: tuple[tuple[float, float], ...] = (
    (299.77, 0.000325),
    (251.88, 0.000165),
    (251.83, 0.000164),
    (349.42, 0.000126),
    (84.66, 0.000110),
    (141.74, 0.000062),
    (207.14, 0.000060),
    (154.84, 0.000054),
    (34.52, 0.000038),
    (207.19, 0.000030),
    (291.34, 0.000029),
    (161.72, 0.000026),
    (239.56, 0.000026),
    (331.55, 0.000026),
)


def new_moon_jde(k: float) -> float:
    """Thời điểm sóc thứ ``k`` theo giờ TT (JDE), chính xác cỡ 1 phút.

    ``k = 0`` ứng với sóc ngày 06/01/2000; mỗi tuần trăng ``k`` tăng 1.
    """
    t = k / 1236.85
    t2, t3, t4 = t * t, t**3, t**4
    jde = (
        2451550.09766
        + 29.530588861 * k
        + 0.00015437 * t2
        - 0.000000150 * t3
        + 0.00000000073 * t4
    )

    k_m = 0.0000021 * k
    e = 1.0 - 0.002516 * t - 0.0000074 * t2
    m = math.radians(2.5534 + 29.10535670 * k - 0.0000014 * t2 - 0.00000011 * t3)
    mp = math.radians(
        201.5643
        + 385.81693528 * k
        + 0.0107582 * t2
        + 0.00001238 * t3
        - 0.000000058 * t4
    )
    f = math.radians(
        160.7108
        + 390.67050284 * k
        - 0.0016118 * t2
        - 0.00000227 * t3
        + 0.000000011 * t4
    )
    om = math.radians(124.7746 - 1.56375588 * k + 0.0020672 * t2 + 0.00000215 * t3)

    sin = math.sin
    corr = (
        -0.40720 * sin(mp)
        + 0.17241 * e * sin(m)
        + 0.01608 * sin(2 * mp)
        + 0.01039 * sin(2 * f)
        + 0.00739 * e * sin(mp - m)
        - 0.00514 * e * sin(mp + m)
        + 0.00208 * e * e * sin(2 * m)
        - 0.00111 * sin(mp - 2 * f)
        - 0.00057 * sin(mp + 2 * f)
        + 0.00056 * e * sin(2 * mp + m)
        - 0.00042 * sin(3 * mp)
        + 0.00042 * e * sin(m + 2 * f)
        + 0.00038 * e * sin(m - 2 * f)
        - 0.00024 * e * sin(2 * mp - m)
        - 0.00017 * sin(om)
        - 0.00007 * sin(mp + 2 * m)
        + 0.00004 * sin(2 * mp - 2 * f)
        + 0.00004 * sin(3 * m)
        + 0.00003 * sin(mp + m - 2 * f)
        + 0.00003 * sin(2 * mp + 2 * f)
        - 0.00003 * sin(mp + m + 2 * f)
        + 0.00003 * sin(mp - m + 2 * f)
        - 0.00002 * sin(mp - m - 2 * f)
        - 0.00002 * sin(3 * mp + m)
        + 0.00002 * sin(4 * mp)
    )
    for base, amp in _PLANET_TERMS:
        corr += amp * sin(math.radians(base) + k_m)
    return jde + corr


def _jd_to_year(jd: float) -> float:
    """Năm thập phân gần đúng của một JD (đủ để tra ΔT)."""
    return (jd - _J2000) / 365.2425 + 2000.0


def new_moon_jd(k: float) -> float:
    """Thời điểm sóc thứ ``k`` theo giờ UT (đã trừ ΔT)."""
    jde = new_moon_jde(k)
    return jde - delta_t_seconds(_jd_to_year(jde)) / 86400.0


def sun_apparent_longitude(jd_ut: float) -> float:
    """Kinh độ biểu kiến của mặt trời, độ trong ``[0, 360)``.

    Công thức độ chính xác vừa của Meeus (ch. 25), có hiệu chỉnh quang sai
    và chương động; sai số cỡ 0,01° tương đương 15 phút thời gian.
    """
    t = (jd_ut - _J2000) / 36525.0
    t2 = t * t
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t2
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t2)
    c = (
        (1.914602 - 0.004817 * t - 0.000014 * t2) * math.sin(m)
        + (0.019993 - 0.000101 * t) * math.sin(2 * m)
        + 0.000289 * math.sin(3 * m)
    )
    omega = math.radians(125.04 - 1934.136 * t)
    apparent = l0 + c - 0.00569 - 0.00478 * math.sin(omega)
    return apparent % 360.0


def winter_solstice_jd(year: int) -> float:
    """JD (UT) của Đông chí tháng 12 năm ``year`` (kinh độ mặt trời 270°)."""
    jd = jd_from_date(21, 12, year)  # 21/12 12:00 UT
    for _ in range(12):
        diff = ((270.0 - sun_apparent_longitude(jd) + 180.0) % 360.0) - 180.0
        if abs(diff) < 1e-7:
            break
        jd += diff / _SUN_DEG_PER_DAY
    return jd


# ===========================================================================
# 3. Bảng tháng liên tục (xương sống của engine)
# ===========================================================================
def _day_number(jd_ut: float, timezone: int = TIMEZONE) -> int:
    """Đổi thời điểm UT sang số ngày Julius của *ngày dương lịch địa phương*."""
    return int(math.floor(jd_ut + 0.5 + timezone / 24.0))


def new_moon_day(k: int, timezone: int = TIMEZONE) -> int:
    """JDN của ngày mùng 1 tuần trăng thứ ``k`` theo giờ địa phương."""
    return _day_number(new_moon_jd(k), timezone)


@lru_cache(maxsize=4096)
def _lunation_of_day(day_number: int) -> int:
    """Chỉ số ``k`` của tuần trăng chứa ngày ``day_number``."""
    k = int(round((day_number - 2451550.09766) / 29.530588861))
    while new_moon_day(k) > day_number:
        k -= 1
    while new_moon_day(k + 1) <= day_number:
        k += 1
    return k


@lru_cache(maxsize=8192)
def _sun_segment_at_new_moon(k: int) -> int:
    """Chỉ số 12 trung khí (0..11) **của ngày** bắt đầu tuần trăng thứ ``k``.

    Xét tại nửa đêm địa phương của ngày mùng 1 (chứ không phải tại đúng thời
    điểm sóc) vì tháng âm lịch được tính theo *ngày*.
    """
    day = new_moon_day(k)
    jd_local_midnight = day - 0.5 - TIMEZONE / 24.0
    lon = sun_apparent_longitude(jd_local_midnight)
    return int(math.floor(lon / 30.0)) % 12


def _has_zhongqi(k: int) -> bool:
    """``True`` nếu tháng bắt đầu ở tuần trăng ``k`` có chứa một trung khí."""
    return _sun_segment_at_new_moon(k) != _sun_segment_at_new_moon(k + 1)


@lru_cache(maxsize=2048)
def _k11(year: int) -> int:
    """Tuần trăng của tháng 11 âm lịch năm ``year`` = tháng chứa Đông chí."""
    return _lunation_of_day(_day_number(winter_solstice_jd(year)))


@dataclass(frozen=True, slots=True)
class _Month:
    """Một tháng trong bảng tháng liên tục."""

    number: int  #: số tháng 1..12
    leap: bool  #: tháng nhuận?
    year: int  #: năm âm lịch chứa tháng này
    start: int  #: JDN ngày mùng 1
    days: int  #: 29 hoặc 30

    @property
    def label(self) -> str:
        return f"{self.number}{' nhuận' if self.leap else ''}/{self.year}"


def _next_number(number: int) -> int:
    """Tháng kế tiếp trong chuỗi đánh số 11, 12, 1, 2, …, 10."""
    if number == 11:
        return 12
    if number == 12:
        return 1
    return number + 1


@lru_cache(maxsize=1024)
def _span(year: int) -> tuple[_Month, ...]:
    """Chuỗi tháng từ tháng 11 năm ``year`` tới sát tháng 11 năm ``year + 1``.

    Chuỗi này dài 12 tháng, hoặc 13 tháng nếu năm có tháng nhuận. Tháng
    nhuận là tháng **đầu tiên không chứa trung khí** (quy tắc cổ truyền);
    nó mang số của tháng đứng ngay trước nó.
    """
    k_a = _k11(year)
    k_b = _k11(year + 1)
    count = k_b - k_a
    leap_at = 0
    if count >= 13:
        for j in range(1, count):
            if not _has_zhongqi(k_a + j):
                leap_at = j
                break

    months: list[_Month] = []
    number, lunar_year = 11, year
    for j in range(count):
        is_leap = leap_at > 0 and j == leap_at
        if j > 0 and not is_leap:
            number = _next_number(number)
            if number == 1:
                lunar_year += 1
        start = new_moon_day(k_a + j)
        months.append(
            _Month(
                number=number,
                leap=is_leap,
                year=lunar_year,
                start=start,
                days=new_moon_day(k_a + j + 1) - start,
            )
        )
    return tuple(months)


@lru_cache(maxsize=1024)
def _year_entries(year: int) -> tuple[_Month, ...]:
    """Các tháng của một năm âm lịch, xếp theo thời gian, gồm cả tháng nhuận."""
    before = tuple(m for m in _span(year - 1) if m.year == year)
    after = tuple(m for m in _span(year) if m.year == year)
    return before + after


@lru_cache(maxsize=1024)
def month11_start(year: int, timezone: int = TIMEZONE) -> int:
    """JDN ngày mùng 1 tháng 11 âm lịch (tháng chứa Đông chí) của năm ``year``."""
    return new_moon_day(_k11(year), timezone)


def leap_offset(a11: int, timezone: int = TIMEZONE) -> int:
    """Vị trí tháng nhuận tính từ tháng 11 có ngày mùng 1 là ``a11``.

    Trả về ``j`` (1..13) nếu tháng nhuận là tháng thứ ``j`` kể từ tháng 11,
    hoặc ``0`` nếu khoảng đó không có tháng nhuận. Giữ lại để tương thích
    với API của thuật toán gốc.
    """
    k_a = _lunation_of_day(a11)
    approx_year = int(_jd_to_year(a11))
    for candidate in (approx_year - 1, approx_year, approx_year + 1):
        if _k11(candidate) == k_a:
            for j, month in enumerate(_span(candidate)):
                if month.leap:
                    return j
            return 0
    return 0


# ===========================================================================
# 4. Chuyển đổi hai chiều
# ===========================================================================
def solar_to_lunar(dd: int, mm: int, yy: int, timezone: int = TIMEZONE) -> LunarDate:
    """Đổi ngày Dương lịch sang Âm lịch Việt Nam.

    >>> solar_to_lunar(10, 2, 2024)
    LunarDate(day=1, month=1, year=2024, leap=False)
    """
    day_number = jd_from_date(dd, mm, yy)
    k = _lunation_of_day(day_number)

    span_year = None
    for candidate in (yy - 1, yy, yy + 1):
        if _k11(candidate) <= k < _k11(candidate + 1):
            span_year = candidate
            break
    if span_year is None:  # pragma: no cover - ngoài phạm vi 1800–2199
        raise ValueError(f"Ngày {dd}/{mm}/{yy} nằm ngoài phạm vi hỗ trợ")

    entry = _span(span_year)[k - _k11(span_year)]
    return LunarDate(
        day=day_number - entry.start + 1,
        month=entry.number,
        year=entry.year,
        leap=entry.leap,
    )


def _find_month(year: int, month: int, leap: bool) -> _Month:
    for entry in _year_entries(year):
        if entry.number == month and entry.leap == leap:
            return entry
    raise ValueError(f"Tháng {month}{' nhuận' if leap else ''} không tồn tại trong năm {year}")


def lunar_to_solar(
    day: int,
    month: int,
    year: int,
    leap: bool = False,
    timezone: int = TIMEZONE,
) -> date:
    """Đổi ngày Âm lịch sang Dương lịch.

    Raises:
        ValueError: nếu tháng/năm không tồn tại hoặc ngày vượt số ngày
            của tháng (ví dụ yêu cầu ngày 30 của tháng thiếu).
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Tháng âm không hợp lệ: {month}")
    if not 1 <= day <= 30:
        raise ValueError(f"Ngày âm không hợp lệ: {day}")
    entry = _find_month(year, month, leap)
    if day > entry.days:
        raise ValueError(
            f"Tháng {month}{' nhuận' if leap else ''}/{year} chỉ có {entry.days} ngày"
        )
    solar_day, solar_month, solar_year = jd_to_date(entry.start + day - 1)
    return date(solar_year, solar_month, solar_day)


def lunar_year_months(
    year: int, timezone: int = TIMEZONE
) -> tuple[tuple[int, bool], ...]:
    """Danh sách ``(tháng, nhuận?)`` của năm âm lịch theo thứ tự thời gian."""
    return tuple((m.number, m.leap) for m in _year_entries(year))


def lunar_month_days(
    month: int,
    year: int,
    leap: bool = False,
    timezone: int = TIMEZONE,
) -> int:
    """Số ngày (29 hoặc 30) của tháng âm."""
    return _find_month(year, month, leap).days


def lunar_month_start(year: int, month: int, leap: bool = False) -> date:
    """Ngày Dương lịch của mùng 1 âm lịch."""
    solar_day, solar_month, solar_year = jd_to_date(_find_month(year, month, leap).start)
    return date(solar_year, solar_month, solar_day)


# ===========================================================================
# 5. Tiết khí
# ===========================================================================
def tiet_khi_index(day: date) -> int:
    """Chỉ số 0..23 của tiết khí **ghi cho ngày** ``day``.

    Quy ước khớp lịch vạn niên: ngày được ghi bằng tiết khí *bắt đầu* trong
    ngày đó; nếu ngày không có tiết khí nào bắt đầu thì giữ tiết khí đang
    hiệu lực từ hôm trước. Vì vậy cần xét kinh độ mặt trời tại **hai** mốc:
    nửa đêm và nửa đêm hôm sau.
    """
    jdn = jd_from_date(day.day, day.month, day.year)
    start = jdn - 0.5 - TIMEZONE / 24.0  # nửa đêm giờ Hà Nội
    step_start = int(math.floor(sun_apparent_longitude(start) / 15.0))
    step_end = int(math.floor(sun_apparent_longitude(start + 1.0) / 15.0))
    # Nếu trong ngày có mốc tiết khí mới ⇒ ghi tên tiết khí mới.
    step = step_end if step_end != step_start else step_start
    return (step - 21) % 24


def tiet_khi_name(day: date) -> str:
    """Tên tiết khí của ngày, ví dụ ``"Sương Giáng"``."""
    from .canchi_constants import TIET_KHI

    return TIET_KHI[tiet_khi_index(day)]
