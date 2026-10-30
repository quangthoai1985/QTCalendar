"""Cấu hình ứng dụng – đọc/ghi ``settings.json`` một cách an toàn.

Nguyên tắc:

* **Không bao giờ làm mất cấu hình của người dùng**: mọi giá trị hỏng được
  kẹp về khoảng hợp lệ thay vì ném lỗi; tệp JSON hỏng được sao lưu rồi
  khởi tạo lại.
* **Ghi nguyên tử**: ghi ra ``.tmp`` rồi ``os.replace`` để mất điện giữa
  chừng cũng không để lại tệp JSON cụt.
* **Hai chế độ lưu**: *portable* (``settings.json`` nằm cạnh ứng dụng) nếu
  tệp đó tồn tại, ngược lại dùng ``%LOCALAPPDATA%\\QTCalendar``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Mapping

from .. import APP_ID

__all__ = [
    "Settings",
    "ConfigStore",
    "config_path",
    "data_dir",
    "app_root",
    "PLACEMENTS",
    "QUOTE_MODES",
    "LUNAR_ENGINES",
]

SCHEMA_VERSION = 2

#: Cách neo cửa sổ vào desktop
#: * ``desktop``  – ghim làm con của Progman (sống sót Win + D)
#: * ``floating`` – cửa sổ nổi bình thường, có thể bật "luôn nổi trên cùng"
PLACEMENTS = ("desktop", "floating")

#: Cách chọn ca dao
QUOTE_MODES = ("daily", "random")

#: Engine âm lịch
LUNAR_ENGINES = ("precise", "hnd")

_MIN_OPACITY, _MAX_OPACITY = 0.20, 1.00
_MIN_W, _MAX_W = 260, 900
_MIN_H, _MAX_H = 320, 1200
_MIN_SCALE, _MAX_SCALE = 0.75, 2.00


def app_root() -> Path:
    """Thư mục gốc dự án khi chạy từ mã nguồn.

    ``core/config.py`` → ``core`` → ``qtcalendar`` → ``src`` → gốc dự án.
    Khi đóng gói bằng PyInstaller, trả về thư mục chứa file thực thi.
    """
    if getattr(sys, "frozen", False):  # pragma: no cover - chỉ đúng khi đóng gói
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """Thư mục dữ liệu người dùng.

    Ưu tiên ``%LOCALAPPDATA%\\QTCalendar``; nếu biến môi trường không có
    (hiếm), lùi về thư mục gốc dự án.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_ID
    return app_root() / ".data"


def config_path() -> Path:
    """Đường dẫn tệp cấu hình đang dùng.

    ``QTCALENDAR_CONFIG`` (biến môi trường) thắng tất cả – rất tiện cho
    kiểm thử và cho người dùng muốn ghim cấu hình ở nơi khác.
    """
    override = os.environ.get("QTCALENDAR_CONFIG")
    if override:
        return Path(override).expanduser()

    portable = app_root() / "settings.json"
    if portable.is_file():
        return portable

    return data_dir() / "settings.json"


