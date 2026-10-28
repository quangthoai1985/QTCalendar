"""Công cụ audit lịch Dương – Âm của QT Calendar.

In bảng lịch tháng dạng text thuần để **so tay với lịch vạn niên**: mỗi ô
ghi ``dương/âm``, dấu ``*`` đánh dấu ngày thuộc tháng nhuận âm lịch.

Cách dùng::

    python -X utf8 scripts/audit_calendar.py             # tháng hiện tại
    python -X utf8 scripts/audit_calendar.py 2026 10     # tháng 10/2026
    python -X utf8 scripts/audit_calendar.py 2023 3      # tháng 3/2023 (có tháng Hai nhuận)
    python -X utf8 scripts/audit_calendar.py --year 2023 # cả NĂM ÂM 2023: 13 tháng, gồm tháng nhuận
    python -X utf8 scripts/audit_calendar.py --year 2026 # cả năm âm 2026: 12 tháng
    python -X utf8 scripts/audit_calendar.py --engine hnd 2026 10   # đối chiếu engine Hồ Ngọc Đức

Ghi chú:

* ``--year`` là **năm âm lịch** (nên mới có 12 hoặc 13 tháng). Muốn xem
  một tháng dương lịch cụ thể thì truyền ``NĂM THÁNG`` (ví dụ ``2026 10``).
* Mặc định dùng engine ``precise`` (engine chính xác, khớp lịch vạn niên
  Việt Nam). ``--engine hnd`` in theo engine Hồ Ngọc Đức để tiện đối chiếu
  các ca lệch đã biết (xem ``tests/test_lunar_hnd.py``).
* Tuần bắt đầu Thứ Hai (quy ước Việt Nam).
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

# Cho phép chạy trực tiếp ``python scripts/audit_calendar.py`` từ thư mục
# gốc dự án: thêm ``src/`` vào sys.path trước khi import gói qtcalendar.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from qtcalendar.core import calendar_service  # noqa: E402
from qtcalendar.core.canchi import (  # noqa: E402
    lunar_month_label,
    month_can_chi,
    year_can_chi,
)
from qtcalendar.core.canchi_constants import WEEKDAY_NAMES  # noqa: E402
from qtcalendar.core.types import DayInfo  # noqa: E402

#: Bề rộng một ô lịch (đủ cho "28/18" hoặc "22/01*").
CELL_WIDTH = 8

#: Độ dài dòng kẻ ngang của bảng: 7 ô + 6 dấu cách phân cách.
LINE_WIDTH = CELL_WIDTH * 7 + 6

#: Engine mặc định của công cụ (trùng engine mặc định của ứng dụng).
DEFAULT_ENGINE = calendar_service.DEFAULT_ENGINE

#: Các engine được hỗ trợ để in bảng.
ENGINE_CHOICES = tuple(calendar_service.ENGINES)


# ===========================================================================
# Định dạng ô / dòng
# ===========================================================================
def _o_ngay(ngay_duong: int, ngay_am: int, nhuận: bool) -> str:
    """Nội dung một ô lịch: ``"dương/âm"``, thêm ``*`` nếu tháng nhuận."""
    noi_dung = f"{ngay_duong:02d}/{ngay_am:02d}" + ("*" if nhuận else "")
    return f"{noi_dung:^{CELL_WIDTH}}"


def _o_trong() -> str:
    """Ô trống ở đầu/cuối lưới tháng âm."""
    return " " * CELL_WIDTH


def _hang_o(cac_o: Sequence[str]) -> str:
    """Ghép các ô của một tuần thành một dòng."""
    return " ".join(cac_o)


def _hang_tieu_de(first_day_of_week: int = 0) -> str:
    """Dòng nhãn 7 cột theo thứ tự tuần đã chọn: ``T2 … CN``."""
    return " ".join(
        f"{x:^{CELL_WIDTH}}" for x in calendar_service.week_header(first_day_of_week)
    )


def _ten_thu(ngay: date) -> str:
    """Tên thứ tiếng Việt của một ngày dương lịch."""
    return WEEKDAY_NAMES[ngay.weekday()]


def _duong_ke(char: str = "-") -> str:
    return char * LINE_WIDTH


# ===========================================================================
# 1. Bảng một tháng DƯƠNG lịch
# ===========================================================================
def render_solar_month(
    year: int,
    month: int,
    engine: str = DEFAULT_ENGINE,
    first_day_of_week: int = 0,
) -> str:
    """Trả về bảng text của tháng dương lịch ``month/year``.

    Mỗi dòng: 7 ô, mỗi ô ``"dương/âm"``. Ô rìa (thuộc tháng trước/sau) vẫn
    được in đủ để lưới không trống.

    Args:
        year, month: tháng dương lịch cần in.
        engine: ``"precise"`` (mặc định) hoặc ``"hnd"``.
        first_day_of_week: 0 = Thứ Hai … 6 = Chủ Nhật.
    """
    luoi = calendar_service.build_month_grid(year, month, engine, first_day_of_week)

    # Tìm ngày mùng 1 âm lịch đầu tiên rơi trong tháng để đặt tiêu đề phụ.
    am_dau: DayInfo | None = None
    for info in luoi.days:
        if info.solar.month == month and info.is_month_start:
            am_dau = info
            break
    if am_dau is not None:
        nhan_am = lunar_month_label(am_dau.lunar.month, am_dau.lunar.leap)
        phu = f"Âm lịch: {nhan_am}, năm {year_can_chi(am_dau.lunar.year).text}"
    else:  # pragma: no cover - mọi tháng dương đều chứa ít nhất một mùng 1 âm
        phu = "Âm lịch: (không xác định)"

    dong: list[str] = []
    dong.append(_duong_ke("="))
    dong.append(f"THÁNG {month} / {year}  ·  {phu}  ·  engine: {engine}")
    dong.append(_duong_ke("="))
    dong.append(_hang_tieu_de(first_day_of_week))
    dong.append(_duong_ke())
    for tuan in luoi.weeks:
        dong.append(_hang_o([_o_ngay(info.solar.day, info.lunar.day, info.lunar.leap) for info in tuan]))
    dong.append(_duong_ke())
    dau = luoi.weeks[0][0].solar
    cuoi = luoi.weeks[-1][-1].solar
    nhan_nhuan = "  ·  * = tháng nhuận âm lịch" if "*" in "\n".join(dong) else ""
    dong.append(
        f"Ô = dương/âm{nhan_nhuan}  ·  Tuần: {dau:%d/%m/%Y} → {cuoi:%d/%m/%Y}"
    )
    return "\n".join(dong)


# ===========================================================================
# 2. Bảng một tháng ÂM lịch
# ===========================================================================
def _moc_thang_am(
    year: int, month: int, leap: bool, engine: str
) -> tuple[date, date, int]:
    """Trả ``(mùng 1, mùng 1 tháng kế tiếp, số ngày)`` của một tháng âm.

    Dùng danh sách tháng của chính engine thay vì ``lunar_month_days`` để
    tránh phụ thuộc vào hành vi của engine ``hnd`` (vốn có lỗi đã biết với
    tháng nhuận).
    """
    eng = calendar_service.get_engine(engine)
    cac_thang = eng.lunar_year_months(year)
    try:
        vi_tri = cac_thang.index((month, leap))
    except ValueError:  # pragma: no cover - tham số đã được kiểm tra trước
        raise SystemExit(f"Engine {engine} không có tháng {month}{' nhuận' if leap else ''}/{year}")
    if vi_tri + 1 < len(cac_thang):
        m_ke, nhuận_ke = cac_thang[vi_tri + 1]
        nam_ke = year
    else:
        m_ke, nhuận_ke = 1, False
        nam_ke = year + 1
    dau = eng.lunar_to_solar(1, month, year, leap)
    cuoi = eng.lunar_to_solar(1, m_ke, nam_ke, nhuận_ke)
    return dau, cuoi, (cuoi - dau).days


def render_lunar_month(year: int, month: int, leap: bool = False, engine: str = DEFAULT_ENGINE) -> str:
    """Trả về bảng text của một tháng ÂM lịch (lưới 7 cột bắt đầu Thứ Hai).

    Ô ghi ``"dương/âm"``; mọi ô đều thuộc đúng tháng âm đang xem.
    """
    dau, cuoi, so_ngay = _moc_thang_am(year, month, leap, engine)
    nhan_thang = lunar_month_label(month, leap)
    tieu_de = (
        f"{nhan_thang}  ·  năm {year_can_chi(year).text}"
        f"  ·  {month_can_chi(month, year).text}"
    )
    dong: list[str] = []
    dong.append(_duong_ke("="))
    dong.append(tieu_de)
    dong.append(
        f"Mùng 1: {dau:%d/%m/%Y} ({_ten_thu(dau)})  →  hết: "
        f"{cuoi - timedelta(days=1):%d/%m/%Y}  ·  {so_ngay} ngày  ·  engine: {engine}"
    )
    dong.append(_duong_ke("="))
    dong.append(_hang_tieu_de(0))
    dong.append(_duong_ke())
    # Căn cột: ô trống đầu tuần thứ nhất theo thứ của ngày mùng 1.
    o_dau = dau.weekday()
    so_o_trong = o_dau
    so_hang = math.ceil((so_o_trong + so_ngay) / 7)
    vi_tri_ngay = 0
    for hang in range(so_hang):
        cac_o: list[str] = []
        for cot in range(7):
            chi_so_o = hang * 7 + cot
            if chi_so_o < so_o_trong or vi_tri_ngay >= so_ngay:
                cac_o.append(_o_trong())
                continue
            ngay_duong = dau + timedelta(days=vi_tri_ngay)
            cac_o.append(_o_ngay(ngay_duong.day, vi_tri_ngay + 1, leap))
            vi_tri_ngay += 1
        dong.append(_hang_o(cac_o))
    dong.append(_duong_ke())
    nhan_nhuan = "  ·  * = tháng nhuận âm lịch" if leap else ""
    dong.append(f"Ô = dương/âm{nhan_nhuan}")
    if so_ngay not in (29, 30):  # pragma: no cover - chỉ engine hnd mới có ca này
        dong.append(f"[!] CẢNH BÁO: tháng này dài {so_ngay} ngày – dữ liệu engine không nhất quán.")
    return "\n".join(dong)


# ===========================================================================
# 3. Bảng cả năm ÂM lịch (12 hoặc 13 tháng, gồm tháng nhuận)
# ===========================================================================
def render_lunar_year(year: int, engine: str = DEFAULT_ENGINE) -> str:
    """In cả năm âm lịch: 12 tháng thường, hoặc 13 nếu có tháng nhuận."""
    eng = calendar_service.get_engine(engine)
    cac_thang = eng.lunar_year_months(year)
    so_thang = len(cac_thang)
    thang_nhuan = [m for m, la_nhuan in cac_thang if la_nhuan]
    mo_ta_nhuan = f", có tháng {thang_nhuan[0]} nhuận" if thang_nhuan else ", không có tháng nhuận"

    dong: list[str] = []
    dong.append(_duong_ke("#"))
    dong.append(f"NĂM ÂM LỊCH {year}  ·  {year_can_chi(year).text}  ·  {so_thang} tháng{mo_ta_nhuan}")
    mung_mot = eng.lunar_to_solar(1, 1, year)
    mung_mot_sau = eng.lunar_to_solar(1, 1, year + 1)
    dong.append(
        f"Mùng 1 tháng Giêng: {mung_mot:%d/%m/%Y} ({_ten_thu(mung_mot)})"
        f"  ·  Mùng 1 năm sau: {mung_mot_sau:%d/%m/%Y}  ·  engine: {engine}"
    )
    dong.append(
        "Ô = dương/âm"
        + ("   ·   * = tháng nhuận âm lịch" if thang_nhuan else "")
        + "   ·   tuần bắt đầu Thứ Hai"
    )
    dong.append(_duong_ke("#"))

    for i, (thang, la_nhuan) in enumerate(cac_thang):
        dong.append("")
        dong.append(render_lunar_month(year, thang, la_nhuan, engine))
    dong.append("")
    dong.append(_duong_ke("="))
    return "\n".join(dong)


# ===========================================================================
# 4. Giao diện dòng lệnh
# ===========================================================================
def build_parser() -> argparse.ArgumentParser:
    """Tạo bộ phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        prog="audit_calendar.py",
        description="In bảng lịch Dương – Âm dạng text để đối chiếu với lịch vạn niên.",
        epilog=(
            "Ví dụ: python scripts/audit_calendar.py 2026 10 | "
            "python scripts/audit_calendar.py --year 2023"
        ),
    )
    parser.add_argument("nam", nargs="?", type=int, help="năm dương lịch (1900–2200)")
    parser.add_argument("thang", nargs="?", type=int, help="tháng dương lịch (1–12)")
    parser.add_argument(
        "--year",
        dest="nam_am",
        type=int,
        metavar="NĂM",
        help="in cả NĂM ÂM LỊCH (12/13 tháng, gồm tháng nhuận)",
    )
    parser.add_argument(
        "--engine",
        choices=ENGINE_CHOICES,
        default=DEFAULT_ENGINE,
        help=f"engine âm lịch để in (mặc định: {DEFAULT_ENGINE})",
    )
    return parser


