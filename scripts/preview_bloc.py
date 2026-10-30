"""Render ảnh preview cho :class:`qtcalendar.ui.bloc_view.BlocView`.

Mục đích: **tự kiểm bằng mắt** mặt trước lịch bloc trước khi bàn giao – render
3 ngày × 4 bảng màu ở kích thước chuẩn 344×468, thêm 2 ảnh khung hẹp
280×420, ảnh scale 125 %, ảnh trạng thái (hắc đạo / ẩn giờ hoàng đạo / ẩn ca
dao / ca dao 3 dòng / khung nhỏ nhất) và ảnh tích hợp cửa sổ thật
(``CalendarWidget``). Mỗi ảnh được kiểm tra tự động theo bố cục 3 cột chân
lịch: chữ trong nhãn có bị cắt (nhãn nhiều dòng đo từng dòng), châm ngôn dải
hoa văn có vừa khung, số ngày dương/âm có bị cắt, thành phần có tràn khỏi tờ
giấy hay đè nhau, chân lịch có đủ thành phần, khoảng thở ca dao → nguồn (đo
giữa hai vệt mực) ≥ 6 px ở khung chuẩn. Script cũng kiểm tra
:func:`qtcalendar.ui.styles.build_stylesheet` có đủ toàn bộ selector bắt buộc
cho cả 4 bảng màu.

Cách chạy (từ gốc dự án)::

    python -X utf8 scripts/preview_bloc.py        # mặc định: offscreen
    python -X utf8 scripts/preview_bloc.py --native   # render bằng nền tảng thật

Ở chế độ mặc định script đặt ``QT_QPA_PLATFORM=offscreen`` (không cần cửa sổ
thật) và tự nạp font hệ thống Windows (Segoe UI, Palatino Linotype) vì QPA offscreen
không đọc được font hệ thống.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PREVIEW_DIR = ROOT / "preview"

#: Ba ngày đại diện: thường – Tết Nguyên Đán – tháng nhuận.
DAYS: tuple[date, ...] = (
    date(2026, 10, 28),  # thứ tư, tiết Sương Giáng
    date(2026, 2, 17),  # Mùng 1 Tết Nguyên Đán Bính Ngọ
    date(2023, 3, 22),  # Mùng 1 tháng Hai nhuận
)

#: Ngày hắc đạo (không phải ngày hoàng đạo) – dùng kiểm tra ẩn badge.
NON_AUSPICIOUS_DAY = date(2026, 10, 1)  # Ngày 21 tháng Tám, tiết Thu Phân

#: Bốn bảng màu trong :mod:`qtcalendar.core.theme`.
THEMES: tuple[str, ...] = ("giay_do", "xanh_ngoc", "hoang_hon", "dem_sao")

#: Kích thước chuẩn và kích thước hẹp.
SIZE_DEFAULT = (344, 468)
SIZE_NARROW = (280, 420)

#: Kích thước thiết kế của bloc và lề shell (khớp ``widget_window``).
_DESIGN_SIZE = (344, 468)
_SHELL_MARGIN = 10  # widget_window.SHADOW_MARGIN

#: Ca dao dự phòng khi module ``quotes`` chưa sẵn sàng.
FALLBACK_QUOTES: tuple[tuple[str, str, str], ...] = (
    (
        "Một cây làm chẳng nên non, ba cây chụm lại nên hòn núi cao",
        "",
        "ca-dao",
    ),
    (
        "Mồng một Tết cha, mồng ba Tết thầy",
        "",
        "tuc-ngu",
    ),
    (
        "Dù ai đi ngược về xuôi, nhớ ngày Giỗ Tổ mùng mười tháng Ba",
        "",
        "ca-dao",
    ),
)

#: Ca dao dài (3 dòng) kèm tác giả – kiểm tra ngắt dòng + dòng ghi nguồn.
LONG_QUOTE = (
    "Trăm năm trong cõi người ta, chữ tài chữ mệnh khéo là ghét nhau. "
    "Trải qua một cuộc bể dâu, những điều trông thấy mà đau đớn lòng.",
    "Nguyễn Du",
    "danh-ngon",
)

#: Toàn bộ selector QSS bắt buộc. Phần lịch bloc khớp widget thật của
#: ``BlocView`` (bố cục 3 cột chân lịch) – ``_validate_stylesheets`` dò lại
#: các nhãn của ``BlocView`` để danh sách này không lỗi thời âm thầm.
REQUIRED_SELECTORS: tuple[str, ...] = (
    "QWidget#BlocRoot",
    "QLabel#SolarDayLabel",
    "QLabel#QuoteLabel",
    "QLabel#CreditLabel",
    "QLabel#Col1MonthEn",
    "QLabel#Col1MonthVn",
    "QLabel#Col1Zodiac",
    "QLabel#Col1HoursTitle",
    "QLabel#Col1Hours",
    "QLabel#Col1Footer",
    "QLabel#Col2Weekday",
    "QLabel#Col2WeekdayEn",
    "QLabel#Col3LunarMonth",
    "QLabel#Col3CanChi",
    "QLabel#Col3TietKhi",
    "QFrame#Divider",
    "QWidget#DividerOrnament",
    "QWidget#MonthRoot",
    "QLabel#MonthTitleLabel",
    "QLabel#MonthSubtitleLabel",
    "QPushButton#NavButton",
    "QPushButton#ViewSwitch",
    "QWidget#DayCell",
    "QLabel#CellSolarLabel",
    "QLabel#CellLunarLabel",
    "QDialog",
    "QComboBox",
    "QSlider",
    "QCheckBox",
)

#: Thành phần chân lịch 3 cột luôn phải hiện (objectName → số widget).
FOOTER_PARTS: dict[str, int] = {
    "Col1MonthEn": 1,
    "Col1MonthVn": 1,
    "Col1Zodiac": 1,
    "Col1Footer": 1,
    "Col2Weekday": 1,
    "Col2WeekdayEn": 1,
    "Col2LunarPill": 1,
    "Col3LunarMonth": 1,
    "Col3CanChi": 4,
}

#: Khoảng thở tối thiểu giữa mực dòng cuối ca dao và mực dòng ghi nguồn, tính
#: bằng design-pixel ở khung chuẩn 344×468 (quy đổi theo hệ số co giãn thật).
QUOTE_CREDIT_MIN_GAP = 6

#: Ngưỡng alpha (0–255) để một điểm ảnh được tính là mực chữ khi đo khoảng
#: thở – loại bóng mờ "mực thấm" (alpha ≈ 10–12 %) và viền khử răng cưa nhạt.
_INK_ALPHA = 64
#: Ngưỡng alpha khi xét chữ bị cắt: chỉ mất điểm ảnh mực đậm (≥ 50 %) mới thấy
#: nét bị xén; mất vài điểm viền khử răng cưa nhạt thì mắt không nhận ra.
_SOLID_INK_ALPHA = 128
_INK_TABLE = bytes(1 if value >= _INK_ALPHA else 0 for value in range(256))
_SOLID_INK_TABLE = bytes(1 if value >= _SOLID_INK_ALPHA else 0 for value in range(256))

#: Font hệ thống cần nạp khi chạy offscreen (Windows).
_WINDOWS_FONT_FILES: tuple[str, ...] = (
    "segoeui.ttf",
    "segoeuib.ttf",
    "segoeuii.ttf",
    "segoeuiz.ttf",
    "segoeuil.ttf",
    "segoeuisl.ttf",
    "seguibl.ttf",
    "seguibli.ttf",
    "seguisb.ttf",
    "seguisbi.ttf",
    "pala.ttf",
    "palab.ttf",
    "palai.ttf",
    "palabi.ttf",
)


@dataclass(slots=True)
class RenderReport:
    """Kết quả một ảnh: đường dẫn + các cảnh báo bố cục."""

    path: Path
    size: tuple[int, int]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Chuẩn bị Qt / font
# ---------------------------------------------------------------------------


def _prepare_platform(native: bool) -> str:
    """Chọn nền tảng Qt; trả về tên nền tảng sẽ dùng."""
    if native:
        os.environ.pop("QT_QPA_PLATFORM", None)
        os.environ.pop("QT_OPENGL", None)
        return "native"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return os.environ.get("QT_QPA_PLATFORM", "offscreen")


def _ensure_system_fonts() -> list[str]:
    """Nạp font Windows cho QPA offscreen (nó không đọc font hệ thống)."""
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    if {"Segoe UI", "Palatino Linotype"} <= families:
        return []
    loaded: list[str] = []
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in _WINDOWS_FONT_FILES:
        path = fonts_dir / name
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            loaded.append(name)
    return loaded


def _prepare_app(native: bool):
    """Tạo QApplication và nạp font cần thiết."""
    platform = _prepare_platform(native)
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    loaded = _ensure_system_fonts()
    mode = app.platformName()
    print(f"[preview] platform={mode}" + (" (font nạp thêm: " + ", ".join(loaded) + ")" if loaded else ""))
    if mode == "offscreen" and not _ensure_fonts_ok():
        print(
            "[preview] CẢNH BÁO: thiếu font Segoe UI/Palatino Linotype – ảnh có thể không "
            "đúng typography.",
            file=sys.stderr,
        )
    del platform
    return app


def _ensure_fonts_ok() -> bool:
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    return "Segoe UI" in families and "Palatino Linotype" in families


def _quote_for(index: int, day: date):
    """Ca dao của ngày; lùi về câu mẫu nếu kho dữ liệu chưa sẵn sàng."""
    from qtcalendar.core.types import Quote

    try:
        from qtcalendar.core.quotes import quote_of_day

        quote = quote_of_day(day)
        if quote is not None and quote.text.strip():
            return quote
    except Exception:  # noqa: BLE001 - kho ca dao có thể chưa xong
        pass
    text, author, topic = FALLBACK_QUOTES[index % len(FALLBACK_QUOTES)]
    return Quote(text=text, author=author, topic=topic)


# ---------------------------------------------------------------------------
# Render + tự kiểm
# ---------------------------------------------------------------------------


def _render(
    app,
    day: date,
    theme_name: str,
    size: tuple[int, int],
    path: Path,
    *,
    quote=None,
    show_quote: bool = True,
    show_auspicious: bool = True,
    show_tiet_khi: bool = True,
    scale: float = 1.0,
) -> RenderReport:
    from PySide6.QtCore import Qt

    from qtcalendar.core.calendar_service import get_day_info
    from qtcalendar.core.theme import get_theme
    from qtcalendar.ui.bloc_view import BlocView

    info = get_day_info(day)
    view = BlocView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    # Mô phỏng đúng hợp đồng của widget_window.CalendarWidget: nó bọc view
    # trong cửa sổ lớn hơn 2×SHADOW_MARGIN và truyền
    # content_scale = user_scale × min(win_w/344, win_h/468) (kẹp 0.5…2.6).
    win_w = size[0] + 2 * _SHELL_MARGIN
    win_h = size[1] + 2 * _SHELL_MARGIN
    content_scale = max(
        0.5,
        min(
            2.6,
            scale * min(win_w / _DESIGN_SIZE[0], win_h / _DESIGN_SIZE[1]),
        ),
    )
    view.apply_theme(get_theme(theme_name), content_scale)
    view.set_day(info)
    view.set_quote(quote if show_quote else None)
    view.set_show_auspicious(show_auspicious)
    view.set_show_tiet_khi(show_tiet_khi)
    view.resize(size[0], size[1])
    view.show()
    app.processEvents()
    view.refresh()
    app.processEvents()

    warnings: list[str] = []
    if view.width() != size[0] or view.height() != size[1]:  # pragma: no cover
        warnings.append(
            f"kích thước thực {view.width()}x{view.height()} khác yêu cầu {size}"
        )
    warnings.extend(
        _layout_warnings(
            view,
            info,
            show_quote=show_quote and quote is not None,
            show_auspicious=show_auspicious,
            show_tiet_khi=show_tiet_khi,
        )
    )

    pixmap = view.grab()
    if pixmap.isNull():  # pragma: no cover
        warnings.append("grab() trả về ảnh rỗng")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path), "PNG"):  # pragma: no cover
        warnings.append(f"không ghi được ảnh {path}")
    actual = (pixmap.width(), pixmap.height())

    view.hide()
    view.deleteLater()
    app.processEvents()
    return RenderReport(path=path, size=actual, warnings=warnings)


def _describe(widget) -> str:
    """Tên widget kèm chữ đang hiện (bốn nhãn ``Col3CanChi`` trùng objectName)."""
    name = widget.objectName() or type(widget).__name__
    text = widget.text() if callable(getattr(widget, "text", None)) else ""
    first = text.split("\n", 1)[0].strip()
    if not first:
        return name
    if len(first) > 24:
        first = first[:23] + "…"
    return f"{name} '{first}'"


def _label_flags(label) -> int:
    """Cờ ``drawText`` mà QLabel dùng khi vẽ chữ thuần (alignment ± ngắt dòng)."""
    from PySide6.QtCore import Qt

    flags = label.alignment().value
    if label.wordWrap():
        flags |= Qt.TextFlag.TextWordWrap.value
    return flags


def _ink_box(image, table: bytes = _INK_TABLE) -> tuple[int, int, int, int] | None:
    """Hộp (trái, trên, phải, dưới) các điểm ảnh có mực của ảnh ARGB32.

    ``table`` đổi alpha → 1 (là mực) / 0, chọn ngưỡng mực nhạt hay mực đậm.
    """
    stride = image.bytesPerLine()
    row_bytes = 4 * image.width()
    data = bytes(image.constBits())
    box: list[int] | None = None
    for y in range(image.height()):
        # ARGB32 little-endian: mỗi điểm ảnh là B, G, R, A → alpha ở byte thứ 4
        alpha = data[y * stride + 3 : y * stride + row_bytes : 4].translate(table)
        first = alpha.find(1)
        if first < 0:
            continue
        last = alpha.rfind(1)
        if box is None:
            box = [first, y, last, y]
        else:
            box[0] = min(box[0], first)
            box[2] = max(box[2], last)
            box[3] = y
    return None if box is None else (box[0], box[1], box[2], box[3])


def _ink_rows(widget) -> tuple[int, int] | None:
    """Hàng điểm ảnh đầu/cuối có mực của ``widget`` (toạ độ trong view cha).

    Vẽ riêng widget lên ảnh trong suốt (không nền, không widget con) rồi dò
    kênh alpha: đo đúng chữ đã vẽ thay vì hộp ascent/descent của font.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QImage, QRegion
    from PySide6.QtWidgets import QWidget

    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag(0))
    box = _ink_box(image)
    return None if box is None else (widget.y() + box[1], widget.y() + box[3])


