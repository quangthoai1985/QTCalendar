"""Kiểm chứng tầng cấu hình (``core/config.py``).

Các yêu cầu được kiểm tra:

* Không bao giờ làm mất cấu hình: tệp JSON hỏng được sao lưu rồi trả mặc
  định; mọi giá trị rác/quá biên đều được kẹp về khoảng hợp lệ.
* Ghi **nguyên tử**: không để lại tệp ``.tmp``, và nếu bước thay thế tệp
  thất bại thì bản cũ vẫn còn nguyên.
* Chế độ *portable*: ``ConfigStore`` nhận ra tệp cấu hình nằm cạnh ứng dụng.
* ``Settings.from_dict`` chịu được dữ liệu rác, khoá lạ, sai kiểu.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from qtcalendar import APP_ID
from qtcalendar.core import config
from qtcalendar.core.config import (
    PLACEMENTS,
    QUOTE_MODES,
    SCHEMA_VERSION,
    ConfigStore,
    Settings,
)
from qtcalendar.core.theme import THEMES


# ===========================================================================
# 1. Giá trị mặc định
# ===========================================================================
def test_gia_tri_mac_dinh_hop_le_va_serializable():
    """``Settings()`` phải dựng được ngay và chuyển thành JSON không lỗi."""
    s = Settings()
    assert s.show_month is False
    assert s.placement in PLACEMENTS
    assert s.quote_mode in QUOTE_MODES
    assert s.theme in THEMES
    assert s.schema_version == SCHEMA_VERSION
    raw = s.to_dict()
    assert isinstance(raw, dict)
    assert set(raw) == {f.name for f in fields(Settings)}
    # JSON hoá được (chuỗi tiếng Việt không được làm vỡ).
    assert json.loads(json.dumps(raw, ensure_ascii=False))["theme"] == "giay_do"


# ===========================================================================
# 2. Kẹp giá trị về khoảng hợp lệ
# ===========================================================================
@pytest.mark.parametrize(
    "truong,gia_tri_rac,ky_vong",
    [
        ("opacity", -5.0, 0.20),  # nhỏ hơn biên dưới
        ("opacity", 99.0, 1.00),  # lớn hơn biên trên
        ("opacity", "không phải số", 1.00),  # sai kiểu -> mặc định
        ("scale", 0.10, 0.75),
        ("scale", 9.0, 2.00),
        ("width", 10, 260),
        ("width", 99999, 900),
        ("height", 0, 320),
        ("height", 99999, 1200),
        ("x", -999999, -32000),
        ("y", 999999, 32000),
    ],
)
def test_kep_gia_tri_so_ve_khoang_hop_le(truong: str, gia_tri_rac: object, ky_vong: object):
    """Mọi giá trị số phải được kẹp về đúng khoảng biên của ứng dụng."""
    s = Settings(**{truong: gia_tri_rac})
    s.clamp()
    assert getattr(s, truong) == ky_vong


@pytest.mark.parametrize(
    "truong,gia_tri,ky_vong",
    [
        ("theme", "theme_khong_ton_tai", "giay_do"),
        ("placement", "khong_co", "desktop"),
        ("quote_mode", "khong_co", "daily"),
    ],
)
def test_kep_gia_tri_chuoi_ve_mac_dinh(truong: str, gia_tri: str, ky_vong: str):
    """Giá trị không nằm trong danh sách cho phép phải quay về mặc định."""
    s = Settings(**{truong: gia_tri})
    s.clamp()
    assert getattr(s, truong) == ky_vong


@pytest.mark.parametrize("theme", list(THEMES))
def test_kep_khong_lam_mat_theme_hop_le(theme: str):
    """Theme hợp lệ phải được giữ nguyên sau khi kẹp."""
    s = Settings(theme=theme, width=500, opacity=0.75)
    s.clamp()
    assert s.theme == theme
    assert s.width == 500
    assert s.opacity == 0.75


@pytest.mark.parametrize(
    "anchor,hop_le",
    [
        ("", True),
        ("2026-10", True),
        ("1900-01", True),
        ("2200-12", True),
        ("2026-13", False),
        ("2026-00", False),
        ("2026", False),
        ("18xx-01", False),
        ("1800-01", False),
        ("2210-01", False),
        ("2026-10-25", False),
    ],
)
def test_kiem_tra_month_anchor(anchor: str, hop_le: bool):
    """``month_anchor`` phải có dạng ``YYYY-MM`` trong khoảng 1900–2200."""
    s = Settings(month_anchor=anchor)
    s.clamp()
    assert s.month_anchor == (anchor if hop_le else "")


# ===========================================================================
# 3. Đọc / ghi tệp
# ===========================================================================
def test_luu_va_doc_lai_nguyen_ven(tmp_config_dir: Path):
    """Ghi rồi đọc lại phải trả đúng từng trường đã lưu."""
    tep = tmp_config_dir / "settings.json"
    store = ConfigStore(tep)
    assert not store.exists()
    goc = Settings(
        x=120,
        y=240,
        width=500,
        height=700,
        scale=1.25,
        opacity=0.8,
        theme="dem_sao",
        show_month=True,
        show_quote=False,
        quote_mode="random",
        placement="floating",
        always_on_top=True,
        month_anchor="2026-10",
    )
    store.save(goc)
    assert tep.is_file()
    doc_lai = store.load()
    assert doc_lai == goc
    assert doc_lai.to_dict() == goc.to_dict()


def test_save_ghi_schema_version_va_json_de_doc(tmp_config_dir: Path):
    """``save`` luôn ghi schema_version hiện tại, JSON có thứ tự khoá ổn định."""
    tep = tmp_config_dir / "settings.json"
    store = ConfigStore(tep)
    s = Settings()
    s.schema_version = 999  # giá trị cũ/lạ phải bị ghi đè
    store.save(s)
    raw = json.loads(tep.read_text(encoding="utf-8"))
    assert raw["schema_version"] == SCHEMA_VERSION
    # Khoá được sắp xếp để diff cấu hình ổn định giữa các lần ghi.
    assert list(raw) == sorted(raw)


def test_ghi_nguyen_tu_khong_de_lai_tep_tmp(tmp_config_dir: Path):
    """Sau khi ghi thành công không còn tệp ``*.tmp`` nào."""
    tep = tmp_config_dir / "settings.json"
    ConfigStore(tep).save(Settings(width=400))
    assert tep.is_file()
    assert list(tmp_config_dir.glob("*.tmp")) == []


def test_ghi_nguyen_tu_giu_ban_cu_khi_thay_the_that_bai(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Nếu ``os.replace`` thất bại, tệp cũ phải còn nguyên và không có rác."""
    tep = tmp_config_dir / "settings.json"
    store = ConfigStore(tep)
    store.save(Settings(width=400))
    noi_dung_cu = tep.read_text(encoding="utf-8")

    def hong(*_args, **_kwargs):
        raise OSError("ổ đĩa bị lỗi khi thay thế tệp")

    monkeypatch.setattr(config.os, "replace", hong)
    store.save(Settings(width=800))  # không được ném ngoại lệ
    assert tep.read_text(encoding="utf-8") == noi_dung_cu
    assert list(tmp_config_dir.glob("*.tmp")) == []


