"""Tầng dịch vụ: biến các con số âm lịch thành :class:`DayInfo` / :class:`MonthGrid`.

UI chỉ cần gọi hai hàm ở đây:

* :func:`get_day_info` – mọi thông tin của một ngày (đã gồm Can Chi, tiết
  khí, giờ hoàng đạo, ngày lễ, ngày hoàng đạo…).
* :func:`build_month_grid` – lưới 7 cột cho lịch tháng.

Kết quả được cache theo ngày nên chuyển tháng liên tục vẫn nhanh (đo được
~0,8 ms cho 42 ô khi cache nguội).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache
from typing import Iterable, Literal

from . import lunar, lunar_precise
from .canchi import (
    auspicious_hours,
    day_can_chi,
    is_auspicious_day,
    month_can_chi,
    year_can_chi,
    zodiac_animal,
)
from .holidays import holiday_for
from .types import DayInfo, MonthGrid

__all__ = [
    "EngineName",
    "ENGINES",
    "DEFAULT_ENGINE",
    "get_engine",
    "get_day_info",
    "build_month_grid",
    "today",
    "shift_month",
    "month_grid_from_anchor",
]

EngineName = Literal["precise", "hnd"]

#: Tên engine -> module
ENGINES: dict[str, object] = {"precise": lunar_precise, "hnd": lunar}

#: Engine mặc định. ``precise`` cho kết quả trùng lịch vạn niên Việt Nam;
#: ``hnd`` là bản sao thuần thuật toán Hồ Ngọc Đức (xem tài liệu so sánh).
DEFAULT_ENGINE: str = "precise"


def get_engine(name: str | None = None):
    """Trả về module engine âm lịch theo tên (mặc định ``precise``)."""
    return ENGINES.get(name or DEFAULT_ENGINE, lunar_precise)


def today() -> date:
    """Ngày hôm nay theo đồng hồ hệ thống (đặt riêng để dễ test)."""
    return date.today()


@lru_cache(maxsize=4096)
def get_day_info(day: date, engine: str = DEFAULT_ENGINE) -> DayInfo:
    """Dựng :class:`DayInfo` đầy đủ cho ngày ``day``.

    Args:
        day: ngày dương lịch cần tra.
        engine: ``"precise"`` (mặc định) hoặc ``"hnd"``.
    """
    eng = get_engine(engine)
    lunar_date = eng.solar_to_lunar(day.day, day.month, day.year)
    dcc = day_can_chi(day)
    return DayInfo(
        solar=day,
        lunar=lunar_date,
        weekday_index=day.weekday(),
        year_can_chi=year_can_chi(lunar_date.year),
        month_can_chi=month_can_chi(lunar_date.month, lunar_date.year),
        day_can_chi=dcc,
        zodiac=zodiac_animal(lunar_date.year),
        tiet_khi=eng.tiet_khi_name(day),
        auspicious_hours=auspicious_hours(day),
        is_auspicious_day=is_auspicious_day(lunar_date.month, dcc),
        holiday=holiday_for(day, lunar_date),
    )


def build_month_grid(
    year: int,
    month: int,
    engine: str = DEFAULT_ENGINE,
    first_day_of_week: int = 0,
) -> MonthGrid:
    """Dựng lưới lịch tháng, mỗi tuần đúng 7 ngày.

    Ô rìa thuộc tháng trước/sau vẫn được điền để lưới không trống; UI tự làm
    mờ chúng bằng cách so ``info.solar.month`` với ``month``.

    Args:
        year, month: tháng dương lịch cần dựng.
        engine: engine âm lịch.
        first_day_of_week: 0 = Thứ Hai (quy ước Việt Nam), 6 = Chủ Nhật.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Tháng dương lịch không hợp lệ: {month}")
    if not 0 <= first_day_of_week <= 6:
        raise ValueError("first_day_of_week phải trong 0..6")

    first = date(year, month, 1)
    lead = (first.weekday() - first_day_of_week) % 7
    start = first - timedelta(days=lead)
    days_in_month = calendar.monthrange(year, month)[1]
    rows = -(-(lead + days_in_month) // 7)  # ceil

    weeks: list[tuple[DayInfo, ...]] = []
    for row in range(rows):
        weeks.append(
            tuple(
                get_day_info(start + timedelta(days=row * 7 + col), engine)
                for col in range(7)
            )
        )
    return MonthGrid(year=year, month=month, weeks=tuple(weeks))


def shift_month(year: int, month: int, delta: int = 1) -> tuple[int, int]:
    """Dịch tháng ``delta`` bước (âm = lùi), trả ``(năm, tháng)``."""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def month_grid_from_anchor(
    anchor: str, engine: str = DEFAULT_ENGINE, first_day_of_week: int = 0
) -> MonthGrid:
    """Dựng lưới từ chuỗi neo ``"YYYY-MM"`` (rỗng = tháng hiện tại)."""
    if anchor:
        try:
            year_s, month_s = anchor.split("-", 1)
            year, month = int(year_s), int(month_s)
        except (ValueError, AttributeError):
            year = month = 0
        if 1900 <= year <= 2200 and 1 <= month <= 12:
            return build_month_grid(year, month, engine, first_day_of_week)
    now = today()
    return build_month_grid(now.year, now.month, engine, first_day_of_week)


def week_header(first_day_of_week: int = 0) -> tuple[str, ...]:
    """Nhãn 7 cột theo thứ tự tuần đã chọn: ``("T2", …, "CN")``."""
    from .canchi_constants import WEEKDAY_SHORT

    return tuple(
        WEEKDAY_SHORT[(first_day_of_week + i) % 7] for i in range(7)
    )


def iter_days(start: date, count: int) -> Iterable[date]:
    """Sinh ``count`` ngày liên tiếp kể từ ``start`` (tiện cho audit)."""
    for i in range(count):
        yield start + timedelta(days=i)
