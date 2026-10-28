"""Ngày lễ Việt Nam – cả Dương lịch lẫn Âm lịch.

Bảng dữ liệu thuần, không phụ thuộc ngày giờ hệ thống. Dùng để tô màu và
ghi chú trên bloc. Thứ tự ưu tiên: lễ Âm lịch (Tết, Giỗ Tổ…) trước, sau
đó mới tới lễ Dương lịch, vì lễ Âm lịch là "linh hồn" của lịch Việt.

Nếu một ngày trùng cả hai (rất hiếm), trả về chuỗi nối bằng " · ".
"""

from __future__ import annotations

from datetime import date

from .types import LunarDate

__all__ = ["solar_holiday", "lunar_holiday", "holiday_for", "SOLAR_HOLIDAYS", "LUNAR_HOLIDAYS"]

#: (tháng, ngày) → tên lễ theo Dương lịch
SOLAR_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Tết Dương lịch",
    (2, 3): "Thành lập Đảng",
    (3, 8): "Quốc tế Phụ nữ",
    (4, 30): "Giải phóng miền Nam",
    (5, 1): "Quốc tế Lao động",
    (5, 19): "Sinh nhật Bác Hồ",
    (6, 1): "Quốc tế Thiếu nhi",
    (9, 2): "Quốc khánh",
    (10, 20): "Phụ nữ Việt Nam",
    (11, 20): "Nhà giáo Việt Nam",
    (12, 22): "Thành lập QĐND Việt Nam",
    (12, 24): "Giáng sinh",
}

#: (tháng, ngày) → tên lễ theo Âm lịch
LUNAR_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Tết Nguyên Đán",
    (1, 2): "Mùng 2 Tết",
    (1, 3): "Mùng 3 Tết",
    (1, 15): "Tết Nguyên Tiêu",
    (3, 3): "Tết Hàn Thực",
    (3, 10): "Giỗ Tổ Hùng Vương",
    (4, 15): "Lễ Phật Đản",
    (5, 5): "Tết Đoan Ngọ",
    (7, 15): "Lễ Vu Lan",
    (8, 15): "Tết Trung Thu",
    (12, 23): "Ông Công Ông Táo",
}


def solar_holiday(day: date) -> str | None:
    """Tên ngày lễ Dương lịch của ``day`` (hoặc ``None``)."""
    return SOLAR_HOLIDAYS.get((day.month, day.day))


def lunar_holiday(lunar: LunarDate) -> str | None:
    """Tên ngày lễ Âm lịch; tháng nhuận không tính là ngày lễ."""
    if lunar.leap:
        return None
    return LUNAR_HOLIDAYS.get((lunar.month, lunar.day))


def holiday_for(day: date, lunar: LunarDate) -> str | None:
    """Gộp lễ Âm lịch và Dương lịch của cùng một ngày."""
    names = [n for n in (lunar_holiday(lunar), solar_holiday(day)) if n]
    if not names:
        return None
    return " · ".join(names)
