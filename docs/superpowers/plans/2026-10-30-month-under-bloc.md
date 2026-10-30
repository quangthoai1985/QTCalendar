# Lịch tháng dưới chân lịch bloc — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép xem cùng lúc lịch bloc và lịch tháng: một tab kéo ở chân bật/tắt lịch tháng hiện ngay dưới tờ bloc, widget dài thêm xuống dưới.

**Architecture:** Thay `QStackedWidget` trong `CalendarWidget` bằng một cột dọc (bloc → khe → lịch tháng → dải đáy). Một widget mới `MonthTab` được đặt tuyệt đối dưới tờ giấy cuối cùng. Trường cấu hình `view` được thay bằng `show_month: bool`; mọi lối vào (tab, nháy đúp, menu chuột phải, khay, Cài đặt) đi về `CalendarWidget.set_show_month()`.

**Tech Stack:** Python 3.14, PySide6 6.11 (QtWidgets), pytest (Qt `offscreen`).

**Spec:** `docs/superpowers/specs/2026-10-30-month-under-bloc-design.md`

## Global Constraints

- Chạy test: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider` (môi trường hiện tại: 507 passed, 7 xfailed trước khi bắt đầu).
- `core/` không được import PySide6.
- Không dùng ký tự tượng hình (▾ ▴ ⋯ ▸ ⚙ …) trong bất kỳ chuỗi hiển thị nào — mũi tên vẽ bằng `QPainter`. Ký tự thiếu glyph làm tốn thêm ~85 MB RAM.
- Lịch tháng vẫn tạo **lười**: chưa mở lần nào thì `CalendarWidget._month is None`.
- `settings.width` / `settings.height` = kích thước widget khi lịch tháng **đóng** (gồm lề bóng). Không chuyển đổi dữ liệu kích thước.
- Hằng số (đặt trong `ui/widget_window.py`): `MONTH_RATIO = 1.15`, `MONTH_GAP_BASE = 6`, `TAB_STRIP_BASE = 12`.
- Chữ trên tab: `"THÁNG"` khi đóng, `"ẨN"` khi mở. Nhãn menu/ô tick: `"Hiện lịch tháng"`; trong hộp thoại Cài đặt: `"Hiện lịch tháng dưới lịch ngày"`.
- `SCHEMA_VERSION = 2`.
- Mở/đóng tức thì, không animation.
- Commit message theo kiểu repo (tiếng Việt không dấu, tiền tố `feat:`/`fix:`/`docs:`), kết thúc bằng dòng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Khởi động với `show_month = True` khi vị trí lưu gần đáy màn hình** — widget phải nằm trọn trong vùng làm việc (Task 5).
2. **Đổi theme / màu nền / độ mờ khi lịch tháng đang mở** — tab và lịch tháng phải đổi màu theo (Task 4).
3. **"Đặt lại kích thước" khi lịch tháng đang mở** — bloc về 344×468, cửa sổ cao `468 + extra_h`, lịch tháng vẫn mở (Task 5).
4. **Bật/tắt lịch tháng khi đang ghim Desktop** — không được gọi `desktop_pin.unpin` (Task 3).
5. **Qua nửa đêm khi đang xem một ngày khác hôm nay** — bỏ chọn, `month.set_selected(None)` (Task 6).

---

### Task 1: Widget `MonthTab`

**Files:**
- Create: `src/qtcalendar/ui/month_tab.py`
- Test: `tests/test_month_tab.py`

**Interfaces:**
- Produces:
  - `class MonthTab(QWidget)` với `toggled = Signal()`
  - `MonthTab.set_open(flag: bool) -> None`; `MonthTab.is_open() -> bool`
  - `MonthTab.label() -> str` — `"THÁNG"` khi đóng, `"ẨN"` khi mở
  - `MonthTab.arrow_points_down() -> bool` — `True` khi đóng
  - `MonthTab.apply_theme(theme: Theme, scale: float) -> None`
  - `MonthTab.sizeHint() -> QSize` — tỉ lệ theo `scale` (gợi ý: rộng `px(78, scale)`, cao `px(22, scale)`); `CalendarWidget` có thể đặt chiều cao cố định khác

- [ ] **Step 1: Viết test hỏng**

`tests/test_month_tab.py` (cùng khung `qapp` fixture, `QT_QPA_PLATFORM=offscreen` như `tests/test_widget_window.py`):

```python
def test_mac_dinh_dong_ghi_thang_mui_ten_xuong(tab):
    assert tab.is_open() is False
    assert tab.label() == "THÁNG"
    assert tab.arrow_points_down() is True

def test_mo_doi_chu_va_mui_ten(tab):
    tab.set_open(True)
    assert tab.label() == "ẨN"
    assert tab.arrow_points_down() is False

def test_bam_chuot_trai_phat_toggled_mot_lan(tab, qapp):
    hits = []
    tab.toggled.connect(lambda: hits.append(1))
    QTest.mouseClick(tab, Qt.LeftButton)
    assert hits == [1]

