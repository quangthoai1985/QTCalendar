"""Kiểm thử phần "nền giấy": độ trong suốt chỉ trên nền + màu nền tuỳ chọn.

Ba nhóm hợp đồng được khoá lại:

1. ``paper_theme`` nhúng alpha vào **màu giấy** và không đụng tới màu chữ —
   chính là yêu cầu "khoá opacity của chữ, chỉ giảm độ trong suốt của nền".
2. ``with_background`` đổi màu nền và tự chọn bộ mực sáng/tối tương phản.
3. ``Settings.bg_color`` lưu/đọc đúng và tự loại bỏ màu không hợp lệ.
"""

from __future__ import annotations

import pytest

from qtcalendar.core.config import Settings
from qtcalendar.core.theme import (
    BACKGROUND_PRESETS,
    alpha_of,
    get_theme,
    is_valid_color,
    paper_theme,
    rgba,
    with_background,
)


# --------------------------------------------------------------------------- #
# 1. Độ trong suốt chỉ nằm ở nền
# --------------------------------------------------------------------------- #
def test_giu_nguyen_mau_chu_khi_giam_do_mo():
    theme = get_theme("giay_do")
    visual = paper_theme(theme, 0.6)
    # Màu chữ, nhấn, chip giữ nguyên tuyệt đối
    assert visual.ink == theme.ink
    assert visual.ink_soft == theme.ink_soft
    assert visual.accent == theme.accent
    assert visual.chip_bg == theme.chip_bg
    assert visual.chip_ink == theme.chip_ink
    assert alpha_of(visual.ink) == 1.0
    assert alpha_of(visual.chip_bg) == 1.0


def test_nen_co_alpha_dung_bang_do_mo():
    theme = get_theme("giay_do")
    for opacity in (0.2, 0.3, 0.5, 0.6, 0.85, 1.0):
        visual = paper_theme(theme, opacity)
        assert alpha_of(visual.paper) == pytest.approx(opacity, abs=1 / 255)
        assert alpha_of(visual.paper_2) == pytest.approx(opacity, abs=1 / 255)


def test_do_mo_1_thi_giu_nguyen_theme_goc():
    theme = get_theme("xanh_ngoc")
    assert paper_theme(theme, 1.0) == theme


def test_do_mo_ngoai_khoang_bi_kep():
    theme = get_theme("giay_do")
    assert alpha_of(paper_theme(theme, 0.0).paper) == pytest.approx(0.0, abs=1 / 255)
    assert alpha_of(paper_theme(theme, 3.0).paper) == pytest.approx(1.0, abs=1 / 255)


def test_mep_giay_dam_hon_nen_de_thay_duong_bao():
    visual = paper_theme(get_theme("giay_do"), 0.3)
    assert alpha_of(visual.paper_edge) > alpha_of(visual.paper)


# --------------------------------------------------------------------------- #
# 2. Màu nền tuỳ chọn
# --------------------------------------------------------------------------- #
def test_mau_nen_sang_giu_muc_toi():
    theme = get_theme("giay_do")
    visual = with_background(theme, "#EAF4EE")
    assert visual.paper.upper() == "#EAF4EE"
    assert visual.ink == theme.ink
    assert visual.dark is False


def test_mau_nen_toi_tu_doi_muc_sang():
    visual = with_background(get_theme("giay_do"), "#141A22")
    assert visual.paper.upper() == "#141A22"
    assert visual.dark is True
    # mực sáng để chữ vẫn đọc được trên nền tối
    from qtcalendar.core.theme import _luminance  # noqa: PLC0415

    assert _luminance(visual.ink) > 0.5


def test_mau_nen_khong_hop_le_thi_giu_nguyen():
    theme = get_theme("hoang_hon")
    assert with_background(theme, "") == theme
    assert with_background(theme, "khong-phai-mau") == theme
    assert with_background(theme, "#12") == theme


def test_paper_theme_ap_ca_mau_nen_lan_do_mo():
    visual = paper_theme(get_theme("giay_do"), 0.5, "#EAF4EE")
    assert alpha_of(visual.paper) == pytest.approx(0.5, abs=1 / 255)
    assert visual.paper.upper().endswith("EAF4EE")


def test_rgba_nhan_them_alpha_san_co():
    # màu đã có alpha 0.6, xin alpha 0.5 ⇒ còn 0.3
    assert "0.300" in rgba(paper_theme(get_theme("giay_do"), 0.6).paper, 0.5)


def test_danh_sach_mau_goi_y_deu_hop_le():
    assert len(BACKGROUND_PRESETS) >= 6
    for name, color in BACKGROUND_PRESETS:
        assert name and is_valid_color(color), f"màu gợi ý sai: {name} {color}"


# --------------------------------------------------------------------------- #
# 3. Cấu hình
# --------------------------------------------------------------------------- #
def test_mac_dinh_bg_color_rong():
    assert Settings().bg_color == ""


def test_luu_va_doc_lai_bg_color():
    s = Settings()
    s.bg_color = "#eaf4ee"
    s.clamp()
    assert s.bg_color == "#EAF4EE"
    assert Settings.from_dict(s.to_dict()).bg_color == "#EAF4EE"


def test_bg_color_sai_bi_loai():
    for bad in ("abc", "#12345", "đỏ", 123, None):
        s = Settings.from_dict({"bg_color": bad})
        assert s.bg_color == ""


def test_bg_color_khong_anh_huong_theme():
    s = Settings.from_dict({"theme": "dem_sao", "bg_color": "#EAF4EE"})
    s.clamp()
    assert s.theme == "dem_sao"
    assert s.bg_color == "#EAF4EE"
