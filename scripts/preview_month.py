"""Render ảnh xem trước cho lịch tháng và hộp thoại cài đặt.

Chạy::

    $env:PYTHONUTF8="1"
    python -X utf8 scripts/preview_month.py

Kết quả nằm trong ``preview/`` (script tự dọn ảnh cũ do chính nó sinh ra):

* ``month_<YYYY-MM>_<theme>_<app|nho|vua>.png`` – 3 tháng × 2 theme × 3 cỡ:
  - ``app``: 344×468 – đúng kích thước cửa sổ widget mặc định;
  - ``nho``: 382×548;
  - ``vua``: 500×700 (scale nội dung 1.2).
  Ba tháng: 10/2026 (có hôm nay), 3/2023 (tháng Hai nhuận),
  2/2026 (Tết Nguyên Đán Bính Ngọ).
* ``month_2026-10_giay_do_app-phong.png`` – cửa sổ mặc định, scale 1.4
  (kiểm tra chữ header/footer không tràn khi người dùng phóng nội dung).
* ``settings.png`` – hộp thoại cài đặt, thẻ "Giao diện", theme Giấy đỏ.
* ``settings_cua_so.png`` / ``settings_nang_cao.png`` – hai thẻ còn lại.
* ``settings_dem_sao.png`` – theme Đêm sao, độ mờ 70 %, cỡ 120 %.
* ``settings_mau_nen_sang.png`` – nền giấy tuỳ chọn sáng (``#EAF4EE``).
* ``settings_mau_nen_toi.png`` – nền giấy tuỳ chọn tối (``#141A22``; mực tự
  chuyển sang màu sáng để chữ vẫn đọc được).

Script cũng tự kiểm nhanh hợp đồng API (đổi tháng, bấm ô ngày, nút Hôm nay,
số hàng lưới 5–6, hộp thoại chỉ sửa trên bản
sao, ``lunar_engine`` lưu được, chọn swatch màu nền ↔ ``Settings.bg_color``,
``SettingsDialog.edit`` trả ``None`` khi Huỷ) và in báo cáo. Mã trả về khác 0
nếu có lỗi.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Render offline: không cần màn hình, nhưng vẫn phải nạp font Windows.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6.QtCore import QPoint, QSize, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QWidget,
)

from qtcalendar.core.config import Settings  # noqa: E402
from qtcalendar.core.theme import get_theme, with_background  # noqa: E402
from qtcalendar.ui.month_view import MonthView  # noqa: E402
from qtcalendar.ui.settings_dialog import SettingsDialog  # noqa: E402

PREVIEW_DIR = ROOT / "preview"

#: Ngày "hôm nay" cố định để ảnh xem trước luôn giống nhau giữa mọi lần chạy.
TODAY = date(2026, 10, 28)

#: (năm, tháng, hậu tố tên tệp, ghi chú).
MONTHS = (
    (2026, 10, "2026-10", "Tháng 10/2026 – có ngày hôm nay"),
    (2023, 3, "2023-03", "Tháng 3/2023 – tháng Hai nhuận"),
    (2026, 2, "2026-02", "Tháng 2/2026 – Tết Nguyên Đán Bính Ngọ"),
)

THEMES_PREVIEW = ("giay_do", "dem_sao")

#: Kích thước lưới tháng: (rộng, cao, scale nội dung).
SIZES: dict[str, tuple[int, int, float]] = {
    "app": (344, 468, 1.0),
    "nho": (382, 548, 1.0),
    "vua": (500, 700, 1.2),
}

MIN_PNG_BYTES = 3_000

#: Tháng kiểm tra số hàng lưới.
ROW_CASES = ((2026, 10, 5), (2027, 2, 5), (2026, 8, 6))


# --------------------------------------------------------------------------- #
# Dọn ảnh cũ
# --------------------------------------------------------------------------- #
def clean_previous_outputs() -> list[Path]:
    """Xoá ảnh do script sinh ở lần chạy trước và file nháp ``_*``."""
    removed: list[Path] = []
    if not PREVIEW_DIR.is_dir():
        return removed
    for path in PREVIEW_DIR.iterdir():
        if not path.is_file():
            continue
        name = path.name
        stale = (
            (name.startswith("month_") and name.endswith(".png"))
            or (name.startswith("settings") and name.endswith(".png"))
            or name.startswith("_")
        )
        if stale:
            try:
                path.unlink()
                removed.append(path)
            except OSError:  # pragma: no cover - file đang mở
                pass
    return removed


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render_month(
    app: QApplication,
    year: int,
    month: int,
    theme_name: str,
    size_key: str,
    *,
    filename: str | None = None,
    scale: float | None = None,
) -> tuple[Path, QSize, int]:
    """Render một lưới tháng ra PNG, trả (đường dẫn, kích thước, số byte)."""
    width, height, default_scale = SIZES[size_key]
    view = MonthView()
    view.apply_theme(
        get_theme(theme_name), default_scale if scale is None else scale
    )
    view.set_today(TODAY)
    view.set_month(year, month)
    view.set_show_lunar(True)
    view.resize(width, height)
    view.show()
    app.processEvents()

    actual = view.size()
    pixmap = view.grab()
    name = filename or f"month_{year}-{month:02d}_{theme_name}_{size_key}.png"
    path = PREVIEW_DIR / name
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Không ghi được ảnh: {path}")
    size = path.stat().st_size
    view.close()
    view.deleteLater()
    app.processEvents()
    return path, actual, size


def render_settings(
    app: QApplication,
    theme_name: str,
    filename: str,
    *,
    tab_index: int = 0,
    opacity_percent: int = 100,
    scale_percent: int = 100,
    bg_color: str = "",
) -> tuple[Path, QSize, int]:
    """Render một thẻ của hộp thoại cài đặt ra PNG."""
    settings = Settings(
        theme=theme_name,
        opacity=1.0,
        scale=1.0,
        view="month",
        show_quote=True,
        show_auspicious=True,
        show_tiet_khi=True,
        bg_color=bg_color,
    )
    dialog = SettingsDialog(settings, autostart_available=True)
    dialog.show()
    app.processEvents()
    # Đặt giá trị qua đúng API công khai mà người dùng thao tác.
    if opacity_percent != 100:
        dialog.findChildren(QSlider)[0].setValue(opacity_percent)
    if scale_percent != 100:
        dialog.findChildren(QSlider)[1].setValue(scale_percent)
    tabs = dialog.findChild(QTabWidget, "SettingsTabs")
    if tabs is not None:
        tabs.setCurrentIndex(tab_index)
    app.processEvents()

    actual = dialog.size()
    pixmap = dialog.grab()
    path = PREVIEW_DIR / filename
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Không ghi được ảnh: {path}")
    size = path.stat().st_size
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
    return path, actual, size


# --------------------------------------------------------------------------- #
# Tự kiểm hợp đồng API
# --------------------------------------------------------------------------- #
def check_month_view(app: QApplication) -> list[str]:
    problems: list[str] = []
    view = MonthView()
    view.apply_theme(get_theme("xanh_ngoc"), 1.0)
    view.set_today(TODAY)
    view.set_month(2026, 10)
    view.resize(344, 468)
    view.show()
    app.processEvents()

    months: list[tuple[int, int]] = []
    days: list[date] = []
    today_hits: list[int] = []
    view.month_changed.connect(lambda y, m: months.append((y, m)))
    view.day_activated.connect(lambda d: days.append(d))
    view.today_requested.connect(lambda: today_hits.append(1))

    if view.current_month() != (2026, 10):
        problems.append(
            f"current_month() sai: {view.current_month()} != (2026, 10)"
        )

    title = view.findChild(QLabel, "MonthTitleLabel")
    if title is None or title.text() != "Tháng 10 / 2026":
        problems.append("Tiêu đề tháng sai hoặc bị rỗng")
    elif title.width() <= 0:
        problems.append("Tiêu đề tháng có bề ngang 0")
    subtitle = view.findChild(QLabel, "MonthSubtitleLabel")
    if subtitle is None or "Tháng Chín" not in subtitle.text():
        problems.append("Dòng phụ âm lịch sai hoặc bị rỗng")

    # Số hàng lưới: 5–6 hàng, không có hàng "chết" bị cắt.
    for year, month, expected in ROW_CASES:
        view.set_month(year, month)
        app.processEvents()
        if view.visible_rows() != expected:
            problems.append(
                f"{year}-{month:02d}: {view.visible_rows()} hàng,"
                f" mong đợi {expected}"
            )
        visible = [
            cell
            for cell in view.findChildren(QWidget, "DayCell")
            if cell.isVisible()
        ]
        if len(visible) != expected * 7:
            problems.append(
                f"{year}-{month:02d}: {len(visible)} ô hiển thị,"
                f" mong đợi {expected * 7}"
            )
    view.set_month(2026, 10)
    app.processEvents()

    # Header/footer không bị tràn ở kích thước cửa sổ mặc định thật.
    view.resize(324, 448)
    app.processEvents()
    footer = view.findChild(QLabel, "FooterInfoLabel")
    if footer is None or not footer.text():
        problems.append("Chú thích chân rỗng")
    elif footer.fontMetrics().horizontalAdvance(footer.text()) > footer.width() + 1:
        problems.append("Chú thích chân bị tràn bề ngang")
    view.resize(344, 468)
    app.processEvents()

    view.step_month(1)
    if view.current_month() != (2026, 11):
        problems.append(f"step_month(+1) sai: {view.current_month()}")
    if not months or months[-1] != (2026, 11):
        problems.append(f"month_changed sau step_month(+1) sai: {months[-1:]!r}")
    view.step_month(-2)
    if view.current_month() != (2026, 9):
        problems.append(f"step_month(-2) sai: {view.current_month()}")
    view.go_today()
    if view.current_month() != (2026, 10):
        problems.append(f"go_today() sai: {view.current_month()}")

    # Bấm thử một ô ngày ở giữa lưới bằng sự kiện chuột thật.
    point = QPoint(view.width() // 2, int(view.height() * 0.55))
    cell = view.childAt(point)
    if cell is None:
        problems.append("Không tìm thấy ô ngày tại điểm bấm thử")
    else:
        QTest.mouseClick(cell, Qt.MouseButton.LeftButton)
        app.processEvents()
        if not days:
            problems.append("Bấm ô ngày nhưng day_activated không phát")
        elif (days[-1].year, days[-1].month) != (2026, 10):
            problems.append(f"day_activated phát ngày ngoài lưới: {days[-1]}")

    today_button = view.findChild(QPushButton, "TodayButton")
    if today_button is None:
        problems.append("Không tìm thấy nút Hôm nay")
    else:
        today_button.click()
        app.processEvents()
        if not today_hits:
            problems.append("Nút Hôm nay không phát today_requested")

    view.set_show_lunar(False)
    view.set_show_lunar(True)
    view.close()
    view.deleteLater()
    app.processEvents()
    return problems


def check_settings_dialog(app: QApplication) -> list[str]:
    problems: list[str] = []
    base = Settings(theme="giay_do", opacity=1.0, scale=1.0, view="bloc")
    snapshot = base.to_dict()

    dialog = SettingsDialog(base, autostart_available=True)
    dialog.show()
    app.processEvents()
    if base.to_dict() != snapshot:
        problems.append("Settings gốc bị hộp thoại sửa trực tiếp")

    tabs = dialog.findChild(QTabWidget, "SettingsTabs")
    if tabs is None or tabs.count() != 3:
        problems.append(
            f"Hộp thoại phải có 3 thẻ, đang có {getattr(tabs, 'count', lambda: 0)()}"
        )
    else:
        for index in range(tabs.count()):
            if tabs.widget(index) is None:
                problems.append(f"Thẻ {index} không dựng được nội dung")

    # Đổi theme + slider qua API công khai của dialog.
    dialog.set_theme_preview(get_theme("dem_sao"))
    sliders = dialog.findChildren(QSlider)
    if len(sliders) < 2:
        problems.append(f"Thiếu slider trong hộp thoại (có {len(sliders)})")
    else:
        sliders[0].setValue(60)  # độ trong suốt
        sliders[1].setValue(130)  # cỡ nội dung
    app.processEvents()

    # Thuật toán âm lịch phải lưu được vào Settings.
    engine_combo = None
    for combo in dialog.findChildren(QComboBox):
        values = [combo.itemData(i) for i in range(combo.count())]
        if "precise" in values and "hnd" in values:
            engine_combo = combo
            break
    if engine_combo is not None:
        engine_combo.setCurrentIndex(engine_combo.findData("hnd"))
        app.processEvents()

    current = dialog.settings()
    if current.theme != "dem_sao":
        problems.append(f"settings().theme sai: {current.theme!r}")
    if abs(current.opacity - 0.60) > 1e-6:
        problems.append(f"settings().opacity sai: {current.opacity!r}")
    if abs(current.scale - 1.30) > 1e-6:
        problems.append(f"settings().scale sai: {current.scale!r}")
    if engine_combo is not None and current.lunar_engine != "hnd":
        problems.append(
            f"settings().lunar_engine sai: {current.lunar_engine!r}"
        )

    path_label = None
    for label in dialog.findChildren(QLabel):
        if label.objectName() == "PathLabel":
            path_label = label
            break
    if path_label is None or "settings" not in path_label.toolTip().lower():
        problems.append("Thiếu nhãn đường dẫn settings.json")

    # Màu nền giấy: swatch ↔ Settings.bg_color; nền tối tự chuyển mực sáng.
    swatches = dialog.findChildren(QPushButton, "BgSwatch")
    if len(swatches) != 10:
        problems.append(f"Phải có 10 swatch màu nền, đang có {len(swatches)}")
    if dialog.findChild(QPushButton, "BgPickButton") is None:
        problems.append("Thiếu nút Màu tuỳ chọn…")
    if dialog.findChild(QPushButton, "BgThemeButton") is None:
        problems.append("Thiếu nút Theo giao diện")
    dark_swatch = next(
        (item for item in swatches if item.property("color") == "#141A22"), None
    )
    if dark_swatch is None:
        problems.append("Thiếu swatch nền tối #141A22")
    else:
        dark_swatch.click()
        app.processEvents()
        if dialog.settings().bg_color != "#141A22":
            problems.append(
                f"Chọn nền tối không lưu được: {dialog.settings().bg_color!r}"
            )
        if "#141A22" not in dialog.styleSheet().upper():
            problems.append("Hộp thoại chưa áp màu nền tối vào QSS")
        if not dark_swatch.isChecked():
            problems.append("Swatch đang chọn chưa được đánh dấu")
    theme_button = dialog.findChild(QPushButton, "BgThemeButton")
    if theme_button is not None:
        theme_button.click()
        app.processEvents()
        if dialog.settings().bg_color != "":
            problems.append(
                "Nút Theo giao diện không reset bg_color:"
                f" {dialog.settings().bg_color!r}"
            )
    dark_visual = with_background(get_theme("giay_do"), "#141A22")
    if not dark_visual.dark:
        problems.append("with_background(#141A22) không đánh dấu là nền tối")
    elif QColor(dark_visual.ink).lightnessF() <= QColor(
        dark_visual.paper
    ).lightnessF():
        problems.append("Nền tối nhưng mực không sáng hơn nền")

    # "Đặt lại mặc định" phải reset cả bg_color về "".
    reset_button = next(
        (
            button
            for button in dialog.findChildren(QPushButton)
            if button.text() == "Đặt lại mặc định"
        ),
        None,
    )
    if reset_button is None:
        problems.append("Thiếu nút Đặt lại mặc định")
    else:
        reset_button.click()
        app.processEvents()
        if dialog.settings().bg_color != "":
            problems.append(
                "Đặt lại mặc định không reset bg_color:"
                f" {dialog.settings().bg_color!r}"
            )

    if base.to_dict() != snapshot:
        problems.append("Settings gốc bị thay đổi sau khi collect")
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

    # edit() phải trả Settings khi bấm Lưu.
    def _accept_modal() -> None:
        widget = QApplication.activeModalWidget()
        if isinstance(widget, SettingsDialog):
            widget._btn_save.click()  # noqa: SLF001 - QA

    QTimer.singleShot(30, _accept_modal)
    saved = SettingsDialog.edit(base)
    if saved is None:
        problems.append("SettingsDialog.edit() trả None dù bấm Lưu")
    elif saved.theme != base.theme:
        problems.append("SettingsDialog.edit() trả cấu hình bất thường")

    # edit() phải trả None khi bấm Huỷ.
    def _reject_modal() -> None:
        widget = QApplication.activeModalWidget()
        if isinstance(widget, SettingsDialog):
            widget._btn_cancel.click()  # noqa: SLF001 - QA

    QTimer.singleShot(30, _reject_modal)
    cancelled = SettingsDialog.edit(base)
    if cancelled is not None:
        problems.append("SettingsDialog.edit() không trả None khi Huỷ")
    return problems


def check_png(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.is_file():
        return [f"Thiếu ảnh: {path}"]
    size = path.stat().st_size
    if size < MIN_PNG_BYTES:
        problems.append(f"Ảnh quá nhỏ ({size} byte): {path.name}")
    return problems


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    removed = clean_previous_outputs()
    app = QApplication(sys.argv)
    app.setApplicationName("QT Calendar Preview")

    problems: list[str] = []
    rendered: list[tuple[Path, QSize, int]] = []

    print(f"== Dọn {len(removed)} ảnh cũ ==")
    print("== Render lịch tháng ==")
    for year, month, _suffix, note in MONTHS:
        for theme_name in THEMES_PREVIEW:
            for size_key in ("app", "nho", "vua"):
                path, actual, size = render_month(
                    app, year, month, theme_name, size_key
                )
                rendered.append((path, actual, size))
                print(
                    f"  {path.name:48s} {actual.width()}x{actual.height()}"
                    f"  {size / 1024:6.1f} KB   ({note})"
                )
    # Kiểm tra thêm: cùng cửa sổ mặc định nhưng scale nội dung 1.4.
    path, actual, size = render_month(
        app,
        2026,
        10,
        "giay_do",
        "app",
        filename="month_2026-10_giay_do_app-phong.png",
        scale=1.4,
    )
    rendered.append((path, actual, size))
    print(
        f"  {path.name:48s} {actual.width()}x{actual.height()}"
        f"  {size / 1024:6.1f} KB   (cửa sổ mặc định, scale 1.4)"
    )
    # Tháng 6 hàng và tháng chỉ 4 tuần (đệm thành 5) – kiểm tra lưới vừa khít.
    for year, month, note in (
        (2026, 8, "tháng 6 hàng"),
        (2027, 2, "tháng 4 tuần – đệm thành 5 hàng"),
    ):
        path, actual, size = render_month(
            app,
            year,
            month,
            "giay_do",
            "app",
            filename=f"month_{year}-{month:02d}_giay_do_app.png",
        )
        rendered.append((path, actual, size))
        print(
            f"  {path.name:48s} {actual.width()}x{actual.height()}"
            f"  {size / 1024:6.1f} KB   ({note})"
        )

    print("== Render hộp thoại cài đặt ==")
    settings_jobs = (
        ("giay_do", "settings.png", 0, 100, 100, "", "thẻ Giao diện"),
        ("giay_do", "settings_cua_so.png", 1, 100, 100, "", "thẻ Cửa sổ"),
        ("giay_do", "settings_nang_cao.png", 2, 100, 100, "", "thẻ Nâng cao"),
        (
            "dem_sao",
            "settings_dem_sao.png",
            0,
            70,
            120,
            "",
            "theme tối, mờ 70 %, cỡ 120 %",
        ),
        (
            "giay_do",
            "settings_mau_nen_sang.png",
            0,
            100,
            100,
            "#EAF4EE",
            "nền giấy tuỳ chọn sáng #EAF4EE",
        ),
        (
            "giay_do",
            "settings_mau_nen_toi.png",
            0,
            100,
            100,
            "#141A22",
            "nền giấy tuỳ chọn tối #141A22 (mực tự sáng)",
        ),
    )
    for (
        theme_name,
        filename,
        tab_index,
        opacity,
        scale,
        bg_color,
        note,
    ) in settings_jobs:
        path, actual, size = render_settings(
            app,
            theme_name,
            filename,
            tab_index=tab_index,
            opacity_percent=opacity,
            scale_percent=scale,
            bg_color=bg_color,
        )
        rendered.append((path, actual, size))
        print(
            f"  {path.name:48s} {actual.width()}x{actual.height()}"
            f"  {size / 1024:6.1f} KB   ({note})"
        )

    print("== Tự kiểm hợp đồng API ==")
    for name, checker in (
        ("MonthView", check_month_view),
        ("SettingsDialog", check_settings_dialog),
    ):
        found = checker(app)
        if found:
            problems.extend(f"{name}: {message}" for message in found)
            for message in found:
                print(f"  [LỖI] {name}: {message}")
        else:
            print(f"  [OK ] {name}")

    for path, _size, _bytes in rendered:
        problems.extend(check_png(path))

    total_bytes = sum(item[2] for item in rendered)
    print("== Tổng kết ==")
    print(f"  Ảnh: {len(rendered)} tệp · {total_bytes / 1024:.1f} KB")
    print(f"  Thư mục: {PREVIEW_DIR}")
    if problems:
        print(f"  CÓ {len(problems)} LỖI:")
        for problem in problems:
            print(f"   - {problem}")
        return 1
    print("  Không phát hiện lỗi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
