#!python3.14
"""Trình khởi chạy QT Calendar (không hiện cửa sổ console).

Chạy trực tiếp bằng:
    Double-click vào tệp này
    hoặc: py -3.14 run_qtcalendar.pyw
    hoặc: pythonw run_qtcalendar.pyw
"""

from __future__ import annotations

import sys
from pathlib import Path

# Đảm bảo in tiếng Việt chuẩn trong console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def _show_fatal_error(title: str, message: str) -> None:
    """Hiển thị hộp thoại lỗi Windows nếu không thể khởi động app."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        print(f"[{title}] {message}", file=sys.stderr)

try:
    from qtcalendar.app import main
except ModuleNotFoundError as e:
    _show_fatal_error(
        "QT Calendar - Lỗi thiếu thư viện",
        f"Không thể khởi động ứng dụng do thiếu thư viện: {e}.\n\n"
        f"Python đang chạy: {sys.executable} (phiên bản {sys.version.split()[0]})\n\n"
        f"Gợi ý: Hãy cài đặt thư viện bằng lệnh:\n"
        f"pip install -r requirements.txt\n"
        f"hoặc chạy bằng Python 3.14: py -3.14 run_qtcalendar.pyw",
    )
    sys.exit(1)
except Exception as e:
    _show_fatal_error(
        "QT Calendar - Lỗi khởi động",
        f"Đã xảy ra lỗi khi khởi động QT Calendar:\n{e}",
    )
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