def _kiem_tra_nam(parser: argparse.ArgumentParser, nam: int) -> None:
    if not 1900 <= nam <= 2200:
        parser.error(f"năm {nam} ngoài phạm vi hỗ trợ 1900–2200")


def main(argv: Sequence[str] | None = None) -> int:
    """Điểm vào của script. Trả mã thoát (0 = thành công)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.nam_am is not None:
        if args.nam is not None or args.thang is not None:
            parser.error("--year không dùng chung với tham số NĂM THÁNG")
        _kiem_tra_nam(parser, args.nam_am)
        print(render_lunar_year(args.nam_am, args.engine))
        return 0

    if args.thang is not None and args.nam is None:
        parser.error("cần nhập đủ NĂM và THÁNG (ví dụ: 2026 10)")

    if args.nam is None:
        # Không có tham số: in tháng hiện tại.
        hom_nay = calendar_service.today()
        nam, thang = hom_nay.year, hom_nay.month
    else:
        nam = args.nam
        if args.thang is None:
            parser.error("cần nhập đủ NĂM và THÁNG (ví dụ: 2026 10)")
        _kiem_tra_nam(parser, nam)
        if not 1 <= args.thang <= 12:
            parser.error(f"tháng {args.thang} không hợp lệ (phải trong 1–12)")
        thang = args.thang

    print(render_solar_month(nam, thang, args.engine))
    return 0


if __name__ == "__main__":  # pragma: no cover - chạy trực tiếp
    raise SystemExit(main())
