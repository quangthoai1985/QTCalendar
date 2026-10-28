"""Kiểu dữ liệu dùng chung giữa tầng core – platform – ui.

Toàn bộ kiểu ở đây là *bất biến* (``frozen``) và có ``slots`` để tiết kiệm
bộ nhớ: một lưới lịch tháng 6x7 tạo ra 42 đối tượng ``DayInfo``, mỗi đối
tượng chỉ chiếm đúng số ô cần thiết.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterator

from .canchi_constants import LUNAR_MONTH_NAMES, WEEKDAY_NAMES, WEEKDAY_SHORT

__all__ = [
    "LunarDate",
    "CanChi",
    "AuspiciousHour",
    "DayInfo",
    "MonthGrid",
    "Quote",
    "WEEKDAY_NAMES",
    "WEEKDAY_SHORT",
]


@dataclass(frozen=True, slots=True)
class LunarDate:
    """Một ngày âm lịch.

    Attributes:
        day: ngày âm (1..30).
        month: tháng âm (1..12). Với tháng nhuận, ``month`` vẫn là tháng gốc.
        year: năm âm lịch (có thể lệch 1 so với năm dương lịch).
        leap: ``True`` nếu đây là ngày thuộc tháng nhuận.
    """

    day: int
    month: int
    year: int
    leap: bool = False

    @property
    def leap_text(self) -> str:
        """``" (nhuận)"`` hoặc chuỗi rỗng – ghép thẳng vào câu hiển thị."""
        return " (nhuận)" if self.leap else ""

    def __str__(self) -> str:  # pragma: no cover - tiện debug
        leap = " nhuận" if self.leap else ""
        return f"{self.day}/{self.month}{leap}/{self.year}"


@dataclass(frozen=True, slots=True)
class CanChi:
    """Một cặp Can Chi, ví dụ ``CanChi("Ất", "Tỵ")``."""

    can: str
    chi: str

    @property
    def text(self) -> str:
        """Chuỗi hiển thị, ví dụ ``"Ất Tỵ"``."""
        return f"{self.can} {self.chi}"

    def __str__(self) -> str:  # pragma: no cover - tiện debug
        return self.text


@dataclass(frozen=True, slots=True)
class AuspiciousHour:
    """Một giờ hoàng đạo (mỗi "giờ" là một canh 2 tiếng đồng hồ).

    Attributes:
        chi: tên địa chi của giờ, ví dụ ``"Tý"``.
        start: giờ bắt đầu (0..23), ví dụ 23.
        end: giờ kết thúc (0..23), ví dụ 1.
        god: tên vị thần trấn giờ, ví dụ ``"Thanh Long"``.
    """

    chi: str
    start: int
    end: int
    god: str = ""

    @property
    def time_text(self) -> str:
        """``"23:00 – 01:00"``."""
        return f"{self.start:02d}:00 – {self.end:02d}:00"

    @property
    def compact_text(self) -> str:
        """``"Tý 23–01"`` – dạng ngắn hiển thị trên widget."""
        return f"{self.chi} {self.start:02d}–{self.end:02d}"

    def __str__(self) -> str:  # pragma: no cover - tiện debug
        return f"{self.chi} ({self.time_text})"


@dataclass(frozen=True, slots=True)
class Quote:
    """Một câu ca dao / tục ngữ / danh ngôn trong kho dữ liệu offline."""

    text: str
    author: str = ""
    topic: str = "ca-dao"

    @property
    def credit(self) -> str:
        """Phần ghi nguồn, ví dụ ``"Tục ngữ Việt Nam"``; rỗng nếu là ca dao."""
        return self.author


@dataclass(frozen=True, slots=True)
class DayInfo:
    """Thông tin đầy đủ của một ngày – đầu vào duy nhất cho mọi view.

    ``DayInfo`` được dựng bởi :func:`qtcalendar.core.calendar_service.get_day_info`.
    UI không bao giờ tự tính ngày; nó chỉ đọc các trường ở đây.
    """

    solar: date
    lunar: LunarDate
    weekday_index: int  #: 0 = Thứ Hai … 6 = Chủ Nhật (theo ``date.weekday()``)
    year_can_chi: CanChi
    month_can_chi: CanChi
    day_can_chi: CanChi
    zodiac: str
    tiet_khi: str
    auspicious_hours: tuple[AuspiciousHour, ...] = ()
    is_auspicious_day: bool = False
    holiday: str | None = None
    lunar_month_char: str = "Đ"  #: 'Đ' = Đủ (30 ngày), 'T' = Thiếu (29 ngày)

    # ---- tiện ích dẫn xuất -------------------------------------------------

    @property
    def weekday_name(self) -> str:
        """``"Thứ Hai"`` … ``"Chủ Nhật"``."""
        return WEEKDAY_NAMES[self.weekday_index]

    @property
    def weekday_short(self) -> str:
        """``"T2"`` … ``"CN"``."""
        return WEEKDAY_SHORT[self.weekday_index]

    @property
    def is_sunday(self) -> bool:
        return self.weekday_index == 6

    @property
    def weekday_en(self) -> str:
        """``"MONDAY"`` … ``"SUNDAY"``."""
        names = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")
        return names[self.weekday_index]

    @property
    def solar_month_en(self) -> str:
        """``"JANUARY"`` … ``"DECEMBER"``."""
        names = (
            "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
            "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
        )
        return names[self.solar.month - 1]

    @property
    def solar_month_vn(self) -> str:
        """``"THÁNG MỘT"`` … ``"THÁNG MƯỜI HAI"``."""
        names = (
            "THÁNG MỘT", "THÁNG HAI", "THÁNG BA", "THÁNG TƯ", "THÁNG NĂM", "THÁNG SÁU",
            "THÁNG BẢY", "THÁNG TÁM", "THÁNG CHÍN", "THÁNG MƯỜI", "THÁNG MƯỜI MỘT", "THÁNG MƯỜI HAI"
        )
        return names[self.solar.month - 1]

    @property
    def day_of_year(self) -> int:
        return self.solar.timetuple().tm_yday

    @property
    def week_of_year(self) -> int:
        return self.solar.isocalendar()[1]

    @property
    def hour_ty_can_chi(self) -> CanChi:
        from .canchi_constants import CAN
        can_idx = CAN.index(self.day_can_chi.can)
        return CanChi(CAN[(2 * can_idx) % 10], "Tý")

    @property
    def is_month_start(self) -> bool:
        """Ngày mùng 1 âm lịch."""
        return self.lunar.day == 1

    @property
    def is_full_moon(self) -> bool:
        """Ngày rằm (15 âm lịch)."""
        return self.lunar.day == 15

    @property
    def is_lunar_new_year(self) -> bool:
        """Mùng 1 tháng Giêng."""
        return self.lunar.day == 1 and self.lunar.month == 1 and not self.lunar.leap

    @property
    def lunar_day_text(self) -> str:
        """``"Mùng 1"``, ``"Rằm"``, ``"Ngày 12"`` …"""
        d = self.lunar.day
        if d == 15:
            return "Rằm"
        if d == 1:
            return "Mùng 1"
        if d < 10:
            return f"Mùng {d}"
        return f"Ngày {d}"

    @property
    def lunar_line(self) -> str:
        """``"Ngày 12 tháng Ba (nhuận)"`` – dòng âm lịch trên bloc."""
        return (
            f"{self.lunar_day_text} tháng "
            f"{LUNAR_MONTH_NAMES[self.lunar.month - 1]}{self.lunar.leap_text}"
        )

    def __str__(self) -> str:  # pragma: no cover - tiện debug
        return f"{self.solar:%d/%m/%Y} ({self.weekday_name}) – {self.lunar_line}"


@dataclass(frozen=True, slots=True)
class MonthGrid:
    """Lưới lịch tháng gồm các tuần, mỗi tuần đúng 7 ngày.

    ``weeks`` luôn chứa ngày của tháng trước/sau ở các ô rìa để lưới không
    bị trống; UI tự làm mờ những ô có ``solar.month != month``.
    """

    year: int
    month: int
    weeks: tuple[tuple[DayInfo, ...], ...]

    @property
    def days(self) -> Iterator[DayInfo]:
        """Duyệt toàn bộ ô theo thứ tự đọc."""
        for week in self.weeks:
            yield from week

    @property
    def title(self) -> str:
        """``"Tháng 10 / 2026"``."""
        return f"Tháng {self.month} / {self.year}"

    @property
    def lunar_month_title(self) -> str:
        """Tháng âm của ngày mùng 1 trong tháng, ví dụ ``"Tháng Tám"``."""
        for week in self.weeks:
            for info in week:
                if info.solar.month == self.month and info.is_month_start:
                    label = LUNAR_MONTH_NAMES[info.lunar.month - 1]
                    return f"Tháng {label}{info.lunar.leap_text}"
        return ""