def test_bam_chuot_phai_khong_phat(tab):
    hits = []
    tab.toggled.connect(lambda: hits.append(1))
    QTest.mouseClick(tab, Qt.RightButton)
    assert hits == []

def test_chu_khong_dung_ky_tu_tuong_hinh(tab):
    for flag in (False, True):
        tab.set_open(flag)
        assert all(ord(ch) < 0x2000 for ch in tab.label())

def test_size_hint_tang_theo_scale(tab):
    from qtcalendar.core.theme import get_theme
    tab.apply_theme(get_theme(None), 1.0)
    nho = tab.sizeHint()
    tab.apply_theme(get_theme(None), 2.0)
    assert tab.sizeHint().width() > nho.width()
    assert tab.sizeHint().height() > nho.height()
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_month_tab.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: qtcalendar.ui.month_tab`

- [ ] **Step 3: Viết `MonthTab` trong `src/qtcalendar/ui/month_tab.py`**

`paintEvent` vẽ một tab giấy: hình chữ nhật bo hai góc dưới (góc trên vuông, chạm mép tờ giấy), nền `theme.paper` → `theme.paper_2`, viền `theme.paper_edge`, nền áp `alpha_of(theme.paper)` như `MonthView.paintEvent`. Chữ dùng `theme.ink_soft` (đổi sang `theme.accent` khi rê chuột), cỡ `px(10, scale)`, `font-weight: 600`, letter-spacing 1. Mũi tên chevron vẽ bằng `QPainterPath` 2 nét bên trái chữ. `setCursor(Qt.PointingHandCursor)`, tooltip `"Hiện lịch tháng"` / `"Ẩn lịch tháng"` theo trạng thái. `mouseReleaseEvent` với nút trái và con trỏ còn trong `rect()` thì phát `toggled`. Theo phong cách docstring tiếng Việt của các file `ui/`.

- [ ] **Step 4: Chạy test, xác nhận qua**

Run: `py -3.14 -X utf8 -m pytest tests/test_month_tab.py -q -p no:cacheprovider`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/qtcalendar/ui/month_tab.py tests/test_month_tab.py
git commit -m "feat(ui): them tab keo MonthTab de bat/tat lich thang"
```

---

### Task 2: `MonthView` — bỏ nút "Ngày", thêm ngày đang chọn

**Files:**
- Modify: `src/qtcalendar/ui/month_view.py` (docstring đầu file ~dòng 45; `_DayCell` ~271–565; `MonthView._build_ui` ~683–707; `_apply_metrics` ~794; `_refresh_footer_text` ~983–1000)
- Modify: `scripts/preview_month.py` (~dòng 26, 225, 315)
- Test: `tests/test_month_view.py` (mới)

**Interfaces:**
- Produces:
  - `MonthView.set_selected(day: date | None) -> None`
  - `MonthView.selected() -> date | None`
  - `_DayCell.set_selected_ref(day: date | None) -> None`; `_DayCell.is_selected() -> bool`
  - Không còn `MonthView.bloc_requested`, không còn `MonthView._btn_bloc`

- [ ] **Step 1: Viết test hỏng**

`tests/test_month_view.py`:

```python
def test_khong_con_nut_ngay_va_tin_hieu_bloc(view):
    assert not hasattr(view, "_btn_bloc")
    assert not hasattr(view, "bloc_requested")

def test_set_selected_danh_dau_dung_mot_o(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 15))
    marked = [c for c in view._cells if c.isVisible() and c.is_selected()]
    assert len(marked) == 1 and marked[0]._info.solar == date(2026, 10, 15)
    assert view.selected() == date(2026, 10, 15)

def test_set_selected_none_bo_danh_dau(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 15))
    view.set_selected(None)
    assert not any(c.is_selected() for c in view._cells)

def test_doi_thang_giu_ngay_chon(view):
    view.set_month(2026, 10)
    view.set_selected(date(2026, 11, 2))
    view.set_month(2026, 11)
    assert any(c.is_selected() and c._info.solar == date(2026, 11, 2) for c in view._cells)

def test_o_hom_nay_khong_tinh_la_dang_chon(view):
    view.set_today(date(2026, 10, 28))
    view.set_month(2026, 10)
    view.set_selected(date(2026, 10, 28))
    cell = next(c for c in view._cells if c._info.solar == date(2026, 10, 28))
    assert cell.is_selected() is False   # hôm nay đã tô đầy, không vẽ thêm viền
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_month_view.py -q -p no:cacheprovider`
Expected: FAIL — `AttributeError: 'MonthView' object has no attribute 'set_selected'`

- [ ] **Step 3: Sửa `month_view.py`**