def _ink_overflow(widget, area, font, draw) -> int:
    """Số điểm ảnh mực chữ thò ra ngoài ``area`` – phần đó bị cắt khi vẽ thật.

    ``draw(painter, rect)`` lặp lại đúng lệnh vẽ chữ của widget vào ``rect``
    (cùng cỡ ``area``) nhưng không cắt; ảnh được nới rộng quanh khung để giữ
    phần tràn rồi so hộp mực đậm với khung. 0 = mực đậm nằm trọn trong khung,
    nên hộp dòng (ascent/descent) có lố 1–2px mà nét chữ không chạm mép, hay
    chỉ mất viền khử răng cưa nhạt, thì không tính.
    """
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    width = int(area.width())
    height = int(area.height())
    pad = max(16, max(width, height) // 2)
    image = QImage(
        width + 2 * pad, height + 2 * pad, QImage.Format.Format_ARGB32_Premultiplied
    )
    dots_per_meter = round(widget.logicalDpiY() / 0.0254)  # font cỡ point
    image.setDotsPerMeterX(dots_per_meter)
    image.setDotsPerMeterY(dots_per_meter)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setFont(font)
    painter.setPen(QColor(0, 0, 0))
    draw(painter, QRectF(pad, pad, area.width(), area.height()))
    painter.end()
    box = _ink_box(image, _SOLID_INK_TABLE)
    if box is None:
        return 0
    left, top, right, bottom = box
    return max(
        0,
        pad - left,
        pad - top,
        right - (pad + width - 1),
        bottom - (pad + height - 1),
    )


def _draw_text_in(text: str, flags: int):
    """Lệnh vẽ ``drawText(rect, flags, text)`` (như QLabel/QPainter) nhưng không cắt."""
    from PySide6.QtCore import Qt

    def draw(painter, rect) -> None:
        painter.drawText(rect, flags | Qt.TextFlag.TextDontClip.value, text)

    return draw


def _draw_text_centered(text: str):
    """Lệnh vẽ số căn tâm theo hộp mực – khớp ``_DayNumber``/``_LunarPill``."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFontMetricsF

    def draw(painter, rect) -> None:
        tight = QFontMetricsF(painter.font()).tightBoundingRect(text)
        x = rect.x() + (rect.width() - tight.width()) / 2.0 - tight.x()
        y = rect.y() + rect.height() / 2.0 - (tight.y() + tight.height() / 2.0)
        painter.drawText(QPointF(x, y), text)

    return draw


def _layout_warnings(
    view,
    info,
    *,
    show_quote: bool,
    show_auspicious: bool,
    show_tiet_khi: bool,
) -> list[str]:
    """Tự kiểm bố cục ``BlocView`` (banner – số ngày – ca dao – chân lịch 3 cột)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFontMetricsF
    from PySide6.QtWidgets import QLabel, QWidget

    from qtcalendar.ui.styles import px

    warnings: list[str] = []
    eff = view._eff  # noqa: SLF001 - chỉ dùng để tự kiểm
    day_number = view._day  # noqa: SLF001 - chỉ dùng để tự kiểm
    banner = view._top_banner  # noqa: SLF001 - chỉ dùng để tự kiểm
    divider = view._div_footer  # noqa: SLF001 - chỉ dùng để tự kiểm
    quote_label = view.findChild(QLabel, "QuoteLabel")
    credit_label = view.findChild(QLabel, "CreditLabel")
    visible = [
        w
        for w in view._all_widgets  # noqa: SLF001 - chỉ dùng để tự kiểm
        if not w.isHidden() and not w.geometry().isEmpty()
    ]

    # --- chữ trong nhãn không bị cắt: vẽ lại như QLabel (tách dòng theo \n,
    # đo từng dòng, căn theo alignment) rồi xem mực có thò khỏi nhãn không ---
    for label in view.findChildren(QLabel):
        if label is day_number:  # tự vẽ, kiểm riêng bên dưới
            continue
        if label.isHidden() or label.geometry().isEmpty() or not label.text():
            continue
        area = QRectF(label.contentsRect())
        flags = _label_flags(label)
        cut = _ink_overflow(label, area, label.font(), _draw_text_in(label.text(), flags))
        if cut > 0:
            block = QFontMetricsF(label.font()).boundingRect(area, flags, label.text())
            lines = label.text().count("\n") + 1
            per_line = f", dòng dài nhất trong {lines} dòng" if lines > 1 else ""
            warnings.append(
                f"{_describe(label)}: mực chữ bị cắt {cut}px "
                f"(khối chữ {block.width():.0f}×{block.height():.0f}px{per_line} "
                f"> nhãn {area.width():.0f}×{area.height():.0f}px)"
            )

    # --- mọi thành phần nằm trong tờ giấy (không lấn xuống mép giấy/bóng đổ) ---
    paper = view._paper_rect().adjusted(-1, -1, 1, 1)  # noqa: SLF001 - chỉ dùng để tự kiểm
    for widget in visible:
        if not paper.contains(QRectF(widget.geometry())):
            warnings.append(
                f"{_describe(widget)}: tràn ra ngoài tờ giấy {widget.geometry().getRect()}"
            )

    # --- chân lịch 3 cột phải đủ thành phần, phần tuỳ chọn ẩn/hiện đúng cài đặt ---
    for name, count in FOOTER_PARTS.items():
        widgets = view.findChildren(QWidget, name)
        if len(widgets) != count:
            warnings.append(f"{name}: có {len(widgets)} widget, cần {count} (chân lịch hỏng)")
        for widget in widgets:
            if widget.isHidden() or widget.geometry().isEmpty() or not widget.text().strip():
                warnings.append(f"{_describe(widget)}: bị ẩn/rỗng (chân lịch thiếu thành phần)")
    has_hours = bool(info.auspicious_hours)
    expected = {
        "Col1HoursTitle": show_auspicious and has_hours,
        "Col1Hours": show_auspicious and has_hours,
        "Col3TietKhi": show_tiet_khi and bool((info.tiet_khi or "").strip()),
        "QuoteLabel": show_quote,
    }
    for name, should_show in expected.items():
        widget = view.findChild(QWidget, name)
        shown = (
            widget is not None
            and not widget.isHidden()
            and not widget.geometry().isEmpty()
        )
        if shown != should_show:
            state = "đang ẩn dù phải hiện" if should_show else "vẫn hiện dù đã tắt"
            warnings.append(f"{name}: {state}")

    # --- châm ngôn trên dải hoa văn (_TopArtBanner tự vẽ, cắt theo khung chữ) ---
    if banner in visible and banner.width() > 140:  # hẹp hơn thì banner bỏ châm ngôn
        motto = banner._motto  # noqa: SLF001 - chỉ dùng để tự kiểm
        motto_font = banner.font_for_paint()
        # khớp text_rect trong _TopArtBanner.paintEvent (drawText cắt theo khung này)
        area = QRectF(46.0, 2.0, banner.width() - 92.0, banner.height() - 6.0)
        flags = Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value
        cut = _ink_overflow(banner, area, motto_font, _draw_text_in(motto, flags))
        if cut > 0:
            motto_metrics = QFontMetricsF(motto_font, banner)
            block = motto_metrics.boundingRect(area, flags, motto)
            lines = max(1, round(block.height() / motto_metrics.lineSpacing()))
            warnings.append(
                f"TopArtBanner: châm ngôn {lines} dòng bị cắt {cut}px "
                f"(khối chữ {block.height():.0f}px > khung chữ "
                f"{area.width():.0f}×{area.height():.0f}px)"
            )

    # --- số ngày dương (vẽ tay): không bị cắt, cách banner và dòng kế dưới ≥ 4px ---
    if day_number in visible:
        day_font = day_number.font_for_paint()
        cut = _ink_overflow(
            day_number,
            QRectF(day_number.rect()),
            day_font,
            _draw_text_centered(day_number.text()),
        )
        if cut > 0:
            tight = QFontMetricsF(day_font).tightBoundingRect(day_number.text())
            warnings.append(
                f"{_describe(day_number)}: mực số bị cắt {cut}px "
                f"({tight.width():.0f}×{tight.height():.0f}px "
                f"> khung {day_number.width()}×{day_number.height()}px)"
            )
        day_ink = _ink_rows(day_number)
        banner_ink = _ink_rows(banner) if banner in visible else None
        if day_ink and banner_ink:
            gap = day_ink[0] - banner_ink[1] - 1
            if gap < 4:
                warnings.append(f"số ngày cách dải hoa văn chỉ {gap}px (< 4px)")
        if quote_label in visible:
            below_name, below_ink = "ca dao", _ink_rows(quote_label)
            below_top = below_ink[0] if below_ink else None
        else:
            below_name, below_top = "đường phân cách", divider.y()
        if day_ink and below_top is not None:
            gap = below_top - day_ink[1] - 1
            if gap < 4:
                warnings.append(f"số ngày cách {below_name} chỉ {gap}px (< 4px)")

    # --- khoảng thở ca dao → nguồn, đo giữa hai vệt mực ---
    # _relayout() đặt nhãn nguồn ngay dưới hộp các dòng ca dao + px(2): khoảng
    # thở thật còn gồm descent của ca dao và phần trống trên dấu của dòng nguồn,
    # nên đo giữa mực của hai dòng, không đo giữa hai hộp nhãn (luôn = px(2)).
    if quote_label in visible and credit_label in visible:
        quote_ink = _ink_rows(quote_label)
        credit_ink = _ink_rows(credit_label)
        if quote_ink and credit_ink:
            gap = credit_ink[0] - quote_ink[1] - 1
            need = px(QUOTE_CREDIT_MIN_GAP, eff)
            if gap < need:
                warnings.append(
                    f"khoảng thở ca dao → nguồn chỉ {gap}px "
                    f"(< {need}px = {QUOTE_CREDIT_MIN_GAP}px × co giãn {eff:.2f})"
                )

    # --- số ngày âm (Col2LunarPill tự vẽ): mực chữ nằm trọn trong cột giữa ---
    pill = view.findChild(QWidget, "Col2LunarPill")
    if pill is not None and pill in visible and pill.text():
        pill_font = pill.font_for_paint()
        cut = _ink_overflow(
            pill, QRectF(pill.rect()), pill_font, _draw_text_centered(pill.text())
        )
        if cut > 0:
            tight = QFontMetricsF(pill_font).tightBoundingRect(pill.text())
            warnings.append(
                f"{_describe(pill)}: mực chữ bị cắt {cut}px "
                f"({tight.width():.0f}×{tight.height():.0f}px "
                f"> khung {pill.width()}×{pill.height()}px)"
            )
        # số âm phải lớn gấp ≥ 2,5 lần cỡ chữ cũ (17.8px) ở khung chuẩn
        if (
            pill.text().isdigit()
            and view.width() >= 340
            and pill_font.pixelSize() < round(17.8 * 2.5)
        ):
            warnings.append(
                f"{_describe(pill)}: cỡ số âm {pill_font.pixelSize()}px < 44.5px (2,5×)"
            )

    # --- các thành phần hiển thị không được đè nhau ---
    for i, first in enumerate(visible):
        for second in visible[i + 1 :]:
            inter = first.geometry().intersected(second.geometry())
            if inter.width() > 2 and inter.height() > 2:
                warnings.append(
                    f"nhãn đè nhau: {_describe(first)} ↔ {_describe(second)} "
                    f"({inter.getRect()})"
                )
    return warnings


def _validate_stylesheets() -> list[str]:
    """Kiểm tra :mod:`qtcalendar.ui.styles` có đủ selector bắt buộc.

    Thử cả 4 bảng màu ở 3 mức scale để chắc QSS sinh được ở mọi tổ hợp và
    không có màu hard-code ngoài ``Theme`` (mọi mã màu đều phải xuất hiện
    trong bảng màu của theme).
    """
    from qtcalendar.core.theme import THEMES as ALL_THEMES
    from qtcalendar.ui.styles import build_dialog_stylesheet, build_stylesheet

    problems: list[str] = []
    combos = 0
    for theme in ALL_THEMES.values():
        for scale in (0.75, 1.0, 1.25):
            combos += 1
            try:
                qss = build_stylesheet(theme, scale)
                dialog_qss = build_dialog_stylesheet(theme, scale)
            except Exception as exc:  # noqa: BLE001 - tự kiểm, không ném ra ngoài
                problems.append(
                    f"{theme.name}@{scale}: build_stylesheet lỗi {type(exc).__name__}: {exc}"
                )
                continue
            for selector in REQUIRED_SELECTORS:
                if selector not in qss:
                    problems.append(f"{theme.name}@{scale}: thiếu selector {selector}")
            for selector in ("QDialog", "QPushButton", "QComboBox", "QSlider", "QCheckBox"):
                if selector not in dialog_qss:
                    problems.append(f"{theme.name}@{scale}: QSS hộp thoại thiếu {selector}")
            # QSS dùng ngoặc nhọn cân đối
            if qss.count("{") != qss.count("}"):
                problems.append(f"{theme.name}@{scale}: ngoặc nhọn lệch")
    for selector in sorted(_bloc_label_selectors() - set(REQUIRED_SELECTORS)):
        problems.append(
            f"REQUIRED_SELECTORS thiếu {selector} – nhãn có thật trong BlocView"
        )
    print(
        f"[preview] QSS: kiểm {len(REQUIRED_SELECTORS)} selector × {combos} tổ hợp "
        f"(4 theme × 3 scale) → {'OK' if not problems else f'{len(problems)} lỗi'}"
    )
    return problems


def _bloc_label_selectors() -> set[str]:
    """Selector QSS mà các nhãn/khung thật của ``BlocView`` dựa vào để lấy màu."""
    from PySide6.QtWidgets import QFrame, QLabel

    from qtcalendar.ui.bloc_view import BlocView

    view = BlocView()
    selectors = {f"QWidget#{view.objectName()}"}
    for widget in view.findChildren(QFrame):
        if widget.objectName():
            kind = "QLabel" if isinstance(widget, QLabel) else "QFrame"
            selectors.add(f"{kind}#{widget.objectName()}")
    view.deleteLater()
    return selectors


def _clean_previous_images() -> int:
    """Xoá ảnh cũ do script này sinh ra để tránh lẫn ảnh của lần render trước."""
    removed = 0
    for pattern in ("bloc_*.png", "app_bloc_*.png"):
        for path in PREVIEW_DIR.glob(pattern):
            try:
                path.unlink()
                removed += 1
            except OSError:  # pragma: no cover - file đang mở
                pass
    if removed:
        print(f"[preview] đã xoá {removed} ảnh cũ trùng tên")
    return removed


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    native = "--native" in argv
    app = _prepare_app(native)
    qss_problems = _validate_stylesheets()
    _clean_previous_images()

    reports: list[RenderReport] = []
    index = 0

    # 12 ảnh: 3 ngày × 4 bảng màu, kích thước chuẩn 344×468
    for day in DAYS:
        quote = _quote_for(index, day)
        for theme_name in THEMES:
            path = PREVIEW_DIR / f"bloc_{day.isoformat()}_{theme_name}.png"
            reports.append(
                _render(app, day, theme_name, SIZE_DEFAULT, path, quote=quote)
            )
        index += 1

    # Quét kích thước bắt buộc: 260×320 (min) → 520×700 (kéo giãn)
    size_sweep = (
        (260, 320, 1.0),
        (300, 400, 1.0),
        (380, 520, 1.0),
        (430, 585, 1.25),
        (520, 700, 1.0),
    )
    for width, height, scale in size_sweep:
        path = PREVIEW_DIR / f"bloc_2026-10-28_giay_do_{width}x{height}.png"
        reports.append(
            _render(
                app,
                DAYS[0],
                "giay_do",
                (width, height),
                path,
                quote=_quote_for(0, DAYS[0]),
                scale=scale,
            )
        )

    # khung nhỏ nhất thực tế của shell (window 260×330 − lề 10px) – kiểm an toàn
    reports.append(
        _render(
            app,
            DAYS[0],
            "giay_do",
            (240, 310),
            PREVIEW_DIR / "bloc_2026-10-28_giay_do_240x310.png",
            quote=_quote_for(0, DAYS[0]),
        )
    )

    # khung lớn nhất khi kéo tay nắm resize (window 1000×1300 − lề 10px)
    reports.append(
        _render(
            app,
            DAYS[0],
            "giay_do",
            (980, 1280),
            PREVIEW_DIR / "bloc_2026-10-28_giay_do_980x1280.png",
            quote=_quote_for(0, DAYS[0]),
        )
    )

    # Tết (Mùng 1 + badge lễ) và tháng nhuận ở khung chuẩn / lớn / nhỏ
    extra_specs = (
        (DAYS[1], "giay_do", (520, 700), 1.0),  # Tết ở khung lớn
        (DAYS[1], "giay_do", (260, 320), 1.0),  # Tết ở khung nhỏ nhất
        (DAYS[2], "giay_do", (520, 700), 1.0),  # tháng Hai (nhuận) khung lớn
        (DAYS[2], "giay_do", (260, 320), 1.0),  # tháng nhuận khung nhỏ
    )
    for day, theme_name, size, scale in extra_specs:
        path = PREVIEW_DIR / f"bloc_{day.isoformat()}_{theme_name}_{size[0]}x{size[1]}.png"
        reports.append(
            _render(
                app,
                day,
                theme_name,
                size,
                path,
                quote=_quote_for(DAYS.index(day), day),
                scale=scale,
            )
        )

    # ngày rằm (15 âm): viên thuốc hiện chữ "Rằm" thay cho số
    rằm_day = date(2026, 10, 24)
    reports.append(
        _render(
            app,
            rằm_day,
            "giay_do",
            SIZE_DEFAULT,
            PREVIEW_DIR / "bloc_state_ram_2026-10-24.png",
            quote=_quote_for(4, rằm_day),
        )
    )

    # ngày hắc đạo: badge "Ngày hoàng đạo" phải ẩn, không để khoảng trống chết
    reports.append(
        _render(
            app,
            NON_AUSPICIOUS_DAY,
            "giay_do",
            SIZE_DEFAULT,
            PREVIEW_DIR / "bloc_state_hac_dao_2026-10-01.png",
            quote=_quote_for(3, NON_AUSPICIOUS_DAY),
        )
    )

    # ảnh trạng thái: ẩn giờ hoàng đạo / ẩn ca dao / ca dao dài khung hẹp
    state_specs = (
        ("bloc_state_hide_auspicious.png", dict(show_auspicious=False)),
        ("bloc_state_no_quote.png", dict(show_quote=False)),
        (
            "bloc_state_minimum_quote_dai_260x320.png",
            dict(size=(260, 320), quote=_make_quote(*LONG_QUOTE)),
        ),
        (
            "bloc_state_quote_dai_280x420.png",
            dict(size=(280, 420), quote=_make_quote(*LONG_QUOTE)),
        ),
        (
            "bloc_state_quote_dai_3_dong.png",
            dict(size=SIZE_DEFAULT, quote=_make_quote(*LONG_QUOTE)),
        ),
    )
    for filename, options in state_specs:
        size = options.pop("size", SIZE_DEFAULT)
        quote = options.pop("quote", _quote_for(0, DAYS[0]))
        reports.append(
            _render(
                app,
                DAYS[0],
                "giay_do",
                size,
                PREVIEW_DIR / filename,
                quote=quote,
                **options,
            )
        )

    app_paths = _render_app_scenes(app)
    return _finish(reports, app_paths, qss_problems)


def _make_quote(text: str, author: str, topic: str):
    from qtcalendar.core.types import Quote

    return Quote(text=text, author=author, topic=topic)


def _render_app_scenes(app) -> list[Path]:
    """Render vài ảnh của cửa sổ thật (``widget_window.CalendarWidget``).

    Phần này là *tích hợp*: kiểm tra ``BlocView`` nằm đúng trong shell trong
    suốt (shell tự vẽ bóng, view tô kín card) và hai nút nổi không bị QSS đè.
    Nếu module giao diện chưa sẵn sàng thì bỏ qua, không làm hỏng phần chính.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    import tempfile

    from qtcalendar.core.config import Settings

    # cấu hình tạm ở thư mục temp để không làm bẩn thư mục preview/
    os.environ["QTCALENDAR_CONFIG"] = str(
        Path(tempfile.gettempdir()) / "qtcalendar_preview_settings.json"
    )
    paths: list[Path] = []
    try:
        from qtcalendar.ui.widget_window import CalendarWidget
    except Exception as exc:  # noqa: BLE001 - modul của thành viên khác
        print(f"[preview] bỏ qua ảnh tích hợp cửa sổ thật: {type(exc).__name__}: {exc}")
        return paths

    windows: list[CalendarWidget] = []
    app_specs = (
        ("giay_do", (344, 468)),
        ("dem_sao", (344, 468)),
        ("giay_do", (520, 700)),
    )
    for theme_name, (width, height) in app_specs:
        try:
            settings = Settings(
                theme=theme_name,
                placement="floating",
                width=width,
                height=height,
            )
            window = CalendarWidget(settings)
            window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            window.resize(settings.width, settings.height)
            window.show()
            app.processEvents()
            window.apply_settings()
            app.processEvents()
            suffix = "" if (width, height) == (344, 468) else f"_{width}x{height}"
            path = PREVIEW_DIR / f"app_bloc_{theme_name}{suffix}.png"
            pixmap = window.grab()
            if not pixmap.isNull() and pixmap.save(str(path), "PNG"):
                paths.append(path)
            windows.append(window)
            app.processEvents()
        except Exception as exc:  # noqa: BLE001 - modul của thành viên khác
            print(f"[preview] lỗi render cửa sổ thật ({theme_name}): {exc}")
    for window in windows:
        window.hide()
        window.deleteLater()
    app.processEvents()
    return paths


def _finish(
    reports: list[RenderReport],
    app_paths: list[Path] | None = None,
    qss_problems: list[str] | None = None,
) -> int:
    print(f"\n[preview] Đã render {len(reports)} ảnh vào {PREVIEW_DIR}:")
    total_warnings = 0
    for report in reports:
        warnings = report.warnings
        total_warnings += len(warnings)
        status = "OK" if not warnings else f"{len(warnings)} cảnh báo"
        print(f"  - {report.path}  ({report.size[0]}×{report.size[1]}, {status})")
        for warning in warnings:
            print(f"      ! {warning}")
    if app_paths:
        print("[preview] Ảnh tích hợp cửa sổ thật:")
        for path in app_paths:
            print(f"  - {path}")
    for problem in qss_problems or ():
        print(f"      ! QSS: {problem}")
    if total_warnings or qss_problems:
        print(
            f"\n[preview] TỔNG {total_warnings} cảnh báo bố cục, "
            f"{len(qss_problems or ())} lỗi QSS – cần sửa."
        )
        return 1
    print("\n[preview] Không phát hiện tràn/cắt chữ. Hãy mở ảnh để kiểm mỹ thuật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
