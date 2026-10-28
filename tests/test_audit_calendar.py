"""Kiểm chứng công cụ ``scripts/audit_calendar.py``.

Công cụ này là "kính lúp" để so tay với lịch vạn niên, nên test tập trung
vào **nội dung bảng** chứ không phải màu sắc/format:

* Bảng tháng dương phải có đúng 7 cột T2…CN, mỗi ô ghi ``dương/âm`` khớp
  dữ liệu âm lịch; các ô rìa vẫn được điền.
* Tháng có tháng nhuận âm phải đánh dấu ``*`` đúng ngày.
* ``--year`` in cả năm âm: 12 tháng, hoặc 13 tháng khi có tháng nhuận.
* Đổi ``--engine hnd`` phải in theo engine Hồ Ngọc Đức.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_calendar.py"

#: Một ô lịch hợp lệ: "dương/âm" (2 chữ số mỗi phần), có thể thêm "*".
O_RE = re.compile(r"^\d{2}/\d{2}\*?$")


@pytest.fixture(scope="module")
def audit():
    """Nạp ``audit_calendar.py`` như một module (không chạy ``main``)."""
    spec = importlib.util.spec_from_file_location("audit_calendar_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cac_dong(text: str) -> list[str]:
    return text.splitlines()


def _dong_tieu_de(text: str) -> list[str]:
    """Các dòng là nhãn 7 cột T2…CN."""
    return [d for d in _cac_dong(text) if d.split() == ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]]


def _dong_o(text: str) -> list[list[str]]:
    """Các dòng lưới có đủ 7 ô (bỏ qua dòng có ô trống của tháng âm)."""
    ket_qua = []
    for dong in _cac_dong(text):
        o = dong.split()
        if len(o) == 7 and all(O_RE.match(x) for x in o):
            ket_qua.append(o)
    return ket_qua


# ===========================================================================
# 1. Hằng số giao diện
# ===========================================================================
def test_cong_cu_co_hang_so_va_engine_mac_dinh(audit):
    """Công cụ dùng engine mặc định của ứng dụng và hỗ trợ cả hai engine."""
    assert audit.DEFAULT_ENGINE == "precise"
    assert set(audit.ENGINE_CHOICES) == {"precise", "hnd"}
    assert audit.CELL_WIDTH >= 7  # đủ chỗ cho "28/18" và dấu "*"


# ===========================================================================
# 2. Bảng tháng dương
# ===========================================================================
def test_bang_thang_10_2026_dung_7_cot_va_dung_du_lieu(audit):
    """Bảng 10/2026: 7 cột, 5 hàng, mỗi ô dương/âm đúng như dữ liệu âm lịch."""
    text = audit.render_solar_month(2026, 10)
    assert "THÁNG 10 / 2026" in text
    assert "Tháng Chín" in text  # tháng âm của mùng 1 rơi trong tháng
    assert "Bính Ngọ" in text
    assert "engine: precise" in text
    assert len(_dong_tieu_de(text)) == 1, "phải có đúng một dòng nhãn T2…CN"

    dong_o = _dong_o(text)
    assert len(dong_o) == 5, "01/10/2026 là Thứ Năm nên lưới tối thiểu 5 hàng"
    # Toàn bộ 35 ô, bắt đầu 28/09 (âm 18/8) và kết thúc 01/11 (âm 23/9).
    cac_o = [o for dong in dong_o for o in dong]
    assert cac_o == [
        "28/18", "29/19", "30/20", "01/21", "02/22", "03/23", "04/24",
        "05/25", "06/26", "07/27", "08/28", "09/29", "10/01", "11/02",
        "12/03", "13/04", "14/05", "15/06", "16/07", "17/08", "18/09",
        "19/10", "20/11", "21/12", "22/13", "23/14", "24/15", "25/16",
        "26/17", "27/18", "28/19", "29/20", "30/21", "31/22", "01/23",
    ]


def test_bang_thang_3_2023_danh_dau_thang_nhuan(audit):
    """Tháng 3/2023 có tháng Hai nhuận: các ngày từ 22/03 trở đi phải có dấu '*'."""
    text = audit.render_solar_month(2023, 3)
    assert "Tháng Hai (nhuận)" in text
    # 22/03/2023 = mùng 1 tháng 2 nhuận; 02/04/2023 = 12/2 nhuận (ô cuối lưới).
    assert "22/01*" in text
    assert "02/12*" in text
    # Ngày 19/03 vẫn thuộc tháng 2 thường (ngày 28).
    assert "19/28" in text
    # Chú thích ý nghĩa dấu *.
    assert "* = tháng nhuận" in text


def test_bang_thang_co_6_hang_khi_can(audit):
    """Tháng 8/2026 (bắt đầu Thứ Bảy, 31 ngày) phải in 6 hàng."""
    assert len(_dong_o(audit.render_solar_month(2026, 8))) == 6


def test_moi_o_trong_bang_thang_hop_le(audit):
    """Mọi ô của lưới phải có dạng dương/âm hợp lệ, không ô rỗng giữa lưới."""
    for nam, thang in ((2026, 10), (2023, 3), (2026, 2), (2024, 2)):
        text = audit.render_solar_month(nam, thang)
        dong_o = _dong_o(text)
        assert dong_o, f"{thang}/{nam}: không tìm thấy dòng lưới"
        for dong in dong_o:
            assert len(dong) == 7
            for o in dong:
                assert O_RE.match(o)


# ===========================================================================
# 3. Bảng tháng âm
# ===========================================================================
def test_bang_thang_hai_nhuan_2023(audit):
    """Tháng 2 nhuận 2023: mùng 1 ngày 22/03/2023, 29 ngày, ô đánh dấu '*'."""
    text = audit.render_lunar_month(2023, 2, leap=True)
    assert "Tháng Hai (nhuận)" in text
    assert "22/03/2023" in text
    assert "29 ngày" in text
    # Ô ghi "dương/âm": ngày đầu là 22/01* (22/03 dương, mùng 1 âm),
    # ngày cuối là 19/29* (19/04 dương, 29 âm).
    assert "22/01*" in text
    assert "19/29*" in text
    # Đúng số ô ngày (không có ô trống lọt vào giữa).
    so_o_ngay = sum(len(dong.split()) for dong in _cac_dong(text) if O_RE.match(dong.split()[0] if dong.split() else ""))
    assert so_o_ngay == 29


def test_bang_thang_am_khong_nhuan(audit):
    """Tháng Chín 2026: mùng 1 = 10/10/2026, 30 ngày, không có dấu '*'."""
    text = audit.render_lunar_month(2026, 9)
    assert "Tháng Chín" in text
    assert "10/10/2026" in text
    assert "30 ngày" in text
    assert "*" not in text


# ===========================================================================
# 4. Bảng cả năm âm (--year)
# ===========================================================================
def test_in_ca_nam_2023_du_13_thang(audit):
    """Năm âm 2023 có 13 tháng (tháng Hai nhuận) – phải in đủ 13 khối."""
    text = audit.render_lunar_year(2023)
    assert "NĂM ÂM LỊCH 2023" in text
    assert "Quý Mão" in text
    assert "13 tháng" in text
    assert "có tháng 2 nhuận" in text
    assert "Tháng Hai (nhuận)" in text
    assert text.count("Mùng 1:") == 13


def test_in_ca_nam_2026_du_12_thang(audit):
    """Năm âm 2026 là năm thường: đúng 12 tháng, không có dấu '*'."""
    text = audit.render_lunar_year(2026)
    assert "NĂM ÂM LỊCH 2026" in text
    assert "Bính Ngọ" in text
    assert "12 tháng" in text
    assert "không có tháng nhuận" in text
    assert text.count("Mùng 1:") == 12
    assert "*" not in text


def test_in_ca_nam_2033_co_thang_11_nhuan(audit):
    """Bài toán 2033: bảng năm âm 2033 phải có tháng Mười Một nhuận."""
    text = audit.render_lunar_year(2033)
    assert "13 tháng" in text
    assert "có tháng 11 nhuận" in text
    assert "Tháng Mười Một (nhuận)" in text
    assert "22/12/2033" in text


# ===========================================================================
# 5. Giao diện dòng lệnh
# ===========================================================================
def test_cli_thang_duong(audit, capsys):
    """``audit_calendar.py 2026 10`` in bảng tháng 10/2026 và trả mã 0."""
    ma = audit.main(["2026", "10"])
    out = capsys.readouterr().out
    assert ma == 0
    assert "THÁNG 10 / 2026" in out
    assert len(_dong_o(out)) == 5


def test_cli_nam_am(audit, capsys):
    """``--year 2023`` in cả năm âm 2023 gồm tháng nhuận."""
    ma = audit.main(["--year", "2023"])
    out = capsys.readouterr().out
    assert ma == 0
    assert "NĂM ÂM LỊCH 2023" in out
    assert "Tháng Hai (nhuận)" in out


def test_cli_khong_tham_so_in_thang_hien_tai(audit, capsys, monkeypatch):
    """Không truyền tham số: in tháng hiện tại (theo ``calendar_service.today``)."""
    monkeypatch.setattr(audit.calendar_service, "today", lambda: __import__("datetime").date(2026, 10, 28))
    ma = audit.main([])
    out = capsys.readouterr().out
    assert ma == 0
    assert "THÁNG 10 / 2026" in out


def test_cli_engine_hnd_cho_ket_qua_khac(audit, capsys):
    """``--engine hnd`` in theo engine Hồ Ngọc Đức (21/03/2023 là mùng 1 tháng 2)."""
    ma = audit.main(["--engine", "hnd", "2023", "3"])
    out = capsys.readouterr().out
    assert ma == 0
    assert "engine: hnd" in out
    assert "21/01" in out  # HND: 21/03/2023 = mùng 1 tháng 2 (precise: 22/03)


def test_cli_engine_hnd_nam_2033_du_13_khoi_va_co_thang_11_nhuan(audit, capsys):
    """Bảng năm 2033 bằng engine HND in đủ 13 khối, có tháng Mười Một nhuận.

    Sau khi Lead sửa ``lunar_year_months``, engine HND xử lý đúng ca 2033:
    tháng 11 nhuận bắt đầu 22/12/2033, dài 29 ngày – không còn tháng 59
    ngày và không còn cảnh báo dữ liệu không nhất quán.
    """
    ma = audit.main(["--year", "2033", "--engine", "hnd"])
    out = capsys.readouterr().out
    assert ma == 0
    assert "13 tháng" in out
    assert "có tháng 11 nhuận" in out
    assert "Tháng Mười Một (nhuận)" in out
    assert "22/12/2033" in out
    assert out.count("Mùng 1:") == 13
    assert "CẢNH BÁO" not in out
    assert "29 ngày" in out  # tháng 11 nhuận dài 29 ngày như precise


@pytest.mark.parametrize(
    "argv",
    [
        ["2026", "13"],  # tháng không hợp lệ
        ["1899", "1"],  # năm ngoài phạm vi
        ["2026"],  # thiếu tháng
        ["--year", "2023", "2026", "10"],  # --year dùng chung với NĂM THÁNG
        ["--year", "1800"],  # năm âm ngoài phạm vi
    ],
    ids=["tháng-13", "năm-1899", "thiếu-tháng", "year-kèm-tháng", "năm-âm-1800"],
)
def test_cli_bao_loi_tham_so(audit, argv):
    """Tham số sai phải thoát bằng ``SystemExit`` (mã 2 của argparse)."""
    with pytest.raises(SystemExit) as loi:
        audit.main(argv)
    assert loi.value.code == 2