- Xoá `_btn_bloc`, tín hiệu `bloc_requested`, phần cộng bề rộng `_btn_bloc` trong `_refresh_footer_text`, vòng lặp style trong `_apply_metrics` chỉ còn `_btn_today`; sửa docstring đầu file.
- `_DayCell`: thêm `self._selected: date | None`; `configure(...)` nhận thêm keyword `selected: date | None = None`; `is_selected()` = ngày khớp **và** không phải hôm nay. Trong `paintEvent`, khi `is_selected()` vẽ viền bo tròn liền nét `theme.accent`, dày `max(1.2, 1.5 * scale)`, sau phần nền ô và trước chữ.
- `MonthView`: giữ `self._selected`; `set_month` truyền `selected=self._selected` vào `cell.configure`; `set_selected` gọi `cell.set_selected_ref` cho mọi ô.

- [ ] **Step 4: Sửa `scripts/preview_month.py`**

Bỏ phần kết nối `bloc_requested` và kiểm tra "Nút Ngày" (dòng ~225, ~315) và câu nhắc ở docstring (~26).

- [ ] **Step 5: Chạy test, xác nhận qua**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh (507 + 6 + 5 passed, 7 xfailed). `widget_window._ensure_month` nối `bloc_requested` qua `hasattr` nên không vỡ.

- [ ] **Step 6: Commit**

```bash
git add src/qtcalendar/ui/month_view.py scripts/preview_month.py tests/test_month_view.py
git commit -m "feat(month-view): bo nut Ngay, them danh dau ngay dang xem"
```

---

### Task 3: `show_month` thay `view` + bố cục xếp dọc

Task lớn nhất vì đổi trường cấu hình buộc mọi nơi dùng `settings.view` phải đổi cùng lúc để app vẫn chạy.

**Files:**
- Modify: `src/qtcalendar/core/config.py` (`__all__`, `SCHEMA_VERSION`, `VIEWS`, `Settings`, `clamp`, `from_dict`)
- Modify: `src/qtcalendar/ui/widget_window.py` (`_build_ui`, `content_scale`, `_ensure_month`, `set_view`/`toggle_view`, `_update_overlay_visibility`, `apply_settings`, `_show_menu`, `mouseDoubleClickEvent`, `paintEvent`, `_card_rect`)
- Modify: `src/qtcalendar/platform/tray.py` (signal, `_build_menu` mục 2, `_on_view_action`, `set_state`, docstring bảng tín hiệu)
- Modify: `src/qtcalendar/ui/settings_dialog.py` (`VIEW_LABELS`, `_build_appearance_page`, `_load_from`, `_collect`, `_current_view`)
- Modify: `src/qtcalendar/app.py` (`_wire`, log trong `start`, `_run_smoke`)
- Test: `tests/test_config.py`, `tests/test_widget_window.py`

**Interfaces:**
- Consumes: không.
- Produces:
  - `Settings.show_month: bool = False`; không còn `Settings.view`, không còn `VIEWS`
  - Module-level trong `widget_window.py`:
    - `month_extra_height(width: int, scale: float) -> int` = `styles.px(MONTH_GAP_BASE, scale * width / BASE_WIDTH) + round((width - 2 * SHADOW_MARGIN) * MONTH_RATIO)`
    - `tab_strip_height(content_scale: float) -> int` = `styles.px(TAB_STRIP_BASE, content_scale)`
  - `CalendarWidget.set_show_month(flag: bool) -> None`; `CalendarWidget.toggle_month() -> None`
  - `CalendarWidget.extra_height() -> int` — `month_extra_height(self.width(), settings.scale)` khi `show_month`, ngược lại `0`
  - `CalendarWidget.bloc_height() -> int` = `self.height() - self.extra_height()`
  - `CalendarWidget._sheet_rects() -> list[QRect]` — 1 phần tử khi đóng, 2 khi mở (toạ độ cửa sổ)
  - `TrayIcon.month_toggled = Signal(bool)`; `TrayIcon.action_show_month: QAction | None`

- [ ] **Step 1: Sửa test cấu hình đang dùng `view`, viết test mới (hỏng)**

Trong `tests/test_config.py`: bỏ import `VIEWS`; `test_gia_tri_mac_dinh_hop_le_va_serializable` thay `s.view in VIEWS` bằng `s.show_month is False`; bỏ dòng `("view", "khong_co", "bloc")` khỏi parametrize; `test_bo_qua_khoa_la_va_gia_tri_sai_kieu` đổi `assert s.view == "month"` thành `assert s.show_month is True`; `test_from_dict_voi_du_lieu_rac_khong_no_ra` đổi `assert s.view == "bloc"` thành `assert s.show_month is False`. Thêm:

