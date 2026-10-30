# Lịch tháng hiện dưới chân lịch bloc — Thiết kế

- **Ngày**: 2026-10-30
- **Trạng thái**: chờ duyệt
- **Phiên bản áp dụng**: sau 1.0.2

## 1. Mục tiêu

Người dùng xem được **cùng lúc** lịch bloc (ngày) và lịch tháng. Nút chuyển
lịch tháng được thiết kế lại cho dễ thấy, dễ bấm: bật lên thì lịch tháng hiện
ngay dưới chân tờ bloc, tắt đi thì widget trở về như cũ.

### Đã thống nhất với người dùng

| Câu hỏi | Quyết định |
|---|---|
| Các chế độ xem | Chỉ còn **Bloc** và **Bloc + tháng**. Bỏ chế độ chỉ có lịch tháng |
| Kích thước khi bật | Widget **dài thêm xuống dưới**, bloc giữ nguyên cỡ |
| Nút bật/tắt | **Tab kéo** luôn hiện, treo ở giữa mép dưới |

### Tiêu chí thành công

1. Bấm tab một lần thấy cả hai lịch; bấm lần nữa widget về đúng kích thước cũ.
2. Chữ trên bloc không đổi cỡ khi bật/tắt lịch tháng.
3. Người đang dùng bản cũ không thấy widget đổi cỡ sau khi cập nhật (khung
   cửa sổ giữ nguyên `width × height`; chỉ phần bloc nhường khoảng 12 px ở đáy
   cho tab, xem §4.2).
4. Không tốn thêm RAM nếu người dùng chưa từng mở lịch tháng.
5. Hoạt động cả khi ghim Desktop lẫn khi là cửa sổ nổi.

### Ngoài phạm vi

- Hiệu ứng trượt khi mở/đóng.
- Chế độ chỉ có lịch tháng.
- Đặt lịch tháng bên cạnh (ngang) lịch bloc.

## 2. Trải nghiệm người dùng

### 2.1 Tab kéo

- Tab giấy nhỏ, luôn hiện, nằm giữa mép dưới tờ bloc, ghi `THÁNG` kèm mũi tên
  chỉ xuống.
- Mũi tên **vẽ tay bằng QPainter**, không dùng ký tự tượng hình (▾, ▴…): dự
  án đã đo được ký tự thiếu glyph có thể làm DirectWrite nạp font dự phòng,
  tốn thêm khoảng 85 MB RAM.
- Có tooltip, con trỏ bàn tay, đổi màu nhẹ khi rê chuột. Màu theo theme đang
  dùng (cả 4 theme và màu nền tuỳ chọn).

### 2.2 Bật / tắt

- Bấm tab: lịch tháng hiện ngay dưới bloc, cùng bề ngang, trông như tờ giấy
  thứ hai. Tab chuyển xuống chân lịch tháng và đổi thành `ẨN` với mũi tên chỉ
  lên.
- Bấm lần nữa: lịch tháng đóng, widget về đúng kích thước cũ.
- Mở/đóng **tức thì**, không animation, vì đổi chiều cao liên tục trên cửa sổ
  trong suốt dễ gây nháy, nhất là khi đang ghim Desktop.

### 2.3 Tương tác trong lịch tháng

- Bấm một ngày: tờ bloc phía trên chuyển sang ngày đó; lịch tháng **vẫn mở**;
  ô của ngày đang xem được viền nhấn (khác với ô hôm nay vốn tô đầy màu).
- Nút `Hôm nay` ở chân lịch tháng: đưa cả hai lịch về hôm nay.
- Nút `Ngày` ở chân lịch tháng: **bỏ**.

### 2.4 Các lối vào khác

| Lối vào | Hành vi mới |
|---|---|
| Nháy đúp vào widget | Bật/tắt lịch tháng (trước đây: đổi chế độ xem) |
| Nút nổi góc trên phải | Bỏ nút `THÁNG`, chỉ giữ nút menu `…` |
| Menu chuột phải | Ô tick "Hiện lịch tháng" thay cho mục chọn chế độ xem |
| Menu khay hệ thống | Ô tick "Hiện lịch tháng" thay cho menu con "Chế độ xem" |
| Hộp thoại Cài đặt | Ô tick "Hiện lịch tháng dưới lịch ngày" thay cho nhóm nút chế độ xem |

### 2.5 Gần đáy màn hình