def test_doc_tep_json_hong_thi_sao_luu_va_tra_mac_dinh(tmp_config_dir: Path):
    """JSON hỏng: sao lưu tệp hỏng, trả mặc định, không ném lỗi."""
    tep = tmp_config_dir / "settings.json"
    tep.write_text("{ đây không phải JSON", encoding="utf-8")
    store = ConfigStore(tep)
    assert store.load() == Settings()
    assert not tep.exists(), "tệp hỏng phải được chuyển thành bản sao lưu"
    ban_sao = list(tmp_config_dir.glob("settings.corrupt-*.json"))
    assert len(ban_sao) == 1
    assert "đây không phải JSON" in ban_sao[0].read_text(encoding="utf-8")


def test_doc_json_khong_phai_object_thi_sao_luu(tmp_config_dir: Path):
    """JSON hợp lệ nhưng không phải object (ví dụ mảng) cũng bị coi là hỏng."""
    tep = tmp_config_dir / "settings.json"
    tep.write_text("[1, 2, 3]", encoding="utf-8")
    store = ConfigStore(tep)
    assert store.load() == Settings()
    assert len(list(tmp_config_dir.glob("settings.corrupt-*.json"))) == 1


def test_doc_tep_khong_ton_tai_tra_mac_dinh_va_khong_tao_tep(tmp_config_dir: Path):
    """Chưa có cấu hình thì trả mặc định, tuyệt đối không tự tạo tệp."""
    tep = tmp_config_dir / "chua-co.json"
    store = ConfigStore(tep)
    assert store.load() == Settings()
    assert not tep.exists()


