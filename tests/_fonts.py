"""Nạp font hệ thống Windows cho test chạy QPA ``offscreen``.

QPA ``offscreen`` không đọc font hệ thống (``QFontDatabase.families()`` rỗng),
nên test cần đo chữ thật phải tự tìm file font trong Registry rồi nạp vào.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFontDatabase

_FONTS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"


def load_family(family: str) -> None:
    """Nạp mọi file font của ``family`` đăng ký trong Registry (chỉ Windows)."""
    if family in QFontDatabase.families():
        return
    import winreg

    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _FONTS_KEY) as key:
        index = 0
        while True:
            try:
                name, value, _kind = winreg.EnumValue(key, index)
            except OSError:
                break
            index += 1
            if name.split(" (")[0].split(" & ")[0].startswith(family):
                path = Path(value) if Path(value).is_absolute() else fonts_dir / value
                if path.is_file():
                    QFontDatabase.addApplicationFont(str(path))