- Sau khi mở, nếu mép dưới widget tràn qua đáy vùng làm việc
  (`availableGeometry`), widget dời lên cho vừa.
- Nếu tổng chiều cao vẫn lớn hơn chiều cao vùng làm việc, bề rộng và chiều cao
  bloc cùng giảm theo tỉ lệ cho vừa. Kích thước mới được lưu lại.
- Khi đóng lịch tháng, widget **không** tự dời về chỗ cũ.

## 3. Cấu hình

### 3.1 Trường mới

`core/config.py`, lớp `Settings`:

- Bỏ `view: str` (`"bloc"` | `"month"`) và hằng `VIEWS`.
- Thêm `show_month: bool = False`.
- `SCHEMA_VERSION` từ 1 lên 2.

### 3.2 Chuyển đổi từ tệp cũ

Trong `Settings.from_dict`:

| Dữ liệu trong `settings.json` | Kết quả |
|---|---|
| Có `show_month` hợp lệ (bool) | Dùng giá trị đó; bỏ qua `view` |
| Không có `show_month`, `"view": "month"` | `show_month = True` |
| Không có `show_month`, `view` khác hoặc không có | `show_month = False` |
| `show_month` sai kiểu | `False` (theo quy tắc kẹp giá trị hiện có) |

Khoá `view` không còn được ghi ra tệp (`to_dict` chỉ ghi các trường của
`Settings`).

### 3.3 Dòng lệnh

`--smoke --view month` vẫn được chấp nhận và được hiểu là `show_month = True`;
`--view bloc` là `False`. Payload JSON của `--smoke` thay khoá `"view"` bằng
`"show_month"`.

## 4. Kích thước và bố cục

### 4.1 Ý nghĩa của `width` / `height`

**Giữ nguyên**: là kích thước widget khi lịch tháng **đóng**, tức kích thước
phần bloc (đã gồm lề bóng `SHADOW_MARGIN`). Không cần chuyển đổi dữ liệu.

### 4.2 Bố cục

- Bỏ `QStackedWidget`. Cửa sổ dùng một cột dọc gồm, từ trên xuống:
  `BlocView`, `MonthView` (ẩn khi đóng), và một **dải đáy** trống cao
  `tab_strip_h`.
- `MonthTab` **không** nằm trong layout; nó được đặt tuyệt đối (giống
  `_ResizeGrip`), căn giữa theo chiều ngang, phần trên chạm mép dưới tờ giấy
  cuối cùng (bloc khi đóng, lịch tháng khi mở), phủ lên dải đáy và lề bóng.
- Lưu ý: cửa sổ có `WA_TranslucentBackground` nên `BlocView` chạy ở chế độ
  `embedded` và tờ giấy phủ kín cả `BlocView`; dưới tờ giấy chỉ có lề bóng
  `SHADOW_MARGIN` (10 px), không đủ cho tab. Vì vậy cần dải đáy riêng.
- `tab_strip_h = px(12, content_scale)`; tab cao khoảng
  `tab_strip_h + SHADOW_MARGIN`.
- Khi đóng: kích thước widget **không đổi** so với bản cũ (`width × height`);
  `BlocView` thấp đi đúng `tab_strip_h` (≈ 12 px ở cỡ mặc định). Bố cục bên
  trong `BlocView` tự co theo chiều cao được cấp. Cần kiểm tra bằng ảnh
  `--smoke` ở cỡ nhỏ nhất 260×330 rằng không có chữ bị cắt.

### 4.3 Chiều cao phần lịch tháng

```
paper_w  = width − 2·SHADOW_MARGIN
month_h  = round(paper_w × MONTH_RATIO)        # MONTH_RATIO = 1.15
extra_h  = MONTH_GAP + month_h                 # MONTH_GAP = khe giữa hai tờ giấy
window_h = height + extra_h                    # khi mở
```

- Dải đáy `tab_strip_h` đã nằm trong `height` nên không cộng thêm; khi mở, dải
  này đi theo xuống dưới `MonthView`.
- `MONTH_GAP` là khe nhỏ (khoảng `px(6, content_scale)`) để hai tờ giấy tách
  nhau và bóng đổ của bloc vẫn thấy được.
- Ở cỡ mặc định 344 px, `extra_h` ≈ 380 px.
- `month_h` không phụ thuộc lịch có 5 hay 6 hàng; `MonthView` tự chia hàng
  trong chiều cao được cấp, nên widget không nhảy cỡ khi chuyển tháng.
