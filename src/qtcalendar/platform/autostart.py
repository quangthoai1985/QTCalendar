"""Khởi động cùng Windows qua Registry (HKCU, không cần quyền admin).

Ghi giá trị chuỗi vào::

    HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
    QTCalendar = "<đường dẫn pythonw.exe>" "<...>\\run_qtcalendar.pyw"

Dùng ``pythonw.exe`` để **không hiện cửa sổ console đen** khi khởi động.

Hợp đồng API (phải giữ đúng để ``tray`` và hộp thoại cài đặt dùng)
------------------------------------------------------------------

``RUN_KEY``, ``VALUE_NAME``, ``APP_ID``
    Hằng số khoá/giá trị.

``build_command() -> str``
    Câu lệnh sẽ ghi vào Registry (có dấu nháy kép đúng chuẩn).

``is_enabled() -> bool``
    Registry đang bật (có giá trị và trỏ đúng câu lệnh hiện tại).

``enable() -> bool`` / ``disable() -> bool``
    Bật/tắt; trả ``False`` kèm ghi log khi bị chặn quyền.

``set_enabled(flag: bool) -> bool``

``read_raw() -> str | None``
    Giá trị thô đang có trong Registry (để chẩn đoán).

Không được ném ngoại lệ ra ngoài; mọi lỗi ``OSError``/``PermissionError``
trả ``False`` để ứng dụng vẫn chạy bình thường.

Ghi chú triển khai
------------------
* Không bao giờ ghi đè giá trị của ứng dụng khác: chỉ đụng đúng
  ``VALUE_NAME`` trong khoá ``RUN_KEY`` dưới ``HKEY_CURRENT_USER``.
* ``read_raw()`` trả ``None`` cho cả trường hợp khoá/giá trị chưa tồn tại
  lẫn trường hợp bị chặn quyền (khác biệt chỉ nằm trong log) – người dùng
  không bao giờ thấy ngoại lệ.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from . import IS_WINDOWS

__all__ = [
    "RUN_KEY",
    "VALUE_NAME",
    "APP_ID",
    "build_command",
    "is_enabled",
    "enable",
    "disable",
    "set_enabled",
    "read_raw",
]

log = logging.getLogger(__name__)

APP_ID = "QTCalendar"
VALUE_NAME = "QTCalendar"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

#: Tên file khởi động (nằm ở gốc dự án) – dùng ``.pyw`` để không có console.
LAUNCHER_NAME = "run_qtcalendar.pyw"

try:  # winreg chỉ có trên Windows; import mềm để module vẫn đọc được ở nơi khác
    import winreg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - chỉ đúng ngoài Windows
    winreg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Đường dẫn
# ---------------------------------------------------------------------------


def project_root() -> Path:
    """Thư mục gốc dự án (nơi có ``run_qtcalendar.pyw`` và ``src``)."""
    try:
        if getattr(sys, "frozen", False):  # pragma: no cover - khi đóng gói
            return Path(sys.executable).resolve().parent
        # src/qtcalendar/platform/autostart.py → platform → qtcalendar → src → gốc
        return Path(__file__).resolve().parents[3]
    except (OSError, IndexError, NameError):  # pragma: no cover
        return Path.cwd()


def launcher_path() -> Path:
    """Đường dẫn đầy đủ tới ``run_qtcalendar.pyw`` ở gốc dự án."""
    return project_root() / LAUNCHER_NAME


def pythonw_path() -> str:
    """Đường dẫn ``pythonw.exe`` (bản không console); fallback ``sys.executable``."""
    try:
        if getattr(sys, "frozen", False):  # pragma: no cover - khi đóng gói
            return str(Path(sys.executable).resolve())
    except OSError:
        pass
    try:
        candidate = Path(sys.executable).with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    except (OSError, ValueError):
        pass
    try:
        found = shutil.which("pythonw.exe")
        if found:
            return found
    except OSError:
        pass
    return str(sys.executable)


# ---------------------------------------------------------------------------
# Câu lệnh / chuẩn hoá
# ---------------------------------------------------------------------------


def build_command() -> str:
    """Câu lệnh ghi vào Registry, luôn có nháy kép quanh từng đường dẫn."""
    try:
        if getattr(sys, "frozen", False):  # pragma: no cover - khi đóng gói
            return f'"{pythonw_path()}"'
        return f'"{pythonw_path()}" "{launcher_path()}"'
    except Exception:
        log.warning("build_command thất bại", exc_info=True)
        return ""


def _normalise(command: str | None) -> str:
    """Chuẩn hoá để so sánh câu lệnh (Windows không phân biệt hoa/thường)."""
    try:
        return " ".join(str(command or "").split()).casefold()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Đọc / ghi Registry
# ---------------------------------------------------------------------------


def read_raw() -> str | None:
    """Giá trị thô của ``QTCalendar`` trong Run; ``None`` nếu chưa có/lỗi."""
    if not IS_WINDOWS or winreg is None:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _value_type = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return None
    except OSError as exc:  # PermissionError, khoá hỏng…
        log.warning("Không đọc được Registry HKCU Run: %s", exc)
        return None
    except Exception:  # pragma: no cover - phòng hờ
        log.warning("read_raw thất bại", exc_info=True)
        return None
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            return None
    return str(value)


def is_enabled() -> bool:
    """``True`` khi Registry có giá trị **và** trỏ đúng câu lệnh hiện tại."""
    try:
        raw = read_raw()
        if not raw:
            return False
        current = build_command()
        if not current:
            return False
        return _normalise(raw) == _normalise(current)
    except Exception:
        log.debug("is_enabled thất bại", exc_info=True)
        return False


def enable() -> bool:
    """Bật khởi động cùng Windows; trả ``False`` nếu bị chặn quyền."""
    if not IS_WINDOWS or winreg is None:
        return False
    try:
        command = build_command()
        if not command:
            log.warning("enable: không tạo được câu lệnh khởi động")
            return False
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        log.info("Đã bật khởi động cùng Windows: %s", command)
        return is_enabled()
    except OSError as exc:
        log.warning("Không bật được khởi động cùng Windows: %s", exc)
        return False
    except Exception:  # pragma: no cover - phòng hờ
        log.warning("enable thất bại", exc_info=True)
        return False


def disable() -> bool:
    """Tắt khởi động cùng Windows; ``True`` nếu chắc chắn đã không còn giá trị."""
    if not IS_WINDOWS or winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        log.info("Đã tắt khởi động cùng Windows")
        return read_raw() is None
    except FileNotFoundError:
        # Khoá hoặc giá trị vốn không tồn tại ⇒ đã tắt từ trước.
        return True
    except OSError as exc:
        log.warning("Không tắt được khởi động cùng Windows: %s", exc)
        return False
    except Exception:  # pragma: no cover - phòng hờ
        log.warning("disable thất bại", exc_info=True)
        return False


def set_enabled(flag: bool) -> bool:
    """Bật/tắt theo ``flag`` (ép kiểu mềm, không ném lỗi)."""
    try:
        return enable() if bool(flag) else disable()
    except Exception:  # pragma: no cover - phòng hờ
        log.warning("set_enabled thất bại", exc_info=True)
        return False


def _debug_state() -> dict[str, object]:
    """Thông tin chẩn đoán (dùng trong log/probe, không thuộc hợp đồng)."""
    return {
        "project_root": str(project_root()),
        "launcher": str(launcher_path()),
        "launcher_exists": launcher_path().is_file(),
        "pythonw": pythonw_path(),
        "command": build_command(),
        "raw": read_raw(),
        "enabled": is_enabled(),
    }
