"""QT Calendar – lịch bloc Dương – Âm thuần Việt cho Windows.

Gói này được thiết kế theo 4 tầng tách biệt:

    core/      – logic thuần (âm lịch, can chi, ca dao, cấu hình)  -> không import Qt
    platform/  – tầng Win32 (ghim desktop, khay hệ thống, khởi động cùng Windows)
    ui/        – giao diện PySide6 (cửa sổ widget, lịch bloc, lịch tháng)
    app.py     – bộ điều phối, nối các tầng lại với nhau

Chỉ tầng ``ui`` và ``app`` được phép import Qt.
"""

from __future__ import annotations

__all__ = ["__version__", "APP_NAME", "APP_ID"]

__version__ = "1.0.0"

#: Tên hiển thị (taskbar, khay hệ thống, hộp thoại).
APP_NAME = "QT Calendar"

#: Khoá định danh dùng cho Registry, thư mục cấu hình, mutex...
APP_ID = "QTCalendar"