- `MONTH_RATIO` là hằng số trong `widget_window.py`; giá trị cuối cùng chỉnh
  theo ảnh `--smoke` sao cho lưới 6 hàng vẫn đọc rõ ở cỡ nhỏ nhất.

### 4.4 Hệ số phóng chữ

`content_scale()` tính từ kích thước **bloc**, không từ chiều cao cửa sổ:

```
bloc_h = window_h − extra_h   if show_month else window_h
ratio  = min(width / BASE_WIDTH, bloc_h / BASE_HEIGHT)
```

`bloc_h` khi đóng chính là `window_h` như công thức hiện nay, nên hệ số phóng
ở trạng thái đóng không đổi so với bản cũ. Lịch tháng dùng chung hệ số này.
`extra_h` phụ thuộc `content_scale` qua `MONTH_GAP`; để tránh vòng lặp, khi
tính `extra_h` dùng `px(6, ratio_w)` với `ratio_w = settings.scale × width /
BASE_WIDTH` (chỉ phụ thuộc bề rộng).

### 4.5 Kéo giãn bằng tay nắm khi đang mở

- Tay nắm vẫn ở góc dưới phải của cả widget.
- Kéo ngang: đổi `width`; `month_h` tính lại theo bề rộng mới nên cả hai lịch
  cùng to/nhỏ.
- Kéo dọc: chỉ đổi chiều cao bloc (`window_h − extra_h`).
- Giới hạn `MIN_*` / `MAX_*` (260×330 … 1000×1300) áp cho **bloc**; tổng chiều
  cao còn bị giới hạn bởi chiều cao vùng làm việc của màn hình.
- `_store_geometry()` lưu `width` và chiều cao **bloc**, không lưu chiều cao
  cửa sổ.

## 5. Thành phần

### 5.1 File mới: `ui/month_tab.py`

Lớp `MonthTab(QWidget)`, khoảng 100 dòng.

| API | Mô tả |
|---|---|
| `toggled = Signal()` | Phát khi người dùng bấm tab |
| `set_open(flag: bool)` | `False` → `THÁNG` + mũi tên xuống; `True` → `ẨN` + mũi tên lên |
| `apply_theme(theme: Theme, scale: float)` | Màu và cỡ theo theme / hệ số phóng |
| `sizeHint()` | Kích thước theo `scale` |

Tab không đọc `Settings`, không biết gì về cửa sổ; `CalendarWidget` đặt vị trí
và trạng thái cho nó.

### 5.2 File sửa

| File | Thay đổi |
|---|---|
| `core/config.py` | `show_month`, chuyển đổi từ `view`, schema 2 (§3) |
| `ui/widget_window.py` | Cột dọc thay `QStackedWidget`; `set_show_month(bool)` và `toggle_month()` thay `set_view` / `toggle_view`; tính lại chiều cao, kéo giãn, `content_scale`, `_store_geometry`; đặt vị trí `MonthTab`; đẩy vào vừa màn hình (§2.5); nháy đúp gọi `toggle_month`; bỏ nút `_view_btn`; menu chuột phải dùng ô tick |
| `ui/month_view.py` | Bỏ `_btn_bloc` và `bloc_requested`; thêm `set_selected(date \| None)` vẽ viền nhấn cho ô đang xem; bỏ phần trừ bề rộng nút `Ngày` trong `_refresh_footer_text` |
| `platform/tray.py` | Thay menu con "Chế độ xem" bằng hành động tick "Hiện lịch tháng"; `view_requested(str)` → `month_toggled(bool)`; `set_state` đọc `settings.show_month` |
| `ui/settings_dialog.py` | Thay `_view_group` bằng ô tick "Hiện lịch tháng dưới lịch ngày"; `_collect` ghi `show_month` |
| `app.py` | Nối `tray.month_toggled` → `widget.set_show_month`; dòng log khởi động; `_run_smoke` theo §3.3 |
| `scripts/preview_month.py` | Bỏ kiểm tra nút `Ngày` / `bloc_requested` |
| `README.md`, `docs/01-kien-truc.md`, `docs/03-tung-buoc-code.md` | Mô tả tính năng và thao tác mới |

### 5.3 Luồng dữ liệu

Tab, nháy đúp, menu chuột phải, menu khay và hộp thoại Cài đặt đều đi về **một**
hàm `CalendarWidget.set_show_month(flag)`:

