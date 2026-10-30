"""Kiểm thử font của theme vẽ đủ chữ tiếng Việt.

Font thiếu glyph (ví dụ Georgia không có ơ, ư, ạ, ố…) khiến Qt mượn từng ký
tự của font khác: dấu lệch, nét chữ lẫn lộn, khoảng cách sai. Vì vậy mọi font
khai báo trong ``Theme`` phải có **toàn bộ** chữ cái tiếng Việt có dấu, cả
dáng thường lẫn nghiêng.

QPA ``offscreen`` không đọc font hệ thống, nên test tự tìm file font trong
Registry của Windows rồi nạp vào ``QFontDatabase``.
"""

from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase, QRawFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qtcalendar.core.theme import THEMES  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="font hệ thống Windows"
)

_FONTS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"


def _vietnamese_letters() -> list[str]:
    """134 chữ cái tiếng Việt không thuộc ASCII (thường + hoa)."""
    letters = set("đĐ")
    for base in "aăâeêioôơuưy" + "AĂÂEÊIOÔƠUƯY":
        for mark in ("", "\u0300", "\u0301", "\u0303", "\u0309", "\u0323"):
            letters.add(unicodedata.normalize("NFC", base + mark))
    return sorted(c for c in letters if not c.isascii())


def _load_family(family: str) -> None:
    """Nạp mọi file font của ``family`` đăng ký trong Registry."""
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


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("italic", [False, True], ids=["thuong", "nghieng"])
@pytest.mark.parametrize("role", ["font_ui", "font_quote"])
def test_font_theme_du_chu_tieng_viet(qapp, role, italic):
    letters = _vietnamese_letters()
    for theme in THEMES.values():
        family = getattr(theme, role)
        if family not in QFontDatabase.families():
            _load_family(family)
        font = QFont(family)
        font.setPixelSize(12)
        font.setItalic(italic)
        raw = QRawFont.fromFont(font)
        assert raw.familyName() == family, f"{theme.name}.{role}: không có font {family!r}"
        missing = "".join(c for c in letters if not raw.supportsCharacter(ord(c)))
        assert not missing, (
            f"{theme.name}.{role} = {family!r} thiếu {len(missing)}/{len(letters)} "
            f"chữ tiếng Việt: {missing}"
        )
