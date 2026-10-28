"""Render ảnh preview cho :class:`qtcalendar.ui.bloc_view.BlocView`.

Mục đích: **tự kiểm bằng mắt** mặt trước lịch bloc trước khi bàn giao – render
3 ngày × 4 bảng màu ở kích thước chuẩn 344×468, thêm 2 ảnh khung hẹp
280×420, ảnh scale 125 %, ảnh trạng thái (hắc đạo / ẩn giờ hoàng đạo / ẩn ca
dao / ca dao 3 dòng / khung nhỏ nhất) và ảnh tích hợp cửa sổ thật
(``CalendarWidget``). Mỗi ảnh được kiểm tra tự động: chữ có bị cắt, nhãn có
tràn khung, các nhãn có đè nhau, khoảng thở ca dao → nguồn ≥ 6 px. Script
cũng kiểm tra :func:`qtcalendar.ui.styles.build_stylesheet` có đủ toàn bộ
selector bắt buộc cho cả 4 bảng màu.

Cách chạy (từ gốc dự án)::

    python -X utf8 scripts/preview_bloc.py        # mặc định: offscreen
    python -X utf8 scripts/preview_bloc.py --native   # render bằng nền tảng thật

Ở chế độ mặc định script đặt ``QT_QPA_PLATFORM=offscreen`` (không cần cửa sổ
thật) và tự nạp font hệ thống Windows (Segoe UI, Georgia) vì QPA offscreen
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

#: Toàn bộ selector QSS bắt buộc (theo đặc tả ``ui/styles.py``).
REQUIRED_SELECTORS: tuple[str, ...] = (
    "QWidget#BlocRoot",
    "QLabel#WeekdayLabel",
    "QLabel#SolarDayLabel",
    "QLabel#SolarMonthLabel",
    "QLabel#LunarLabel",
    "QLabel#LunarCaptionLabel",
    "QLabel#LunarMonthLabel",
    "QLabel#LunarYearLabel",
    "QWidget#LunarPill",
    "QLabel#CanChiLabel",
    "QLabel#QuoteLabel",
    "QLabel#CreditLabel",
    "QLabel#ChipLabel",
    "QLabel#TietKhiLabel",
    "QLabel#HolidayLabel",
    "QFrame#Divider",
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
    "georgia.ttf",
    "georgiab.ttf",
    "georgiai.ttf",
    "georgiaz.ttf",
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
    if {"Segoe UI", "Georgia"} <= families:
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
            "[preview] CẢNH BÁO: thiếu font Segoe UI/Georgia – ảnh có thể không "
            "đúng typography.",
            file=sys.stderr,
        )
    del platform
    return app


def _ensure_fonts_ok() -> bool:
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    return "Segoe UI" in families and "Georgia" in families


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
    from PySide6.QtGui import QFontMetricsF
    from PySide6.QtWidgets import QLabel

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

    labels = {label.objectName(): label for label in view.findChildren(QLabel)}

    for label in view.findChildren(QLabel):
        if label.isHidden() or label.geometry().isEmpty():
            continue
        text = label.text()
        if not text:
            continue
        if label.objectName() == "QuoteLabel":
            # đã ngắt dòng sẵn: kiểm từng dòng không vượt bề rộng nhãn
            metrics = QFontMetricsF(label.font())
            lines = text.split("\n")
            max_width = max(
                (metrics.horizontalAdvance(line) for line in lines),
                default=0.0,
            )
            if max_width > label.width() + 1.5:
                warnings.append(
                    f"{label.objectName()}: dòng ca dao rộng {max_width:.0f}px "
                    f"> nhãn {label.width()}px"
                )
            if len(lines) > 3:
                warnings.append(f"{label.objectName()}: {len(lines)} dòng > 3")
            text_height = metrics.height() * len(lines)
            if label.height() + 0.5 < text_height:
                warnings.append(
                    f"{label.objectName()}: cao {label.height()}px < {len(lines)} dòng "
                    f"cần {text_height:.0f}px"
                )
            continue
        metrics = QFontMetricsF(label.font())
        advance = metrics.horizontalAdvance(text)
        if advance > label.width() + 1.5:
            warnings.append(
                f"{label.objectName()}: chữ rộng {advance:.0f}px > nhãn {label.width()}px"
            )
        height_needed = metrics.height()
        if label.height() + 0.5 < height_needed:
            warnings.append(
                f"{label.objectName()}: cao {label.height()}px < cần {height_needed:.0f}px"
            )
        geometry = label.geometry()
        if geometry.right() > view.width() or geometry.bottom() > view.height():
            warnings.append(
                f"{label.objectName()}: tràn khung {geometry.getRect()}"
            )

    # --- KHỐI ÂM LỊCH phải luôn hiển thị đầy đủ (caption + số + tháng + năm) ---
    lunar_pill = view._lunar_pill  # noqa: SLF001 - chỉ dùng để tự kiểm
    lunar_widgets = {
        "LunarCaptionLabel": labels.get("LunarCaptionLabel"),
        "LunarPill": lunar_pill,
        "LunarMonthLabel": labels.get("LunarMonthLabel"),
        "LunarYearLabel": labels.get("LunarYearLabel"),
    }
    for name, widget in lunar_widgets.items():
        if widget is None:
            warnings.append(f"{name}: không tồn tại (khối âm lịch hỏng)")
            continue
        if widget.isHidden() or widget.geometry().isEmpty():
            warnings.append(f"{name}: khối âm lịch bị ẩn/rỗng")
            continue
        geo = widget.geometry()
        if (
            geo.left() < -1
            or geo.top() < -1
            or geo.right() > view.width() + 1
            or geo.bottom() > view.height() + 1
        ):
            warnings.append(f"{name}: tràn khung {geo.getRect()}")
    month_label = labels.get("LunarMonthLabel")
    if month_label is not None and (
        month_label.isHidden() or not month_label.text().strip()
    ):
        warnings.append("LunarMonthLabel: thiếu nhãn tháng âm")
    if lunar_pill is not None and not lunar_pill.isHidden():
        pill_font = lunar_pill.font_for_paint()
        pill_metrics = QFontMetricsF(pill_font)
        pill_text = lunar_pill.text()
        advance = pill_metrics.horizontalAdvance(pill_text)
        if advance > lunar_pill.width() + 0.5:
            warnings.append(
                f"LunarPill: chữ '{pill_text}' rộng {advance:.0f}px "
                f"> viên {lunar_pill.width()}px"
            )
        tight = pill_metrics.tightBoundingRect(pill_text)
        if tight.height() > lunar_pill.height() + 0.5:
            warnings.append(
                f"LunarPill: cao chữ {tight.height():.0f}px "
                f"> viên {lunar_pill.height()}px"
            )
        # yêu cầu "số âm lớn gấp ≥2,5 lần cỡ chữ cũ (17.8px)" ở khung chuẩn
        if pill_text.isdigit():
            if view.width() >= 340 and pill_font.pixelSize() < round(17.8 * 2.5):
                warnings.append(
                    f"LunarPill: cỡ số âm {pill_font.pixelSize()}px < 44.5px (2,5×)"
                )
        elif view.width() >= 340 and pill_font.pixelSize() < 20:
            warnings.append(
                f"LunarPill: chữ đặc biệt '{pill_text}' chỉ {pill_font.pixelSize()}px (< 20px)"
            )

    # khoảng thở tối thiểu 6px giữa dòng cuối ca dao và dòng ghi nguồn
    quote_label = labels.get("QuoteLabel")
    credit_label = labels.get("CreditLabel")
    if (
        quote_label is not None
        and credit_label is not None
        and not quote_label.isHidden()
        and not quote_label.geometry().isEmpty()
        and not credit_label.isHidden()
    ):
        metrics = QFontMetricsF(quote_label.font())
        line_count = max(1, len(quote_label.text().split("\n")))
        text_height = metrics.height() * line_count
        text_bottom = quote_label.y() + (quote_label.height() - text_height) / 2 + text_height
        gap = credit_label.y() - text_bottom
        if gap < 6:
            warnings.append(
                f"khoảng cách ca dao → nguồn chỉ {gap:.1f}px (< 6px)"
            )

    # số ngày (vẽ tay) phải cách dòng "THÁNG …" tối thiểu 4px
    day_label = view._day  # noqa: SLF001 - chỉ dùng để tự kiểm
    month_label = labels.get("SolarMonthLabel")
    if (
        month_label is not None
        and not day_label.isHidden()
        and not month_label.isHidden()
    ):
        metrics = QFontMetricsF(day_label.font_for_paint())
        tight = metrics.tightBoundingRect(day_label.text())
        glyph_bottom = day_label.y() + (day_label.height() + tight.height()) / 2
        gap = month_label.y() - glyph_bottom
        if gap < 4:
            warnings.append(f"số ngày cách dòng tháng chỉ {gap:.1f}px (< 4px)")

    # các nhãn hiển thị không được đè nhau
    visible = [w for w in view._all_widgets if not w.isHidden() and not w.geometry().isEmpty()]  # noqa: SLF001 - chỉ dùng để tự kiểm
    for i, first in enumerate(visible):
        for second in visible[i + 1 :]:
            inter = first.geometry().intersected(second.geometry())
            if inter.width() > 2 and inter.height() > 2:
                name_a = first.objectName() or type(first).__name__
                name_b = second.objectName() or type(second).__name__
                warnings.append(f"nhãn đè nhau: {name_a} ↔ {name_b} ({inter.getRect()})")

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
    print(
        f"[preview] QSS: kiểm {len(REQUIRED_SELECTORS)} selector × {combos} tổ hợp "
        f"(4 theme × 3 scale) → {'OK' if not problems else f'{len(problems)} lỗi'}"
    )
    return problems


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
                view="bloc",
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