1. Bỏ qua nếu trạng thái **hiển thị thực tế** đã khớp (`MonthView` đã tồn tại
   và đang hiện khi `flag = True`; hoặc không hiện khi `flag = False`). Không
   so với `settings.show_month`, vì lúc khởi động và khi áp Cài đặt giá trị
   này đã được ghi trước.
2. Ghi `settings.show_month`.
3. Lần mở đầu tiên: tạo `MonthView` (tạo lười như hiện nay), nối tín hiệu,
   đồng bộ tháng theo `month_anchor`.
4. Hiện/ẩn `MonthView`, `MonthTab.set_open(flag)`, đổi chiều cao cửa sổ (§4.3).
5. Khi mở: đẩy vào vừa màn hình (§2.5).
6. Phát `settings_changed` → `AppController` cập nhật tick ở khay và lưu cấu
   hình (debounce 500 ms như hiện nay).

Hộp thoại Cài đặt: `AppController.open_settings` gọi `apply_settings`; hàm này
gọi `set_show_month(settings.show_month)` để áp trạng thái mới.

Bấm ngày trong lịch tháng: `_on_day_activated` đặt `_selected`, làm mới bloc,
gọi `month.set_selected(...)`; **không** đóng lịch tháng. `go_today` xoá
`_selected` và gọi `month.set_selected(None)`.

## 6. Xử lý lỗi và trường hợp biên

| Tình huống | Hành vi |
|---|---|
| Không lấy được `screen()` | Dùng `primaryScreen()`; nếu vẫn không có thì bỏ qua bước vừa màn hình |
| Đang ghim Desktop khi bật/tắt | Chỉ đổi kích thước cửa sổ top-level; không bỏ ghim; watchdog hiện có giữ Z-order |
| `show_month = True` lúc khởi động | Tạo `MonthView` ngay khi dựng cửa sổ và mở sẵn (chấp nhận tốn RAM vì người dùng đã chọn) |
| Đổi theme / màu nền / độ mờ | `MonthTab.apply_theme` được gọi cùng chỗ với `BlocView` và `MonthView` |
| Sang ngày mới (nửa đêm) | Như hiện nay; thêm `month.set_selected(None)` nếu đang xem hôm nay |

## 7. Kiểm thử

Viết test trước khi viết code (TDD).

### 7.1 `tests/test_config.py`

- Mặc định `show_month is False`.
- `{"view": "month"}` → `show_month is True`; `{"view": "bloc"}` → `False`.
- Có cả `show_month` và `view` → theo `show_month`.
- `show_month` sai kiểu → `False`.
- `to_dict()` không có khoá `view`; `schema_version == 2`.
- Sửa các test hiện có đang dùng `view` / `VIEWS`.

### 7.2 `tests/test_widget_window.py`

- Đóng (mặc định): cửa sổ đúng `width × height`; tab nằm trọn trong cửa sổ,
  căn giữa, chạm mép dưới `BlocView`.
- Mở: chiều cao tăng đúng `extra_h` theo bề rộng; bề rộng không đổi; tab chạm
  mép dưới `MonthView`.
- Khởi động với `show_month = True`: lịch tháng hiện sẵn, cửa sổ cao
  `height + extra_h`.
- Đóng: về đúng `width × height` cũ.
- Bật/tắt không làm đổi `content_scale()`.
- Kéo giãn khi đang mở: `settings.width/height` là kích thước bloc.
- Gần đáy màn hình: widget dời lên; cao hơn màn hình: thu nhỏ cho vừa.
- Bấm một ngày: bloc đổi ngày, `show_month` vẫn `True`, `set_selected` nhận ngày đó.
- Nháy đúp: bật/tắt lịch tháng.
- Chưa mở lần nào: `_month is None`.
- Sửa các test hiện có đang dùng `set_view` / nút `THÁNG`.

### 7.3 `tests/test_month_tab.py` (mới)

- `set_open(True/False)` đổi chữ hiển thị và hướng mũi tên.
- Bấm chuột trái phát `toggled` đúng một lần.

### 7.4 Kiểm tra bằng mắt và bằng tay

- `run_qtcalendar.pyw --smoke` ở cả hai trạng thái, theme `giay_do` và
  `dem_sao`; xem ảnh PNG.
- Thử tay ở chế độ ghim Desktop: mở/đóng lịch tháng, bấm `Win + D`, kéo giãn.
- Toàn bộ `pytest tests -q` xanh.
