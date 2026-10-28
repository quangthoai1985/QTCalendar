"""Tầng nền tảng Windows.

Ba nhóm chức năng, mỗi nhóm một module:

``win32``
    Khai báo ``ctypes`` cho ``user32`` / ``shell32`` / ``kernel32`` và các hàm
    tiện ích (lấy HWND từ QWidget, đọc/ghi style, EnumWindows…).

``desktop_pin``
    Ghim cửa sổ xuống mặt bàn Desktop bằng ``SetParent(hwnd, Progman)`` – nhờ
    vậy cửa sổ sống sót qua ``Win + D`` và không chiếm chỗ trong Alt+Tab.

``autostart``
    Bật/tắt khởi động cùng Windows qua khoá Registry
    ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``.

``tray``
    Icon khay hệ thống (module duy nhất của tầng này dùng Qt).

Toàn bộ module phải **an toàn trên mọi máy**: mọi lời gọi Win32 được bọc
``try/except`` và trả về ``False``/``None`` khi thất bại, không bao giờ ném
lỗi làm sập ứng dụng.
"""

from __future__ import annotations

import sys

__all__ = ["IS_WINDOWS"]

#: ``True`` khi chạy trên Windows (các module khác dựa vào cờ này để no-op).
IS_WINDOWS: bool = sys.platform == "win32"