```python
@pytest.mark.parametrize("raw,ky_vong", [
    ({"view": "month"}, True),
    ({"view": "bloc"}, False),
    ({}, False),
    ({"view": "month", "show_month": False}, False),
    ({"view": "bloc", "show_month": True}, True),
    ({"show_month": "khong-phai-bool"}, False),
])
def test_chuyen_doi_view_cu_sang_show_month(raw, ky_vong):
    assert Settings.from_dict(raw).show_month is ky_vong

def test_khong_con_ghi_khoa_view_va_schema_2():
    raw = Settings().to_dict()
    assert "view" not in raw and raw["show_month"] is False
    assert raw["schema_version"] == 2 == SCHEMA_VERSION
```

Trong `tests/test_widget_window.py` thêm:

```python
def test_mo_lich_thang_cao_them_dung_extra(widget):
    w, h = widget.width(), widget.height()
    widget.set_show_month(True)
    assert widget.width() == w
    assert widget.height() == h + month_extra_height(w, widget._settings.scale)
    assert widget._settings.show_month is True

def test_dong_lich_thang_ve_kich_thuoc_cu(widget):
    widget.set_show_month(True)
    widget.set_show_month(False)
    assert (widget.width(), widget.height()) == (BASE_WIDTH, BASE_HEIGHT)

def test_bat_tat_khong_doi_he_so_phong(widget):
    truoc = widget.content_scale()
    widget.set_show_month(True)
    assert widget.content_scale() == pytest.approx(truoc)
    widget.set_show_month(False)
    assert widget.content_scale() == pytest.approx(truoc)

def test_chua_mo_thi_chua_tao_lich_thang(widget):
    assert widget._month is None

def test_hai_to_giay_khi_mo(widget):
    assert len(widget._sheet_rects()) == 1
    widget.set_show_month(True)
    bloc, month = widget._sheet_rects()
    assert month.top() > bloc.bottom() and month.width() == bloc.width()

def test_nhay_dup_bat_tat_lich_thang(widget, qapp):
    QTest.mouseDClick(widget, Qt.LeftButton, pos=widget.rect().center())
    assert widget._settings.show_month is True

def test_khoi_dong_voi_show_month_true(qapp):
    s = Settings(show_month=True)
    w = CalendarWidget(s)          # app.py không gọi apply_settings lúc khởi động
    assert w._month is not None
    assert w.height() == s.height + month_extra_height(s.width, s.scale)

def test_bat_tat_khi_dang_ghim_khong_bo_ghim(widget, monkeypatch):  # Review Focus 4
    from qtcalendar.ui import widget_window as ww
    calls = []
    for name, fn in (("pin", lambda h: True), ("is_pinned", lambda h: True),
                     ("update_z_order", lambda h: None), ("unpin", lambda h: calls.append(h) or True)):
        monkeypatch.setattr(ww.desktop_pin, name, fn)
    widget.set_placement("desktop")
    calls.clear()
    widget.set_show_month(True)
    widget.set_show_month(False)
    assert calls == []
```

