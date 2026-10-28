"""Sinh icon ứng dụng (PNG + ICO) bằng Pillow.

Chạy::

    python -X utf8 scripts/make_icon.py

Kết quả: ``assets/icon.png`` (256×256) và ``assets/icon.ico`` (đa kích thước).
Icon mô phỏng một tờ lịch bloc: giấy ngà, dải gáy đỏ, số ngày lớn.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

#: Màu lấy đúng theo theme "Giấy đỏ" trong qtcalendar/core/theme.py
PAPER = (255, 253, 246, 255)
PAPER_EDGE = (231, 217, 191, 255)
RED = (179, 35, 31, 255)
INK = (42, 33, 27, 255)
INK_SOFT = (107, 89, 70, 255)

_WIN_FONTS = Path(r"C:\Windows\Fonts")


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in candidates:
        path = _WIN_FONTS / name
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def render(size: int = 256) -> Image.Image:
    """Vẽ icon kích thước ``size`` (thiết kế gốc ở 256 rồi scale)."""
    scale = size / 256.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(v: float) -> float:
        return v * scale

    # ---- bóng đổ nhẹ phía sau ------------------------------------------
    for i, alpha in ((6, 18), (4, 26), (2, 34)):
        draw.rounded_rectangle(
            [s(14 - i), s(8 - i), s(242 + i), s(250 + i)],
            radius=s(28 + i),
            fill=(70, 40, 25, alpha),
        )

    # ---- tờ giấy --------------------------------------------------------
    draw.rounded_rectangle(
        [s(16), s(8), s(240), s(248)],
        radius=s(28),
        fill=PAPER,
        outline=PAPER_EDGE,
        width=max(1, int(s(2))),
    )

    # ---- dải gáy đỏ -----------------------------------------------------
    band_bottom = s(72)
    draw.rounded_rectangle(
        [s(16), s(8), s(240), band_bottom + s(26)],
        radius=s(28),
        fill=RED,
    )
    draw.rectangle([s(16), band_bottom - s(8), s(240), band_bottom + s(24)], fill=RED)

    # ---- lỗ đục gáy -----------------------------------------------------
    hole_font_pad = s(16)
    for cx in (s(72), s(128), s(184)):
        draw.ellipse(
            [cx - s(6), s(20), cx + s(6), s(32)],
            fill=PAPER,
        )

    # ---- chữ THỨ --------------------------------------------------------
    f_week = _font(["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"], int(s(30)))
    text = "THỨ 4"
    box = draw.textbbox((0, 0), text, font=f_week)
    tw = box[2] - box[0]
    draw.text((s(128) - tw / 2, s(38)), text, font=f_week, fill=PAPER)

    # ---- số ngày --------------------------------------------------------
    f_day = _font(["seguibl.ttf", "segoeuib.ttf", "arialbd.ttf"], int(s(112)))
    day_text = "28"
    box = draw.textbbox((0, 0), day_text, font=f_day)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text(
        (s(128) - tw / 2 - box[0] * 0, s(108) - box[1]),
        day_text,
        font=f_day,
        fill=RED,
    )

    # ---- dòng âm lịch ---------------------------------------------------
    f_lunar = _font(["segoeuib.ttf", "arialbd.ttf"], int(s(24)))
    lunar_text = "19/9"
    box = draw.textbbox((0, 0), lunar_text, font=f_lunar)
    tw = box[2] - box[0]
    draw.text((s(128) - tw / 2, s(216)), lunar_text, font=f_lunar, fill=INK_SOFT)

    # ---- đường kẻ mảnh --------------------------------------------------
    draw.line([s(48), s(200), s(208), s(200)], fill=PAPER_EDGE, width=max(1, int(s(2))))

    return img


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    big = render(256)
    png = ASSETS / "icon.png"
    big.save(png, "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [render(sz) for sz in sizes]
    ico = ASSETS / "icon.ico"
    frames[-1].save(ico, format="ICO", sizes=[(sz, sz) for sz in sizes])
    print(f"OK {png} ({png.stat().st_size} B)")
    print(f"OK {ico} ({ico.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
