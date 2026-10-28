"""Thuật toán Âm lịch Việt Nam – bản chuyển từ "Âm lịch Việt Nam" của
Hồ Ngọc Đức (https://www.informatik.uni-leipzig.de/~duc/amlich/).

Đặc điểm kỹ thuật quan trọng
============================

1. **Múi giờ cố định UTC+7** (``TIMEZONE = 7``). Âm lịch Trung Quốc dùng
   UTC+8 nên một số tháng nhuận và ngày Tết hai nước lệch nhau (ví dụ Tết
   1985: Việt Nam 21/01, Trung Quốc 20/02). Hàm ở đây luôn trả ngày Việt Nam.
2. **Tháng nhuận** xác định bằng quy tắc: nếu giữa hai tháng 11 liên tiếp
   có 13 tuần trăng (> 365 ngày) thì năm đó có tháng nhuận, và tháng nhuận
   là tháng đầu tiên *không* chứa Trung khí (``get_leap_month_offset``).
3. **Năm âm lịch** bắt đầu từ Tết Nguyên Đán, không phải từ tháng 11 như
   âm lịch cổ. Vì vậy hàm ``solar_to_lunar`` phải thử cả năm trước/năm sau.

Các hàm đều thuần số học, không đọc đồng hồ hệ thống, nên kiểm thử được
bằng cách so sánh với bảng lịch vạn niên in sẵn.

Phạm vi chính xác khuyến nghị: **1800 – 2199**. Ngoài khoảng này thuật toán
vẫn chạy nhưng chuỗi Fourier rút gọn có thể lệch so với thiên văn thật.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from .types import LunarDate

__all__ = [
    "TIMEZONE",
    "jd_from_date",
    "jd_to_date",
    "new_moon",
    "sun_longitude",
    "get_new_moon_day",
    "get_sun_longitude",
    "get_lunar_month_11",
    "get_leap_month_offset",
    "solar_to_lunar",
    "lunar_to_solar",
    "lunar_month_days",
    "lunar_year_months",
    "tiet_khi_index",
    "tiet_khi_name",
]

PI = math.pi

#: Múi giờ dùng để tính âm lịch Việt Nam.
TIMEZONE = 7

#: Hằng số "tháng 11 năm 1900" của Hồ Ngọc Đức – mốc neo của thuật toán.
_ANCHOR_11 = 2415021  #: JDN của 01/01/1900 trừ 11 tháng? (xem get_lunar_month_11)
_CANONICAL_EPOCH = 2415021.076998695


# ---------------------------------------------------------------------------
# Chuyển đổi lịch Julius / Gregory  <->  số ngày Julius (JDN)
# ---------------------------------------------------------------------------
def jd_from_date(dd: int, mm: int, yy: int) -> int:
    """Đổi ngày Dương lịch sang số ngày Julius (JDN).

    Dùng cùng công thức cho cả lịch Julius (trước 1582-10-15) và Gregory;
    nhánh ``jd < 2299161`` tự chọn công thức Julius.

    >>> jd_from_date(1, 1, 2000)
    2451545
    """
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def jd_to_date(jd: int) -> tuple[int, int, int]:
    """Đổi số ngày Julius về ``(ngày, tháng, năm)`` Dương lịch.

    >>> jd_to_date(2451545)
    (1, 1, 2000)
    """
    if jd > 2299160:
        a = jd + 32044
        b = (4 * a + 3) // 146097
        c = a - (b * 146097) // 4
    else:
        b = 0
        c = jd + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = b * 100 + d - 4800 + (m // 10)
    return day, month, year


# ---------------------------------------------------------------------------
# Thiên văn: sóc (new moon) và kinh độ mặt trời
# ---------------------------------------------------------------------------
def new_moon(k: int) -> float:
    """Thời điểm sóc thứ ``k`` tính từ mốc 1900 (đơn vị JDN có phần lẻ).

    Dùng công thức chuỗi của Meeus, đủ chính xác cho lịch pháp (sai số vài
    phút, không ảnh hưởng việc xác định ngày vì ngày được làm tròn theo
    UTC+7 với lề khá lớn).
    """
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = PI / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 -= 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * mpr)
    c1 += 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 -= 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 -= 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 += 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))
    if t < -11:
        deltat = (
            0.001
            + 0.000839 * t
            + 0.0002261 * t2
            - 0.00000845 * t3
            - 0.000000081 * t * t3
        )
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    return jd1 + c1 - deltat


def sun_longitude(jdn: float) -> float:
    """Kinh độ biểu kiến của mặt trời (radian, 0..2π) tại thời điểm ``jdn``."""
    t = (jdn - 2451545.0) / 36525
    t2 = t * t
    dr = PI / 180
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(dr * 3 * m)
    l = l0 + dl
    l *= dr
    l -= PI * 2 * math.floor(l / (PI * 2))
    return l


# ---------------------------------------------------------------------------
# Các đại lượng dẫn xuất
# ---------------------------------------------------------------------------
def get_new_moon_day(k: int, timezone: int = TIMEZONE) -> int:
    """Ngày (JDN) bắt đầu tuần trăng thứ ``k`` theo múi giờ cho trước."""
    jd = new_moon(k)
    return int(math.floor(jd + 0.5 + timezone / 24))


def get_sun_longitude(day_number: int, timezone: int = TIMEZONE) -> int:
    """Chỉ số 12 "trung khí" (0..11) của ngày ``day_number``.

    Giá trị 0 ứng với Xuân Phân, 1 ứng với Cốc Vũ… (mỗi bước 30°).
    """
    return int(math.floor(sun_longitude(day_number - 0.5 - timezone / 24) / PI * 6))


def get_lunar_month_11(yy: int, timezone: int = TIMEZONE) -> int:
    """Ngày (JDN) bắt đầu tháng 11 âm lịch của năm Dương lịch ``yy``.

    Tháng 11 là tháng chứa Đông chí; đây là mốc để biết một năm có tháng
    nhuận hay không.
    """
    off = jd_from_date(31, 12, yy) - _ANCHOR_11
    k = int(math.floor(off / 29.530588853))
    nm = get_new_moon_day(k, timezone)
    sun_long = get_sun_longitude(nm, timezone)
    if sun_long >= 9:
        nm = get_new_moon_day(k - 1, timezone)
    return nm


def get_leap_month_offset(a11: int, timezone: int = TIMEZONE) -> int:
    """Vị trí tháng nhuận tính từ tháng 11 (1..13).

    Trả chỉ số ``i`` sao cho tháng thứ ``i`` kể từ tháng 11 là tháng nhuận;
    ``i - 1`` chính là số tháng kể từ tháng 11 tới tháng nhuận.
    """
    k = int(math.floor((a11 - _CANONICAL_EPOCH) / 29.530588853 + 0.5))
    last = 0
    i = 1
    arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
    while i < 14:
        last = arc
        i += 1
        arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
        if arc == last:
            break
    return i - 1


# ---------------------------------------------------------------------------
# API chính
# ---------------------------------------------------------------------------
def solar_to_lunar(dd: int, mm: int, yy: int, timezone: int = TIMEZONE) -> LunarDate:
    """Đổi ngày Dương lịch sang Âm lịch Việt Nam.

    >>> solar_to_lunar(10, 2, 2024)   # Tết Giáp Thìn
    LunarDate(day=1, month=1, year=2024, leap=False)
    """
    day_number = jd_from_date(dd, mm, yy)
    k = int(math.floor((day_number - _CANONICAL_EPOCH) / 29.530588853))
    month_start = get_new_moon_day(k + 1, timezone)
    if month_start > day_number:
        month_start = get_new_moon_day(k, timezone)

    a11 = get_lunar_month_11(yy, timezone)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = get_lunar_month_11(yy - 1, timezone)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month_11(yy + 1, timezone)

    lunar_day = day_number - month_start + 1
    diff = int(math.floor((month_start - a11) / 29))
    lunar_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = get_leap_month_offset(a11, timezone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return LunarDate(day=lunar_day, month=lunar_month, year=lunar_year, leap=lunar_leap)


def lunar_to_solar(
    day: int,
    month: int,
    year: int,
    leap: bool = False,
    timezone: int = TIMEZONE,
) -> date:
    """Đổi ngày Âm lịch sang Dương lịch.

    Raises:
        ValueError: nếu ``(month, leap)`` không tồn tại trong năm ``year``
            (ví dụ yêu cầu tháng 3 nhuận ở năm không có tháng nhuận).
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Tháng âm không hợp lệ: {month}")
    if not 1 <= day <= 30:
        raise ValueError(f"Ngày âm không hợp lệ: {day}")

    if month < 11:
        a11 = get_lunar_month_11(year - 1, timezone)
        b11 = get_lunar_month_11(year, timezone)
    else:
        a11 = get_lunar_month_11(year, timezone)
        b11 = get_lunar_month_11(year + 1, timezone)

    k = int(math.floor((a11 - _CANONICAL_EPOCH) / 29.530588853 + 0.5))
    off = month - 11
    if off < 0:
        off += 12

    if b11 - a11 > 365:
        leap_off = get_leap_month_offset(a11, timezone)
        leap_month = leap_off - 2
        if leap_month < 0:
            leap_month += 12
        if leap:
            if month != leap_month:
                raise ValueError(
                    f"Tháng {month} không phải tháng nhuận của năm {year} "
                    f"(tháng nhuận là {leap_month})"
                )
            off = leap_off
        else:
            # Các tháng sau tháng nhuận phải cộng thêm 1 vì có thêm một tuần trăng.
            if off >= leap_off:
                off += 1
    elif leap:
        raise ValueError(f"Năm {year} không có tháng nhuận")

    month_start = get_new_moon_day(k + off, timezone)
    dd, mm, yy = jd_to_date(month_start + day - 1)
    return date(yy, mm, dd)