Import thêm ở đầu `tests/test_widget_window.py` (dùng chung cho Task 3–6): `from datetime import date`, `from PySide6.QtCore import QRect, Qt`, `from PySide6.QtTest import QTest`, và `SHADOW_MARGIN`, `month_extra_height` từ `qtcalendar.ui.widget_window`.

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_config.py tests/test_widget_window.py -q -p no:cacheprovider`
Expected: FAIL — `show_month` / `set_show_month` / `month_extra_height` chưa có

- [ ] **Step 3: `core/config.py`**

`SCHEMA_VERSION = 2`; xoá `VIEWS` (và khỏi `__all__`) cùng nhánh `view` trong `clamp`; thay trường `view` bằng `show_month: bool = False` cùng vị trí. Trong `from_dict`, sau vòng ép kiểu: nếu `"show_month"` không có trong `kwargs` (thiếu hoặc sai kiểu đã bị loại) **và** `"show_month"` không có trong `raw` **và** `raw.get("view") == "month"` thì `kwargs["show_month"] = True`. (Có `show_month` nhưng sai kiểu → mặc định `False`, không nhìn `view`.)

- [ ] **Step 4: `ui/widget_window.py` — bố cục và API**

- Hằng số `MONTH_RATIO`, `MONTH_GAP_BASE`, `TAB_STRIP_BASE` (thêm vào `__all__` cùng hai hàm module-level).
- `_build_ui`: bỏ `QStackedWidget` và `_month_placeholder`. Layout dọc, margin `SHADOW_MARGIN`, spacing 0: `self._bloc` (stretch 1) → `self._month_gap` (`QWidget` cao cố định) → chỗ cho `MonthView` (chèn lười ở index 2) → `self._tab_strip` (`QWidget` cao cố định `tab_strip_height(content_scale)`). `_month_gap` ẩn khi đóng.
- Thêm `_apply_sheet_heights()`: đặt chiều cao cố định cho `_month_gap` (`styles.px(MONTH_GAP_BASE, settings.scale * width / BASE_WIDTH)`), `MonthView` (`round((width - 2*SHADOW_MARGIN) * MONTH_RATIO)`), `_tab_strip`. Gọi từ `resizeEvent` và `set_show_month`.
- `content_scale()`: dùng `self.bloc_height()` thay `self.height()`.
- `_ensure_month()`: `MonthView(self)`, chèn vào layout, bỏ phần `bloc_requested`, gọi `month.set_selected(self._selected)`.
- `set_show_month(flag)`: theo spec §5.3 bước 1–6 (Task 5 bổ sung bước 5 "vừa màn hình"). Đổi chiều cao bằng `self.resize(self.width(), settings.height + extra)` sau khi đã ghi `settings.show_month`. Không đụng tới `desktop_pin`.
- `toggle_month()` = `set_show_month(not settings.show_month)`.
- Xoá `set_view` / `toggle_view`; `_view_btn.clicked` nối `toggle_month` (nút này bị bỏ ở Task 4); `_update_overlay_visibility` bỏ điều kiện `view == "bloc"`.
- `__init__`: sau `_start_timers()`, gọi `self.set_show_month(self._settings.show_month)` để khởi động với lịch tháng mở sẵn khi cấu hình yêu cầu.
- `apply_settings`: thay `self.set_view(...)` bằng `self.set_show_month(self._settings.show_month)`; `_resize_to_settings` dùng `settings.height + self.extra_height()` cho chiều cao.
- `_show_menu`: thay menu con "Chế độ xem" bằng một action checkable `"Hiện lịch tháng"` nối `self.set_show_month`.
- `mouseDoubleClickEvent`: gọi `toggle_month()`.
- `_sheet_rects()`: `[self._bloc.geometry()]` + `[self._month.geometry()]` nếu đang mở. `paintEvent` vẽ bóng 6 nét quanh **từng** rect (giữ nguyên công thức hiện có); `_card_rect()` trả hình bao của các rect (dùng cho `_clamp_into_screen`).
- `_on_day_activated` tạm thời bỏ dòng `self.set_view("bloc")` (Task 6 hoàn thiện).

- [ ] **Step 5: `platform/tray.py`**

`view_requested = Signal(str)` → `month_toggled = Signal(bool)`. Mục 2 trong `_build_menu`: một action checkable `"Hiện lịch tháng"` (`self.action_show_month`) nối `_on_month_action(checked)` → phát `month_toggled(bool(checked))` khi `not self._syncing`. Bỏ `_view_group`, `action_view_bloc`, `action_view_month`, `_on_view_action`. `set_state`: `action_show_month.setChecked(bool(getattr(settings, "show_month", False)))`. Sửa bảng tín hiệu trong docstring đầu file.

- [ ] **Step 6: `ui/settings_dialog.py`**

Bỏ `VIEW_LABELS`, `_view_frame`, `_view_group`, `_current_view`. Thêm `self._chk_show_month = self._new_checkbox("Hiện lịch tháng dưới lịch ngày")`, đặt ở hàng form `"Chế độ xem"`. `_load_from`: `setChecked(bool(settings.show_month))`. `_collect`: `settings.show_month = self._chk_show_month.isChecked()`.

- [ ] **Step 7: `app.py`**

`AppController.__init__`: `self._widget.resize(settings.width, settings.height)` → `self._widget.resize(settings.width, settings.height + self._widget.extra_height())` (nếu không, cửa sổ bị cắt mất lịch tháng khi khởi động với `show_month = True`). `_wire`: `tray.month_toggled.connect(w.set_show_month)` thay dòng `view_requested`. Log trong `start`: `view=%s` → `show_month=%s`. `_run_smoke`: `s.show_month = (view == "month")`, thay `widget.set_view(s.view)` bằng `widget.set_show_month(s.show_month)`, payload `"view"` → `"show_month": s.show_month`. Giữ nguyên tham số `--view`.

- [ ] **Step 8: Chạy toàn bộ test**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh. Nếu `test_keo_thu_nho_bi_kep_o_min` đổi giá trị: chiều cao nhỏ nhất giờ có thể là 332 (`BlocView.minimumSizeHint` 300 + 2×10 lề + 12 dải đáy); test đã so với `minimumSizeHint()` nên vẫn qua — không sửa test.

- [ ] **Step 9: Kiểm tra nhanh bằng ảnh**

Run: `py -3.14 -X utf8 run_qtcalendar.pyw --smoke "%TEMP%\qt_bloc.png" --view bloc` và `--view month` (ra `qt_both.png`)
Expected: exit 0; JSON có `"show_month": false` / `true`; `pixels` của ảnh thứ hai cao hơn ảnh thứ nhất đúng `month_extra_height(344, 1.0)`. Mở ảnh xem: hai tờ giấy tách nhau, mỗi tờ có bóng.

- [ ] **Step 10: Commit**

```bash
git add src/qtcalendar/core/config.py src/qtcalendar/ui/widget_window.py src/qtcalendar/platform/tray.py src/qtcalendar/ui/settings_dialog.py src/qtcalendar/app.py tests/test_config.py tests/test_widget_window.py
git commit -m "feat: hien lich thang duoi lich bloc (show_month thay cho view)"
```

---

### Task 4: Gắn `MonthTab` vào widget, bỏ nút nổi "THÁNG"

**Files:**
- Modify: `src/qtcalendar/ui/widget_window.py` (`_build_ui`, `_apply_theme`, `_apply_overlay_style`, `_layout_overlay`, `resizeEvent`, `set_show_month`)
- Test: `tests/test_widget_window.py`

**Interfaces:**
- Consumes: `MonthTab` (Task 1); `set_show_month`, `_sheet_rects`, `tab_strip_height` (Task 3).
- Produces: `CalendarWidget._tab: MonthTab`; `CalendarWidget._layout_tab() -> None`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_tab_dong_cham_mep_duoi_bloc(widget):
    tab = widget._tab
    assert tab.isVisible() and tab.label() == "THÁNG"
    assert tab.geometry().top() == widget._bloc.geometry().bottom() + 1
    assert abs(tab.geometry().center().x() - widget._bloc.geometry().center().x()) <= 1
    assert widget.rect().contains(tab.geometry())

def test_tab_mo_cham_mep_duoi_lich_thang(widget):
    widget.set_show_month(True)
    tab = widget._tab
    assert tab.label() == "ẨN"
    assert tab.geometry().top() == widget._month.geometry().bottom() + 1
    assert widget.rect().contains(tab.geometry())

def test_bam_tab_bat_tat(widget):
    QTest.mouseClick(widget._tab, Qt.LeftButton)
    assert widget._settings.show_month is True
    QTest.mouseClick(widget._tab, Qt.LeftButton)
    assert widget._settings.show_month is False

def test_khong_con_nut_noi_thang(widget):
    assert not hasattr(widget, "_view_btn")

def test_doi_theme_khi_mo_cap_nhat_tab_va_lich_thang(widget):  # Review Focus 2
    widget.set_show_month(True)
    widget.set_theme_name("dem_sao")
    assert widget._tab._theme.name == "dem_sao"
    widget.set_opacity(0.4)
    from qtcalendar.core.theme import alpha_of
    assert alpha_of(widget._tab._theme.paper) == pytest.approx(0.4, abs=0.02)
```