@dataclass(slots=True)
class Settings:
    """Toàn bộ trạng thái bền vững của widget.

    Mọi trường đều có giá trị mặc định hợp lý nên ``Settings()`` luôn dựng
    được ứng dụng ở trạng thái chạy tốt.
    """

    # ---- hình học cửa sổ --------------------------------------------------
    x: int = -1  #: -1 = chưa có vị trí, ứng dụng tự chọn góc màn hình
    y: int = -1
    width: int = 344
    height: int = 468
    scale: float = 1.0  #: hệ số phóng to nội dung (0.75 – 2.0)

    # ---- hiển thị ---------------------------------------------------------
    opacity: float = 1.00
    theme: str = "giay_do"
    #: Màu nền giấy tuỳ chọn ``"#RRGGBB"``; chuỗi rỗng = dùng màu gốc của theme.
    bg_color: str = ""
    show_month: bool = False  #: hiện lịch tháng ngay dưới chân lịch bloc
    show_quote: bool = True
    show_auspicious: bool = True
    show_tiet_khi: bool = True
    quote_mode: str = "daily"  #: ``daily`` | ``random``
    #: Engine âm lịch: ``precise`` (khớp lịch vạn niên) hoặc ``hnd`` (bản gốc).
    lunar_engine: str = "precise"

    # ---- hành vi cửa sổ ---------------------------------------------------
    placement: str = "desktop"  #: ``desktop`` (ghim) | ``floating``
    always_on_top: bool = False
    lock_position: bool = False
    run_at_startup: bool = False
    hidden: bool = False

    # ---- trạng thái phụ ---------------------------------------------------
    month_anchor: str = ""  #: "YYYY-MM" của lịch tháng, "" = tháng hiện tại

    #: Phiên bản lược đồ – dùng để nâng cấp cấu hình về sau.
    schema_version: int = SCHEMA_VERSION

    # ---- tiện ích ---------------------------------------------------------

    def copy(self) -> "Settings":
        """Bản sao độc lập (hộp thoại sửa trên bản sao rồi mới lưu)."""
        return replace(self)

    def clamp(self) -> "Settings":
        """Kẹp mọi giá trị về khoảng hợp lệ, tại chỗ, rồi trả lại ``self``."""
        self.opacity = _clamp_float(self.opacity, _MIN_OPACITY, _MAX_OPACITY, 1.0)
        self.scale = _clamp_float(self.scale, _MIN_SCALE, _MAX_SCALE, 1.0)
        self.width = _clamp_int(self.width, _MIN_W, _MAX_W, 344)
        self.height = _clamp_int(self.height, _MIN_H, _MAX_H, 468)
        self.x = _clamp_int(self.x, -32000, 32000, -1)
        self.y = _clamp_int(self.y, -32000, 32000, -1)
        if self.theme not in _theme_names():
            self.theme = "giay_do"
        if not _color_valid(self.bg_color):
            self.bg_color = ""
        else:
            self.bg_color = str(self.bg_color).strip().upper()
            if not self.bg_color.startswith("#"):
                self.bg_color = "#" + self.bg_color
        if self.placement not in PLACEMENTS:
            self.placement = "desktop"
        if self.quote_mode not in QUOTE_MODES:
            self.quote_mode = "daily"
        if self.lunar_engine not in LUNAR_ENGINES:
            self.lunar_engine = "precise"
        if not self._month_anchor_valid():
            self.month_anchor = ""
        return self

    def _month_anchor_valid(self) -> bool:
        if not self.month_anchor:
            return True
        try:
            year_s, month_s = self.month_anchor.split("-", 1)
            year, month = int(year_s), int(month_s)
        except (ValueError, AttributeError):
            return False
        return 1900 <= year <= 2200 and 1 <= month <= 12

    def to_dict(self) -> dict[str, Any]:
        """Chuyển thành dict thuần để ghi JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Settings":
        """Dựng ``Settings`` từ dict bất kỳ, bỏ qua khoá lạ và kiểu sai."""
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in raw:
                continue
            coerced = _coerce(f.name, f.type, raw[f.name])
            if coerced is not None:
                kwargs[f.name] = coerced
        # Schema 1 lưu ``view = "month"`` (chế độ chỉ có lịch tháng); nay lịch
        # tháng hiện dưới chân bloc ⇒ người đang dùng lịch tháng thấy cả hai.
        if "show_month" not in raw and raw.get("view") == "month":
            kwargs["show_month"] = True
        return cls(**kwargs).clamp()

    def diff(self, other: "Settings") -> dict[str, tuple[Any, Any]]:
        """Các trường khác nhau (dùng cho log/kiểm thử)."""
        a, b = self.to_dict(), other.to_dict()
        return {k: (a[k], b[k]) for k in a if a[k] != b[k]}


def _theme_names() -> set[str]:
    # Import trễ để ``config`` không phụ thuộc cứng vào ``theme`` khi test.
    from .theme import THEMES

    return set(THEMES)


def _color_valid(value: Any) -> bool:
    """Kiểm tra chuỗi màu hex 6/8 ký tự; rỗng cũng coi là hợp lệ (theo theme)."""
    if value in (None, "", False):
        return False
    from .theme import is_valid_color

    return is_valid_color(str(value))


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


def _coerce(name: str, ftype: Any, value: Any) -> Any:
    """Ép kiểu mềm: sai kiểu thì trả ``None`` để dùng mặc định."""
    ftype_name = ftype if isinstance(ftype, str) else getattr(ftype, "__name__", "")
    try:
        if ftype_name == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "có"}
            return None
        if ftype_name == "int":
            return int(value)
        if ftype_name == "float":
            return float(value)
        if ftype_name == "str":
            return str(value) if isinstance(value, str) else None
    except (TypeError, ValueError):
        return None
    return value


class ConfigStore:
    """Đọc/ghi :class:`Settings` từ một tệp JSON."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self._path = Path(path) if path is not None else config_path()

    # ---- thông tin --------------------------------------------------------

    @property
    def path(self) -> Path:
        """Tệp cấu hình thực tế đang dùng."""
        return self._path

    @property
    def portable(self) -> bool:
        """``True`` nếu cấu hình nằm cạnh ứng dụng thay vì LOCALAPPDATA."""
        try:
            return self._path.resolve().parent == app_root().resolve()
        except OSError:  # pragma: no cover
            return False

    def exists(self) -> bool:
        return self._path.is_file()

    # ---- đọc / ghi --------------------------------------------------------

    def load(self) -> Settings:
        """Đọc cấu hình; tệp thiếu/hỏng thì trả mặc định (và sao lưu tệp hỏng)."""
        if not self._path.is_file():
            return Settings()
        try:
            text = self._path.read_text(encoding="utf-8")
            raw = json.loads(text)
        except (OSError, UnicodeDecodeError):
            return Settings()
        except json.JSONDecodeError:
            self._backup_broken()
            return Settings()
        if not isinstance(raw, dict):
            self._backup_broken()
            return Settings()
        return Settings.from_dict(raw)

    def save(self, settings: Settings) -> None:
        """Ghi cấu hình nguyên tử. Tự tạo thư mục cha nếu cần."""
        settings.schema_version = SCHEMA_VERSION
        payload = settings.to_dict()
        parent = self._path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError:  # pragma: no cover - thư mục bị khoá
            return

        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        except OSError:  # pragma: no cover - đĩa chỉ đọc
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def reset(self) -> Settings:
        """Xoá cấu hình và trả về mặc định."""
        try:
            self._path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass
        return Settings()

    # ---- nội bộ -----------------------------------------------------------

    def _backup_broken(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = self._path.with_name(f"settings.corrupt-{stamp}.json")
        try:
            self._path.replace(target)
        except OSError:  # pragma: no cover
            pass