def test_bo_qua_khoa_la_va_gia_tri_sai_kieu(tmp_config_dir: Path):
    """Cấu hình có khoá lạ/giá trị sai kiểu vẫn đọc được, phần đúng được giữ."""
    tep = tmp_config_dir / "settings.json"
    tep.write_text(
        json.dumps(
            {
                "width": "500",  # chuỗi số -> ép được
                "theme": "xanh_ngoc",
                "view": "month",
                "khoa_la": {"a": 1},
                "height": None,
                "opacity": "khong-phai-so",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    s = ConfigStore(tep).load()
    assert s.width == 500
    assert s.theme == "xanh_ngoc"
    assert s.show_month is True  # khoá view cũ được chuyển đổi
    assert s.height == 468  # mặc định
    assert s.opacity == 1.0  # mặc định


def test_reset_xoa_cau_hinh(tmp_config_dir: Path):
    """``reset`` xoá tệp và trả về mặc định."""
    tep = tmp_config_dir / "settings.json"
    store = ConfigStore(tep)
    store.save(Settings(width=500))
    assert tep.is_file()
    assert store.reset() == Settings()
    assert not tep.exists()


# ===========================================================================
# 4. from_dict chịu dữ liệu rác
# ===========================================================================
def test_from_dict_voi_du_lieu_rac_khong_no_ra():
    """Mọi trường rác phải quay về mặc định thay vì làm sập ứng dụng."""
    rac = {
        "width": "abc",
        "height": None,
        "opacity": float("nan"),
        "scale": 2.5,
        "theme": 123,
        "view": ["bloc"],
        "show_quote": 0,
        "x": 1.9,
        "month_anchor": "2023-02",
        "khoa_khong_ton_tai": True,
    }
    s = Settings.from_dict(rac)
    assert s.width == 344  # mặc định
    assert s.height == 468  # mặc định
    assert s.opacity == 1.0  # NaN -> mặc định
    assert s.scale == 2.0  # kẹp biên trên
    assert s.theme == "giay_do"
    assert s.show_month is False
    assert s.show_quote is False  # 0 -> False
    assert s.x == 1  # float -> int
    assert s.month_anchor == "2023-02"


def test_from_dict_dict_rong_la_mac_dinh():
    """Dict rỗng phải bằng đúng ``Settings()``."""
    assert Settings.from_dict({}) == Settings()


@pytest.mark.parametrize(
    "gia_tri,ky_vong",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("Có", True),
        ("on", True),
        ("không", False),
        ("", False),
        (None, False),  # sai kiểu -> mặc định của trường (False? xem ghi chú)
    ],
)
def test_from_dict_ep_kieu_bool_linh_hoat(gia_tri: object, ky_vong: bool):
    """Trường bool nhận cả bool, số và chuỗi tiếng Việt/Anh."""
    s = Settings.from_dict({"run_at_startup": gia_tri})
    if gia_tri is None:
        # ``_coerce`` trả None -> không truyền vào -> dùng mặc định (False).
        assert s.run_at_startup is False
    else:
        assert s.run_at_startup is ky_vong


# ===========================================================================
# 5. Vị trí tệp cấu hình và chế độ portable
# ===========================================================================
def test_config_path_uu_tien_bien_moi_truong(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """``QTCALENDAR_CONFIG`` thắng mọi lựa chọn khác (tiện cho kiểm thử)."""
    tep = tmp_config_dir / "rieng.json"
    monkeypatch.setenv("QTCALENDAR_CONFIG", str(tep))
    assert config.config_path() == tep
    monkeypatch.delenv("QTCALENDAR_CONFIG")
    # Không đặt biến môi trường thì rơi về thư mục dữ liệu người dùng.
    duong_dan = config.config_path()
    assert duong_dan.name == "settings.json"
    assert duong_dan.parent in (config.data_dir(), config.app_root())


def test_data_dir_theo_bien_moi_truong(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Thư mục dữ liệu: ưu tiên LOCALAPPDATA, kế đến XDG_DATA_HOME, cuối cùng là app_root."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_config_dir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert config.data_dir() == tmp_config_dir / APP_ID

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_config_dir / "xdg"))
    assert config.data_dir() == tmp_config_dir / "xdg" / APP_ID

    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert config.data_dir() == config.app_root() / ".data"


def test_app_root_la_thu_muc_goc_du_an():
    """Khi chạy từ mã nguồn, ``app_root()`` là thư mục chứa ``src/``."""
    goc = config.app_root()
    assert (goc / "src" / "qtcalendar").is_dir()
    assert (goc / "src" / "qtcalendar" / "core" / "config.py").is_file()


def test_configstore_portable_nhan_dien_dung(tmp_config_dir: Path):
    """Tệp cạnh ứng dụng là portable; tệp ở nơi khác thì không."""
    assert ConfigStore(config.app_root() / "settings.json").portable is True
    assert ConfigStore(tmp_config_dir / "settings.json").portable is False


# ===========================================================================
# 6. Tiện ích của Settings
# ===========================================================================
def test_copy_la_ban_sao_doc_lap():
    """Sửa bản copy không được ảnh hưởng bản gốc (dialog sửa trên bản copy)."""
    goc = Settings(width=344)
    ban_sao = goc.copy()
    assert ban_sao == goc
    ban_sao.width = 500
    assert goc.width == 344
    assert ban_sao.width == 500


def test_diff_liet_ke_dung_truong_khac():
    """``diff`` chỉ liệt kê các trường thực sự khác nhau."""
    a = Settings()
    b = Settings(width=500, theme="dem_sao")
    khac = a.diff(b)
    assert set(khac) == {"width", "theme"}
    assert khac["width"] == (344, 500)
    assert a.diff(a) == {}


# ===========================================================================
# Lịch tháng dưới chân bloc: show_month thay cho view (schema 2)
# ===========================================================================
@pytest.mark.parametrize(
    "raw,ky_vong",
    [
        ({"view": "month"}, True),
        ({"view": "bloc"}, False),
        ({}, False),
        ({"view": "month", "show_month": False}, False),
        ({"view": "bloc", "show_month": True}, True),
        ({"show_month": "khong-phai-bool"}, False),
    ],
)
def test_chuyen_doi_view_cu_sang_show_month(raw: dict, ky_vong: bool):
    assert Settings.from_dict(raw).show_month is ky_vong


def test_khong_con_ghi_khoa_view_va_schema_2():
    raw = Settings().to_dict()
    assert "view" not in raw
    assert raw["show_month"] is False
    assert raw["schema_version"] == 2 == SCHEMA_VERSION