(`MonthTab.apply_theme` lưu theme đã nhận vào `self._theme`; `Theme.name` là mã bảng màu.)

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_widget_window.py -q -p no:cacheprovider`
Expected: FAIL — `AttributeError: '_tab'`

- [ ] **Step 3: Sửa `widget_window.py`**

- `_build_ui`: tạo `self._tab = MonthTab(self)`, nối `toggled` → `toggle_month`; xoá `_view_btn` khỏi overlay (overlay chỉ còn `_menu_btn`).
- `_layout_tab()`: tờ cuối = `_month` nếu đang mở, ngược lại `_bloc`; đặt chiều cao tab = `self.height() - (last.geometry().bottom() + 1)`, bề rộng = `tab.sizeHint().width()`; căn giữa theo tờ cuối; `raise_()`. Gọi từ `resizeEvent`, `showEvent`, `set_show_month`, `_apply_content_scale`, `_apply_theme`.
- `set_show_month` gọi `self._tab.set_open(flag)`.
- `_apply_theme` và `_apply_content_scale` gọi `self._tab.apply_theme(visual, content_scale)`.
- `_apply_overlay_style`: bỏ selector `#ViewSwitch` và vòng lặp chỉ còn `_menu_btn`.

- [ ] **Step 4: Chạy toàn bộ test**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh

- [ ] **Step 5: Kiểm tra ảnh**

Chạy lại hai lệnh `--smoke` của Task 3 Step 9, thêm `--theme dem_sao`. Mở 4 ảnh: tab có chữ đúng, mũi tên đúng hướng, không đè lên câu ca dao/ chân lịch tháng, màu hợp theme tối.

- [ ] **Step 6: Commit**

```bash
git add src/qtcalendar/ui/widget_window.py tests/test_widget_window.py
git commit -m "feat(ui): gan tab keo vao chan widget, bo nut noi THANG"
```

---

### Task 5: Kéo giãn khi đang mở, vừa màn hình, lưu kích thước bloc

**Files:**
- Modify: `src/qtcalendar/ui/widget_window.py` (`begin_resize`, `drag_resize`, `end_resize`, `reset_size`, `_store_geometry`, `_clamp_into_screen`, `restore_position`, `set_show_month`, `_show_menu` mục "Đặt lại kích thước")
- Test: `tests/test_widget_window.py`

**Interfaces:**
- Consumes: `extra_height()`, `bloc_height()`, `set_show_month` (Task 3).
- Produces: `CalendarWidget._available_rect() -> QRect | None` (vùng làm việc của màn hình chứa widget; test monkeypatch hàm này); `CalendarWidget._fit_into_screen() -> None`.

