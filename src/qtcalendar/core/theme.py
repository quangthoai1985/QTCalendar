"""Bộ "design token" cho giao diện.

Mọi màu sắc, bo góc, font chữ đều nằm ở đây để ``ui/styles.py`` chỉ việc
sinh QSS còn hai view chỉ việc vẽ. Nhờ vậy đổi giao diện = đổi một dict.

Quy ước tên trường:

======  ==================================================================
paper   màu giấy nền (đỉnh của gradient)
paper_2 màu giấy phía dưới (đáy của gradient) – tạo cảm giác giấy có thớ
ink     màu chữ chính (ngày dương lịch)
accent  màu nhấn thương hiệu (đỏ lịch bloc)
accent_2 màu phụ (vàng đồng) dùng cho chi tiết trang trí
======  ==================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = [
    "Theme",
    "THEMES",
    "THEME_ORDER",
    "DEFAULT_THEME",
    "BACKGROUND_PRESETS",
    "get_theme",
    "rgba",
    "with_background",
    "paper_theme",
    "is_valid_color",
]


def _parse_rgb(color: str) -> tuple[int, int, int]:
    """Tách ``"#RRGGBB"``/``"#AARRGGBB"`` thành ``(r, g, b)``."""
    h = str(color or "").strip().lstrip("#")
    if len(h) == 8:  # Qt dùng alpha ở đầu: #AARRGGBB
        h = h[2:]
    if len(h) != 6:
        raise ValueError(f"Màu không hợp lệ: {color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def alpha_of(color: str) -> float:
    """Độ mờ hiện có của một màu (1.0 nếu màu không kèm alpha)."""
    h = str(color or "").strip().lstrip("#")
    if len(h) == 8:
        return int(h[0:2], 16) / 255.0
    return 1.0


def _hex(r: int, g: int, b: int) -> str:
    clamp = lambda v: max(0, min(255, int(round(v))))  # noqa: E731
    return f"#{clamp(r):02X}{clamp(g):02X}{clamp(b):02X}"


def _mix(color: str, other: str, t: float) -> str:
    """Trộn ``color`` về phía ``other`` theo tỉ lệ ``t`` (0..1)."""
    r1, g1, b1 = _parse_rgb(color)
    r2, g2, b2 = _parse_rgb(other)
    return _hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def _luminance(color: str) -> float:
    """Độ sáng tương đối (WCAG) của một màu."""
    def channel(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _parse_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def is_valid_color(color: str) -> bool:
    """``True`` nếu chuỗi là màu hex 6 hoặc 8 ký tự."""
    try:
        _parse_rgb(color)
        return True
    except (ValueError, TypeError):
        return False


def _with_alpha(color: str, alpha: float) -> str:
    """Gắn alpha vào màu -> ``"#AARRGGBB"`` (định dạng QColor/QSS hiểu)."""
    r, g, b = _parse_rgb(color)
    a = max(0, min(255, int(round(max(0.0, min(1.0, alpha)) * 255))))
    return f"#{a:02X}{r:02X}{g:02X}{b:02X}"


def rgba(hex_color: str, alpha: float) -> str:
    """Đổi màu hex + độ mờ thành chuỗi QSS ``"rgba(r, g, b, a)"``.

    Nếu ``hex_color`` đã có alpha sẵn thì hai alpha được **nhân** với nhau để
    nền trong suốt vẫn giữ đúng độ mờ tương đối của từng chi tiết.
    """
    r, g, b = _parse_rgb(hex_color)
    final = max(0.0, min(1.0, alpha * alpha_of(hex_color)))
    return f"rgba({r}, {g}, {b}, {final:.3f})"


@dataclass(frozen=True, slots=True)
class Theme:
    """Một bảng màu hoàn chỉnh cho widget."""

    name: str
    display_name: str
    dark: bool

    # ---- nền giấy ---------------------------------------------------------
    paper: str
    paper_2: str
    paper_edge: str
    shadow: str

    # ---- chữ --------------------------------------------------------------
    ink: str
    ink_soft: str
    ink_faint: str
    weekend_ink: str

    # ---- nhấn -------------------------------------------------------------
    accent: str
    accent_2: str
    accent_ink: str
    line: str

    # ---- thành phần nhỏ ---------------------------------------------------
    chip_bg: str
    chip_ink: str
    quote_ink: str
    today_bg: str
    today_ink: str
    hover_bg: str

    # ---- hình khối / chữ --------------------------------------------------
    radius: int = 14
    font_ui: str = "Segoe UI"
    font_display: str = "Segoe UI Black"
    # Georgia thiếu ơ, ư, ạ, ố… → Qt mượn glyph font khác, dấu lệch, chữ dính.
    font_quote: str = "Palatino Linotype"

    @property
    def is_dark(self) -> bool:
        return self.dark


#: Bảng màu 1 – "Giấy đỏ": giấy trắng ngà, mực nâu đen, đỏ lịch bloc cổ điển.
_GIay_DO = Theme(
    name="giay_do",
    display_name="Giấy đỏ",
    dark=False,
    paper="#FFFDF6",
    paper_2="#F7EFDD",
    paper_edge="#E7D9BF",
    shadow="rgba(60, 34, 20, 0.28)",
    ink="#2A211B",
    ink_soft="#6B5946",
    ink_faint="#B9A98F",
    weekend_ink="#B3231F",
    accent="#B3231F",
    accent_2="#C79A3B",
    accent_ink="#FFFFFF",
    line="#E3D3B6",
    chip_bg="#F3E6CE",
    chip_ink="#7A5B2E",
    quote_ink="#6F5A3C",
    today_bg="#B3231F",
    today_ink="#FFFFFF",
    hover_bg="#F5E9D2",
)

#: Bảng màu 2 – "Xanh ngọc": giấy xanh nhạt, mực xanh rêu, nhấn ngọc bích.
_XANH_NGOC = Theme(
    name="xanh_ngoc",
    display_name="Xanh ngọc",
    dark=False,
    paper="#F7FCF9",
    paper_2="#E4F2EA",
    paper_edge="#C9E0D3",
    shadow="rgba(16, 58, 44, 0.26)",
    ink="#12332A",
    ink_soft="#4C6F62",
    ink_faint="#9DBCAD",
    weekend_ink="#0B7A5F",
    accent="#0B7A5F",
    accent_2="#C08A2E",
    accent_ink="#FFFFFF",
    line="#CFE4D8",
    chip_bg="#DEEFE5",
    chip_ink="#2C5E4C",
    quote_ink="#3E6154",
    today_bg="#0B7A5F",
    today_ink="#FFFFFF",
    hover_bg="#E8F4EC",
)

#: Bảng màu 3 – "Hoàng hôn": giấy hồng đào, nhấn cam đất, đượm chất giấy cũ.
_HOANG_HON = Theme(
    name="hoang_hon",
    display_name="Hoàng hôn",
    dark=False,
    paper="#FFF8F1",
    paper_2="#FBE7D6",
    paper_edge="#EBCDB4",
    shadow="rgba(74, 36, 16, 0.28)",
    ink="#33201A",
    ink_soft="#77503F",
    ink_faint="#C4A08A",
    weekend_ink="#C0492A",
    accent="#C0492A",
    accent_2="#D9A13F",
    accent_ink="#FFFFFF",
    line="#F0D8C2",
    chip_bg="#F9E5D1",
    chip_ink="#8A4E2A",
    quote_ink="#7B533C",
    today_bg="#C0492A",
    today_ink="#FFFFFF",
    hover_bg="#FCEEDF",
)

#: Bảng màu 4 – "Đêm sao": nền than, chữ kem, nhấn đỏ son (dùng ban đêm).
_DEM_SAO = Theme(
    name="dem_sao",
    display_name="Đêm sao",
    dark=True,
    paper="#20232B",
    paper_2="#14161C",
    paper_edge="#333846",
    shadow="rgba(0, 0, 0, 0.55)",
    ink="#F4EBDC",
    ink_soft="#B9AE9C",
    ink_faint="#6E6759",
    weekend_ink="#F07468",
    accent="#E2564B",
    accent_2="#D6B36A",
    accent_ink="#1B1410",
    line="#343947",
    chip_bg="#2C3140",
    chip_ink="#D9CFB9",
    quote_ink="#C3B79F",
    today_bg="#E2564B",
    today_ink="#1B1410",
    hover_bg="#2A2F3B",
)

#: Thứ tự hiển thị trong hộp thoại cài đặt.
THEME_ORDER: tuple[str, ...] = ("giay_do", "xanh_ngoc", "hoang_hon", "dem_sao")

THEMES: dict[str, Theme] = {
    t.name: t for t in (_GIay_DO, _XANH_NGOC, _HOANG_HON, _DEM_SAO)
}

DEFAULT_THEME = "giay_do"


def get_theme(name: str | None) -> Theme:
    """Lấy theme theo tên, tự lùi về theme mặc định nếu tên không hợp lệ."""
    if not name:
        return THEMES[DEFAULT_THEME]
    return THEMES.get(name, THEMES[DEFAULT_THEME])


#: Gợi ý màu nền giấy cho người dùng: (tên hiển thị, mã màu).
#: Chuỗi rỗng = "theo giao diện" (dùng màu giấy gốc của theme đang chọn).
BACKGROUND_PRESETS: tuple[tuple[str, str], ...] = (
    ("Giấy ngà", "#FFFDF6"),
    ("Trắng", "#FFFFFF"),
    ("Kem", "#FBF3E2"),
    ("Xanh bạc hà", "#EAF4EE"),
    ("Hồng phấn", "#FBEEF0"),
    ("Xanh da trời", "#E8F0FA"),
    ("Xám tro", "#D9D5CC"),
    ("Tím nhạt", "#EFE9F7"),
    ("Than", "#20232B"),
    ("Đen xanh", "#141A22"),
)


def with_background(theme: Theme, color: str) -> Theme:
    """Đổi **màu giấy** của theme theo ``color``; chuỗi rỗng/không hợp lệ thì giữ nguyên.

    Ngoài màu giấy, nếu độ sáng của màu mới khác tông của theme thì bộ **mực**
    (chữ, chip, đường kẻ, bóng đổ) được lấy từ gói tương phản tương ứng
    (giấy sáng → mực tối như "Giấy đỏ"; giấy tối → mực sáng như "Đêm sao"),
    nhờ vậy người dùng chọn nền tối vẫn đọc được chữ.
    """
    if not color or not is_valid_color(color):
        return theme

    dark_bg = _luminance(color) < 0.42
    if dark_bg == theme.dark:
        base = theme                       # cùng tông: giữ nguyên bộ màu của theme
    else:
        base = THEMES["dem_sao"] if dark_bg else THEMES["giay_do"]

    toward = "#FFFFFF" if dark_bg else "#000000"
    return replace(
        base,
        name=theme.name,
        display_name=theme.display_name,
        dark=dark_bg,
        paper=color,
        paper_2=_mix(color, toward, 0.07),
        paper_edge=_mix(color, toward, 0.16),
        hover_bg=_mix(color, toward, 0.09),
    )


def paper_theme(theme: Theme, opacity: float = 1.0, bg_color: str = "") -> Theme:
    """Theme dùng để **vẽ**: màu nền tuỳ chọn + độ trong suốt chỉ trên phần nền.

    Đây là điểm cốt lõi của yêu cầu "khoá opacity của chữ, chỉ giảm độ trong
    suốt của nền": độ mờ được nhúng vào **màu giấy** (paper/paper_2/paper_edge)
    chứ không áp lên cả cửa sổ, nên chữ, badge, chip giờ hoàng đạo… vẫn đục
    100 % và luôn đọc được.
    """
    base = with_background(theme, bg_color)
    a = max(0.0, min(1.0, float(opacity)))
    if a >= 0.999:
        return base
    # Giữ mép giấy đậm hơn một chút để đường bao vẫn thấy khi nền rất trong.
    edge_alpha = min(1.0, a + 0.18)
    return replace(
        base,
        paper=_with_alpha(base.paper, a),
        paper_2=_with_alpha(base.paper_2, a),
        paper_edge=_with_alpha(base.paper_edge, edge_alpha),
    )
