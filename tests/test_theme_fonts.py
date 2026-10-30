"""Kiểm thử font của theme vẽ đủ chữ tiếng Việt.

Font thiếu glyph (ví dụ Georgia không có ơ, ư, ạ, ố…) khiến Qt mượn từng ký
tự của font khác: dấu lệch, nét chữ lẫn lộn, khoảng cách sai. Vì vậy mọi font
khai báo trong ``Theme`` phải có **toàn bộ** chữ cái tiếng Việt có dấu, cả
dáng thường lẫn nghiêng.

QPA ``offscreen`` không đọc font hệ thống, nên test nạp font qua
:func:`_fonts.load_family`.
"""

from __future__ import annotations

import os
import sys
import unicodedata

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QRawFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from _fonts import load_family  # noqa: E402
from qtcalendar.core.theme import THEMES  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="font hệ thống Windows"
)


def _vietnamese_letters() -> list[str]:
    """134 chữ cái tiếng Việt không thuộc ASCII (thường + hoa)."""
    letters = set("đĐ")
    for base in "aăâeêioôơuưy" + "AĂÂEÊIOÔƠUƯY":
        for mark in ("", "\u0300", "\u0301", "\u0303", "\u0309", "\u0323"):
            letters.add(unicodedata.normalize("NFC", base + mark))
    return sorted(c for c in letters if not c.isascii())


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
        load_family(family)
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