- [ ] **Step 1: Viết test hỏng**

```python
def _gia_man_hinh(monkeypatch, widget, rect):
    monkeypatch.setattr(widget, "_available_rect", lambda: QRect(*rect))

def test_keo_khi_mo_luu_kich_thuoc_bloc(widget):
    widget.set_show_month(True)
    widget.begin_resize(QPoint(0, 0))
    widget.drag_resize(QPoint(60, 40))
    widget.end_resize()
    assert widget._settings.width == BASE_WIDTH + 60
    assert widget._settings.height == BASE_HEIGHT + 40
    assert widget.height() == widget._settings.height + month_extra_height(widget.width(), widget._settings.scale)

def test_cham_day_man_hinh_thi_doi_len(widget, monkeypatch):
    _gia_man_hinh(monkeypatch, widget, (0, 0, 1920, 1040))
    widget.move(100, 600)
    widget.set_show_month(True)
    assert widget.frameGeometry().bottom() - SHADOW_MARGIN <= 1039
    assert widget._settings.width == BASE_WIDTH        # chỉ dời, không thu nhỏ

def test_cao_hon_man_hinh_thi_thu_nho(widget, monkeypatch):
    _gia_man_hinh(monkeypatch, widget, (0, 0, 1366, 700))
    widget.move(100, 0)
    widget.set_show_month(True)
    assert widget.height() - 2 * SHADOW_MARGIN <= 700
    assert widget._settings.width < BASE_WIDTH
    assert widget._settings.width / widget._settings.height == pytest.approx(BASE_WIDTH / BASE_HEIGHT, rel=0.03)

def test_dat_lai_kich_thuoc_khi_mo(widget):  # Review Focus 3
    widget.set_show_month(True)
    widget.resize(500, 1200)
    widget.reset_size()
    assert widget._settings.show_month is True
    assert (widget._settings.width, widget._settings.height) == (BASE_WIDTH, BASE_HEIGHT)
    assert widget.height() == BASE_HEIGHT + month_extra_height(BASE_WIDTH, widget._settings.scale)

def test_khoi_dong_mo_san_gan_day_van_vua_man_hinh(qapp, monkeypatch):  # Review Focus 1
    s = Settings(show_month=True, x=100, y=900)
    w = CalendarWidget(s)
    monkeypatch.setattr(w, "_available_rect", lambda: QRect(0, 0, 1920, 1040))
    w.restore_position()           # đúng thứ tự AppController.start()
    assert w.pos().y() + w.height() - SHADOW_MARGIN <= 1040
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_widget_window.py -q -p no:cacheprovider`
Expected: FAIL — `_available_rect` chưa có / kích thước lưu sai

- [ ] **Step 3: Sửa `widget_window.py`**

- `_available_rect()`: `(self.screen() or QGuiApplication.primaryScreen()).availableGeometry()`, `None` nếu không có màn hình. `_clamp_into_screen` và `drag_resize` dùng hàm này.
- `drag_resize`: tính trên kích thước **bloc** — `bloc_h = start_bloc_h + delta.y` kẹp `[min_h, MAX_HEIGHT]`, `width` kẹp như cũ; giới hạn thêm `bloc_h + month_extra_height(width, scale) ≤ avail.height() - 2*SHADOW_MARGIN` khi đang mở; `resize(width, bloc_h + extra)`. `begin_resize` ghi `_resize_start_size = QSize(self.width(), self.bloc_height())`.
- `_store_geometry`: `settings.height = self.bloc_height()` (nhánh ghim: chiều cao từ `GetWindowRect` trừ `extra_height()`).
- `_fit_into_screen()`: nếu `self.height() - 2*SHADOW_MARGIN > avail.height()` thì tìm `f` sao cho `round(h*f) + month_extra_height(round(w*f), scale) + 2*SHADOW_MARGIN ≤ avail.height()` (giảm dần `f` theo bước 0,01, dừng ở cỡ `_min_size()`), resize, `_store_geometry()`; sau đó `_clamp_into_screen()`. Gọi ở cuối `set_show_month(True)` và trong `restore_position` khi `show_month`.
- `reset_size`: `resize(BASE_WIDTH, BASE_HEIGHT + self.extra_height())` với `extra_height` tính cho `BASE_WIDTH`, rồi như cũ.
- `_show_menu`: mục "Đặt lại kích thước" enable khi `(settings.width, settings.height) != (BASE_WIDTH, BASE_HEIGHT)`.

- [ ] **Step 4: Chạy toàn bộ test**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh (các test kéo giãn cũ chạy ở trạng thái đóng nên không đổi)

- [ ] **Step 5: Commit**

```bash
git add src/qtcalendar/ui/widget_window.py tests/test_widget_window.py
git commit -m "feat(ui): keo gian va vua man hinh khi lich thang dang mo"
```

