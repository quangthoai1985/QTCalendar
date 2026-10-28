"""Can Chi và giờ hoàng đạo.

Quy tắc cổ truyền
=================

* **Can Chi của năm**: ``can = (năm + 6) % 10``, ``chi = (năm + 8) % 12``.
* **Can Chi của tháng**: tháng Giêng luôn là Dần; can tháng khởi từ can năm
  theo quy tắc "Giáp – Kỷ khởi Bính", "Ất – Canh khởi Mậu", "Bính – Tân
  khởi Canh", "Đinh – Nhâm khởi Nhâm", "Mậu – Quý khởi Giáp", tức
  ``can = (2 * can_năm + tháng + 1) % 10``.
* **Can Chi của ngày**: chu kỳ 60 ngày liên tục, neo theo JDN:
  ``can = (JDN + 9) % 10``, ``chi = (JDN + 1) % 12``. Mốc kiểm chứng:
  01/01/2000 (JDN 2451545) là ngày **Mậu Ngọ**.

Giờ hoàng đạo
=============

Mỗi ngày có 12 canh giờ (mỗi canh 2 tiếng, bắt đầu từ Tý 23h–01h). Mười hai
vị thần luân phiên theo giờ với bước 1; vị trí khởi đầu (Thanh Long) phụ
thuộc chi của ngày::

    Thanh Long = (2 * chi_ngày + 8) % 12

Sáu vị thần thuộc nhóm hoàng đạo là Thanh Long, Minh Đường, Kim Quỹ,
Bảo Quang, Ngọc Đường, Tư Mệnh. Với ngày Tý ta được các giờ
Thân, Dậu, Tý, Sửu, Mão, Ngọ – đúng như lịch vạn niên ghi.

Ngày hoàng đạo / hắc đạo
========================

Cùng chu kỳ 12 thần nhưng theo **tháng âm lịch**: tháng Giêng và tháng Bảy
(chi Dần – Thân) khởi Thanh Long tại ngày Tý, rồi tiến 2 chi mỗi tháng::

    chi của ngày Thanh Long = (2 * (tháng âm - 1)) % 12

Suy ra tháng Giêng có ngày hoàng đạo là Tý, Sửu, Thìn, Tỵ, Mùi, Tuất –
đúng câu "tháng Giêng ngày hoàng đạo là Tý, Sửu, Thìn, Tỵ, Mùi, Tuất".
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from .canchi_constants import (
    AUSPICIOUS_GOD_INDEXES,
    CAN,
    CHI,
    HOUR_GODS,
    LUNAR_MONTH_NAMES,
    ZODIAC,
)
from .lunar import jd_from_date
from .types import AuspiciousHour, CanChi

__all__ = [
    "year_can_chi",
    "month_can_chi",
    "day_can_chi",
    "zodiac_animal",
    "auspicious_hours",
    "is_auspicious_day",
    "hour_of_day",
    "lunar_month_label",
]


def year_can_chi(year: int) -> CanChi:
    """Can Chi của năm âm lịch.

    >>> year_can_chi(2024).text
    'Giáp Thìn'
    """
    return CanChi(CAN[(year + 6) % 10], CHI[(year + 8) % 12])


def month_can_chi(month: int, year: int) -> CanChi:
    """Can Chi của tháng âm lịch ``month`` (1..12) trong năm ``year``.

    >>> month_can_chi(1, 2024).text
    'Bính Dần'
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Tháng âm không hợp lệ: {month}")
    can_index = (2 * ((year + 6) % 10) + month + 1) % 10
    chi_index = (month + 1) % 12
    return CanChi(CAN[can_index], CHI[chi_index])


def day_can_chi(day: date) -> CanChi:
    """Can Chi của ngày Dương lịch ``day``.

    >>> day_can_chi(date(2000, 1, 1)).text
    'Mậu Ngọ'
    """
    jdn = jd_from_date(day.day, day.month, day.year)
    return CanChi(CAN[(jdn + 9) % 10], CHI[(jdn + 1) % 12])


def zodiac_animal(year: int) -> str:
    """Con giáp của năm âm lịch (``Mão`` → ``Mèo`` theo cách gọi Việt Nam)."""
    return ZODIAC[(year + 8) % 12]


def _hour_start(hour_index: int) -> int:
    """Giờ đồng hồ bắt đầu của canh thứ ``hour_index`` (0 = Tý → 23h)."""
    return (23 + 2 * hour_index) % 24


@lru_cache(maxsize=4096)
def auspicious_hours(day: date) -> tuple[AuspiciousHour, ...]:
    """Sáu giờ hoàng đạo của ngày ``day``, xếp theo thứ tự trong ngày.

    Mỗi phần tử mang cả tên thần trấn giờ để giao diện có thể hiển thị
    dạng nâng cao.
    """
    jdn = jd_from_date(day.day, day.month, day.year)
    day_chi = (jdn + 1) % 12
    thanh_long = (2 * day_chi + 8) % 12
    result: list[AuspiciousHour] = []
    for h in range(12):
        god_index = (h - thanh_long) % 12
        if god_index not in AUSPICIOUS_GOD_INDEXES:
            continue
        start = _hour_start(h)
        result.append(
            AuspiciousHour(
                chi=CHI[h],
                start=start,
                end=(start + 2) % 24,
                god=HOUR_GODS[god_index],
            )
        )
    return tuple(result)


def hour_of_day(day: date, hour: int) -> tuple[int, AuspiciousHour | None]:
    """Canh giờ chứa thời điểm ``hour`` (0..23) của ngày.

    Returns:
        ``(chỉ số canh 0..11, giờ hoàng đạo tương ứng hoặc None)``.

    Quy ước: canh Tý gồm 23:00–00:59, tức nửa đêm thuộc *canh* của ngày kế
    tiếp về mặt lịch pháp, nhưng với mục đích hiển thị ta giữ nguyên ngày
    đang xem.
    """
    if not 0 <= hour <= 23:
        raise ValueError(f"Giờ không hợp lệ: {hour}")
    index = ((hour + 1) % 24) // 2
    target_chi = CHI[index]
    for item in auspicious_hours(day):
        if item.chi == target_chi:
            return index, item
    return index, None


def is_auspicious_day(lunar_month: int, day: CanChi) -> bool:
    """``True`` nếu ngày là ngày hoàng đạo theo tháng âm lịch."""
    if not 1 <= lunar_month <= 12:
        raise ValueError(f"Tháng âm không hợp lệ: {lunar_month}")
    day_chi_index = CHI.index(day.chi)
    thanh_long_chi = (2 * (lunar_month - 1)) % 12
    offset = (day_chi_index - thanh_long_chi) % 12
    return offset in AUSPICIOUS_GOD_INDEXES


def lunar_month_label(month: int, leap: bool = False) -> str:
    """``"Tháng Giêng"``, ``"Tháng Chạp"``, ``"Tháng Ba (nhuận)"``."""
    if not 1 <= month <= 12:
        raise ValueError(f"Tháng âm không hợp lệ: {month}")
    suffix = " (nhuận)" if leap else ""
    return f"Tháng {LUNAR_MONTH_NAMES[month - 1]}{suffix}"