def lunar_month_days(
    month: int,
    year: int,
    leap: bool = False,
    timezone: int = TIMEZONE,
) -> int:
    """Số ngày của một tháng âm: 29 hoặc 30.

    Được suy ra **từ chính phép chuyển đổi** của engine này (đếm tiến từng
    ngày cho tới khi sang tháng khác), nhờ vậy luôn nhất quán với
    :func:`solar_to_lunar` và không bao giờ trả số âm.
    """
    start = lunar_to_solar(1, month, year, leap, timezone)
    for count in range(28, 31):
        probe = start + timedelta(days=count)
        lunar_day = solar_to_lunar(probe.day, probe.month, probe.year, timezone)
        if (lunar_day.month, lunar_day.leap, lunar_day.year) != (month, leap, year):
            return count
    return 30


def lunar_year_months(
    year: int, timezone: int = TIMEZONE
) -> tuple[tuple[int, bool], ...]:
    """Danh sách ``(tháng, nhuận?)`` của một năm âm lịch theo thứ tự thời gian.

    Đi từ Tết năm ``year`` tới Tết năm sau và ghi lại tháng gặp được, nên tự
    động bao gồm cả tháng nhuận 11/12 (trường hợp mà công thức chỉ số của bản
    gốc Hồ Ngọc Đức bỏ sót).
    """
    start = lunar_to_solar(1, 1, year, False, timezone)
    end = lunar_to_solar(1, 1, year + 1, False, timezone)
    out: list[tuple[int, bool]] = []
    seen: set[tuple[int, bool]] = set()
    cursor = start
    while cursor < end:
        lunar_day = solar_to_lunar(cursor.day, cursor.month, cursor.year, timezone)
        key = (lunar_day.month, lunar_day.leap)
        if key not in seen:
            seen.add(key)
            out.append(key)
        cursor += timedelta(days=1)
    return tuple(out)


# ---------------------------------------------------------------------------
# Tiết khí (24 tiết) – dùng lại chuỗi kinh độ mặt trời ở trên
# ---------------------------------------------------------------------------
def tiet_khi_index(day: date) -> int:
    """Chỉ số 0..23 của tiết khí ứng với ngày ``day``.

    0 = Lập Xuân (kinh độ 315°), 3 = Xuân Phân, 12 = Lập Thu, 21 = Đông Chí…
    """
    jdn = jd_from_date(day.day, day.month, day.year)
    longitude_step = int(math.floor(sun_longitude(jdn - 0.5 - TIMEZONE / 24) / (PI / 12)))
    return (longitude_step - 21) % 24


def tiet_khi_name(day: date) -> str:
    """Tên tiết khí của ngày, ví dụ ``"Thanh Minh"``."""
    from .canchi_constants import TIET_KHI

    return TIET_KHI[tiet_khi_index(day)]