---

### Task 6: Bấm ngày trong lịch tháng — giữ lịch tháng mở, đánh dấu ngày đang xem

**Files:**
- Modify: `src/qtcalendar/ui/widget_window.py` (`_on_day_activated`, `go_today`, `_on_new_day`)
- Test: `tests/test_widget_window.py`

**Interfaces:**
- Consumes: `MonthView.set_selected`, `MonthView.selected` (Task 2); `set_show_month` (Task 3).

- [ ] **Step 1: Viết test hỏng**

```python
def test_bam_ngay_doi_bloc_va_giu_lich_thang(widget):
    widget.set_show_month(True)
    widget._on_day_activated(date(2026, 10, 15))
    assert widget._settings.show_month is True
    assert widget._bloc.current_day().solar == date(2026, 10, 15)
    assert widget._month.selected() == date(2026, 10, 15)

def test_ve_hom_nay_bo_chon(widget):
    widget.set_show_month(True)
    widget._on_day_activated(date(2026, 10, 15))
    widget.go_today()
    assert widget._month.selected() is None

def test_qua_nua_dem_bo_chon(widget):  # Review Focus 5
    widget.set_show_month(True)
    widget._on_day_activated(date(2026, 10, 15))
    widget._midnight_timer.stop()
    widget._on_new_day()
    assert widget._selected is None and widget._month.selected() is None
```

- [ ] **Step 2: Chạy test, xác nhận hỏng**

Run: `py -3.14 -X utf8 -m pytest tests/test_widget_window.py -q -p no:cacheprovider`
Expected: FAIL — `selected()` vẫn `None` / không bỏ chọn

- [ ] **Step 3: Sửa `widget_window.py`**

`_on_day_activated`: đặt `_selected` như cũ, `_refresh_content()`, rồi `self._month.set_selected(self._selected)` nếu `_month` đã có; không đổi `show_month`. `go_today` và `_on_new_day`: sau khi xoá `_selected`, gọi `self._month.set_selected(None)` nếu có. `_ensure_month` đã truyền `_selected` từ Task 3.

- [ ] **Step 4: Chạy toàn bộ test**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh

- [ ] **Step 5: Commit**

```bash
git add src/qtcalendar/ui/widget_window.py tests/test_widget_window.py
git commit -m "feat(ui): bam ngay trong lich thang giu lich mo va danh dau ngay dang xem"
```

---

### Task 7: Tài liệu và kiểm tra cuối

**Files:**
- Modify: `README.md` (bảng tính năng "Lịch tháng", bảng "Thao tác" dòng nháy đúp và nút nổi, số test)
- Modify: `docs/01-kien-truc.md` (yêu cầu F10, sơ đồ timer/bố cục nếu nhắc `QStackedWidget`)
- Modify: `docs/03-tung-buoc-code.md` (§10 / §11 đoạn nói chuyển view và `QStackedWidget`)
- Modify: `docs/05-kiem-thu-va-dong-goi.md` (bảng test: thêm `test_month_tab.py`, `test_month_view.py`; số liệu; checklist phát hành thêm "bấm tab mở/đóng lịch tháng")

- [ ] **Step 1: Tìm chỗ cần sửa**

Run: `grep -rn "QStackedWidget\|set_view\|toggle_view\|Chế độ xem\|Nháy đúp\|THÁNG\|lịch tháng" README.md docs/0*.md`
Expected: danh sách các dòng mô tả cách chuyển chế độ cũ

- [ ] **Step 2: Sửa các dòng đó cho khớp spec §2**

Mô tả: tab kéo ở chân, hai lịch xếp dọc, nháy đúp bật/tắt lịch tháng, ô tick "Hiện lịch tháng" trong menu/khay/Cài đặt, bấm ngày giữ lịch tháng mở.

- [ ] **Step 3: Kiểm tra cuối**

Run: `py -3.14 -X utf8 -m pytest tests -q -p no:cacheprovider`
Expected: toàn bộ xanh; ghi số passed thật vào README và docs/05.

Run: `--smoke` 4 ảnh (2 trạng thái × `giay_do`/`dem_sao`) và thêm cỡ nhỏ nhất: tạo `settings.json` tạm với `"width": 260, "height": 330, "show_month": true` qua biến môi trường `QTCALENDAR_CONFIG`, chạy `--smoke`. Mở ảnh: không chữ nào bị cắt ở bloc và lịch tháng, tab không đè nội dung.

Thử tay (ghi kết quả vào tin nhắn bàn giao, không tự khẳng định nếu chưa thử được): ghim Desktop, mở/đóng lịch tháng, bấm `Win + D`, kéo giãn khi đang mở.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/01-kien-truc.md docs/03-tung-buoc-code.md docs/05-kiem-thu-va-dong-goi.md
git commit -m "docs: cap nhat tai lieu cho lich thang duoi lich bloc"
```
