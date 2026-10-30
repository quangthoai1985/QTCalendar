# 05 — Kiểm thử, số liệu đo và đóng gói

> Tài liệu này ghi lại **cách dự án tự chứng minh mình chạy đúng**: bốn lớp
> kiểm thử, các con số đo được trên máy thật, những giới hạn còn lại và cách
> đóng gói thành ứng dụng chạy được.

Mục lục

1. [Bốn lớp kiểm thử](#1-bốn-lớp-kiểm-thử)
2. [Kết quả chạy test](#2-kết-quả-chạy-test)
3. [Kiểm chứng thuật toán âm lịch](#3-kiểm-chứng-thuật-toán-âm-lịch)
4. [Đo bộ nhớ và bài học glyph](#4-đo-bộ-nhớ-và-bài-học-glyph)
5. [Kiểm chứng "sống" trên Windows](#5-kiểm-chứng-sống-trên-windows)
6. [Hạn chế đã biết](#6-hạn-chế-đã-biết)
7. [Đóng gói và phát hành](#7-đóng-gói-và-phát-hành)

---

## 1. Bốn lớp kiểm thử

| Lớp | Công cụ | Phạm vi | Thời gian |
|---|---|---|---|
| **1. Unit – core** | `pytest` | 8 module `core/`: âm lịch (2 engine), Can Chi, cấu hình, ca dao, lễ, ngày lễ, tầng dịch vụ | ~6 s |
| **2. Tích hợp core + service** | `pytest` + `scripts/audit_calendar.py` | `DayInfo`/`MonthGrid` thật, CLI audit đối chiếu lịch vạn niên bằng mắt | ~1 s |
| **3. Giao diện** | `QWidget.grab()` → PNG | 4 theme × 3 ngày × nhiều kích thước; tự kiểm tràn chữ/đè nhãn; xem ảnh thật bằng `read_image` | ~10 s |
| **4. "Sống" trên Windows** | app thật + ctypes | khởi động, HWND, style, RAM, thử Registry, chụp màn hình | ~15 s |

Lệnh chạy tất cả:

```powershell
$env:PYTHONUTF8="1"
python -X utf8 -m pytest tests -q                 # lớp 1 + 2
python -X utf8 scripts\preview_bloc.py --native    # lớp 3 (bloc)
python -X utf8 scripts\preview_month.py            # lớp 3 (tháng + dialog)
python -X utf8 scripts\verify_live.py              # lớp 4
python -X utf8 scripts\probe_desktop_pin.py        # lớp 4 (chuyên sâu ghim)
```

---

## 2. Kết quả chạy test

```
$ python -X utf8 -m pytest tests -q
545 passed, 7 xfailed in 10,8s
```

| File test | Số test | Phạm vi |
|---|---:|---|
| `test_lunar_precise.py` | 130 | 56 ngày Tết, 18 tháng nhuận, liên tục 1900–2200, round-trip, độ dài năm, tiết khí, thiên văn (sóc 06/01/2000, ΔT, phân/chí 2026) |
| `test_lunar_hnd.py` | 99 | engine Hồ Ngọc Đức: Tết, `lunar_month_days`, `lunar_year_months`, các ca khác biệt có chủ đích |
| `test_config.py` | 64 | load/save, tệp hỏng, kẹp giá trị, ghi nguyên tử, portable, chuyển `view` cũ → `show_month` (schema 2) |
| `test_canchi.py` | 55 | Can Chi năm/tháng/ngày, con giáp, giờ hoàng đạo, ngày hoàng đạo |
| `test_calendar_service.py` | 44 | `DayInfo`, `MonthGrid`, ngày lễ |
| `test_holidays.py` | 38 | bảng lễ Dương + Âm, ưu tiên, tháng nhuận không tính lễ |
| `test_audit_calendar.py` | 20 | CLI audit: bố cục bảng, `--year`, `--engine`, tháng nhuận |
| `test_quotes.py` | 26 | kho ca dao: số lượng, không trùng, UTF-8, ổn định theo ngày |
| `test_widget_window.py` | 35 | kéo giãn cửa sổ (delta, kẹp min/max, lưu kích thước) + **chế độ ghim giữ nền trong suốt, không quầng đen** + lịch tháng dưới bloc (cao thêm đúng, không đổi cỡ chữ, tab bám mép, kéo giãn/vừa màn hình, bấm ngày giữ lịch mở) |
| `test_month_tab.py` | 6 | tab kéo: chữ/mũi tên theo trạng thái, phát `toggled`, không dùng ký tự tượng hình, co giãn theo hệ số phóng |
| `test_month_view.py` | 5 | lịch tháng: không còn nút Ngày, đánh dấu ngày đang xem (`set_selected`) |
| `test_desktop_pin.py` | 7 | `handle_windowposchanging` (chống dời `-32000`, chống `SWP_HIDEWINDOW`, `SWP_NOZORDER` khi click, cho phép lệnh nội bộ), `pin`/`unpin`, `update_z_order` khi Show Desktop và bình thường |
| `test_theme_paper.py` | 15 | độ mờ chỉ ở nền (chữ đặc), màu nền tuỳ chọn, `bg_color` lưu/đọc |

### 7 xfail — khác biệt **có chủ đích** của engine Hồ Ngọc Đức gốc

| Ca | Engine `hnd` | Lịch Việt Nam chuẩn |
|---|---|---|
| Tết 1991 | 14/02/1991 | **15/02/1991** |
| Tháng nhuận 2023 | tháng Giêng | **tháng Hai** |
| Tháng nhuận 2039 | tháng Tư | **tháng Năm** |
| Sóc 05/2020 | 22/05 | **23/05** |
| Sóc 03/2023 | 21/03 | **22/03** |
| Sóc 08/2026 | 12/08 | **13/08** |
| Sóc 04/2031 | 22/04 | **21/04** |

Nguyên nhân: chuỗi Fourier rút gọn trong bản gốc có sai số ±50 phút; khi điểm
sóc rơi sát nửa đêm giờ Hà Nội thì lệch hẳn một ngày. Engine mặc định
(`precise`) **không** có các sai lệch này — xem `docs/04`.

---

## 3. Kiểm chứng thuật toán âm lịch

| Phép kiểm | Phạm vi | Kết quả |
|---|---|---|
| Ngày Tết Nguyên Đán | 31 năm 1985–2040 (bảng lịch VN) | **31/31 khớp** |
| Tên tháng nhuận | 18 năm 1990–2036 | **18/18 khớp** |
| Tháng 11 nhuận (bài toán 2033) | 2033 | đúng: 22/12/2033 → 19/01/2034, thuộc năm 2033 |
| Tính liên tục của lịch | **109.938 ngày** (1900–2200) | **0 lỗi** (không nhảy cóc, không trùng) |
| Khứ hồi Dương → Âm → Dương | 1900–2100 | **0 lỗi** |
| Độ dài năm âm | 1900–2200 | chỉ ∈ {353, 354, 355, 383, 384, 385} |
| Ngày mùng 1 khứ hồi | 1900–2200 | **0 lỗi** |
| Sóc 06/01/2000 | so với ví dụ 49.a của Meeus | khớp (18:14 TT) |
| Đông chí / Xuân phân 2026 | giờ Hà Nội | Đông chí 22/12, Xuân phân 20/03 |
| Can Chi mốc | 01/01/2000, Tết 2024, 28/10/2026 | Mậu Ngọ · Giáp Thìn · Ất Hợi |
| Giờ hoàng đạo ngày Tý | tập hợp kỳ vọng | {Tý, Sửu, Mão, Ngọ, Thân, Dậu} |
| Ngày hoàng đạo tháng Giêng | kỳ vọng | {Tý, Sửu, Thìn, Tỵ, Mùi, Tuất} |

So sánh hai engine (đo trên 185 tuần trăng 2020–2034):

| Tiêu chí | `hnd` (bản gốc) | `precise` (mặc định) |
|---|---|---|
| Sai số điểm sóc | ±50 phút (max 49,2 phút đo được) | < 1 phút |
| Sóc lệch ngày | 4/185 | 0 |
| Năm sai tên tháng nhuận (1990–2040) | 2 (2023, 2039) | 0 |
| Xử lý tháng 11/12 nhuận | sai (2033) | đúng |

---

## 4. Đo bộ nhớ và bài học glyph

Đo bằng `Get-Process` (WorkingSet64 / PrivateMemorySize64) trên Windows 11
25H2, Python 3.14.7, PySide6 6.11.2:

| Trạng thái | Working set | Private |
|---|---:|---:|
| `QApplication` + import Qt | 41–43 MB | 22–23 MB |
| Khung widget trong suốt, rỗng | 49 MB | 25 MB |
| **QT Calendar – chạy ngầm (lịch ngày)** | **82 MB** | **46 MB** |
| Mở lịch tháng lần đầu (tạo lười) | ~160 MB | ~82 MB |

> Mục tiêu đề bài là **< 60 MB**. Thực đo **~82 MB**: vượt ~22 MB do mức nền
> Qt6 + Python (~43 MB trước khi vẽ nội dung). Nếu cần tuyệt đối < 60 MB,
> lựa chọn đúng là WPF/.NET 8 (xem bảng so sánh `docs/01` §2.1).

### Phát hiện quan trọng: một ký tự có thể tốn 85 MB

Khi đo từng ký tự đặt làm nhãn nút, kết quả bất ngờ:

| Ký tự | RAM tăng | Kết luận |
|---|---:|---|
| `⋯` U+22EF | **+84 MB** | ❌ |
| `⚙` U+2699 | **+87 MB** | ❌ |
| `▸` U+25B8 | **+86 MB** | ❌ |
| `☰` U+2630, `▦` U+25A6, `✕` U+2715, `⏱` U+23F1 | **+87…+89 MB** | ❌ |
| `•` `·` `…` `–` `—` `‹` `›` `●` `°` `×` | +2…+11 MB | ✅ an toàn |

Cơ chế: nếu DirectWrite không tìm thấy glyph trong font hiện tại, Windows nạp
**cả bộ font dự phòng** (CJK…) vào tiến trình. Vì vậy:

* nút menu dùng `…` (U+2026) thay cho `⋯`;
* quy ước chung: **chỉ dùng glyph có trong Segoe UI**;
* nếu một ngày nào đó ai thêm icon tượng hình, hãy đo lại RAM ngay.

Hai tối ưu khác đã áp dụng: `MonthView` **tạo lười** (chỉ khi mở lịch tháng
lần đầu) và tiêu đề tháng **không** elide bằng `QFontMetrics` lúc `setText`
(cũng kích hoạt bộ font dự phòng).

---

## 5. Kiểm chứng "sống" trên Windows

> **Lưu ý (từ bản 1.0.1):** §5.1 – §5.3 ghi lại kết quả đo của cơ chế ghim
> cũ `SetParent(Progman)` (bản ≤ 1.0.0). Cơ chế hiện tại là cửa sổ top-level
> kiểu Rainmeter (xem `docs/01-kien-truc.md` §4), không gọi `SetParent` nên
> không còn bị UIPI chặn. Các script `verify_live.py`, `probe_desktop_pin.py`
> và `verify_pin_visibility.py` **vẫn kiểm tra theo cơ chế cũ** (mong đợi
> `ws_child = true`, `parent_class = "Progman"`) nên kết quả của chúng không
> còn phản ánh đúng; cần viết lại trước khi dùng làm tiêu chí phát hành.

### 5.1 `scripts/verify_live.py`

Chạy ứng dụng thật với `settings.json` tạm, chờ 3 giây rồi đo:

```json
{
  "window_found": true,
  "class": "Qt6112QWindowToolSaveBits",
  "visible": true,
  "rect": [940, 120, 1284, 588],
  "ex_toolwindow": true,
  "ws_popup": true, "ws_child": false,
  "parent": 0, "progman": 65794,
  "is_top_level": true,
  "memory": {"working_set_mb": 82.1, "private_mb": 45.7},
  "autostart": {"command": "\"C:\\Python314\\pythonw.exe\" \"E:\\App\\QTCalendar\\run_qtcalendar.pyw\"",
                "before": null, "enable_ok": false, "is_enabled": false}
}
```

Đọc được: cửa sổ đúng vị trí đã lưu (940,120), kích thước 344×468,
`WS_EX_TOOLWINDOW` bật (không có trong taskbar/Alt+Tab), RAM 82 MB.
Hai mục **không kết luận được** trong môi trường agent:

* `parent = 0` ⇒ chưa ghim được;
* `enable_ok = false` ⇒ chưa ghi được Registry.

### 5.2 Vì sao — và bằng chứng thay thế

Tiến trình do agent khởi chạy chạy ở **Low Integrity** (sandbox); Explorer
chạy **Medium**. Windows UIPI chặn `SetParent` sang cửa sổ của tiến trình có
integrity cao hơn ⇒ `Win32 error 5 (ERROR_ACCESS_DENIED)`. Ghi `HKCU\...\Run`
cũng bị restricted token chặn.

`scripts/probe_desktop_pin.py` chứng minh **cơ chế đúng** bằng ba pha:

| Pha | Host | Kết quả |
|---|---|---|
| 1 | `Progman` thật | `pin=False`, `last_error=5` — do UIPI, không phải logic |
| 2 | host do chính script tạo (cùng tiến trình) | `pin=True`, `parent==host`, `WS_CHILD` bật, `WS_POPUP` tắt, HWND **biến mất khỏi `EnumWindows`**, rect màn hình giữ nguyên, `unpin` khôi phục hoàn hảo, `monitor()` ghim lại được |
| 3 | host của **tiến trình Python khác** (cùng integrity) | `pin=True`, `parent==host` ⇒ `SetParent` xuyên tiến trình không bị cấm |

Nghĩa là khi ứng dụng chạy bình thường (Medium IL, như Explorer), lần ghim
đầu tiên sẽ thành công. **Để có bằng chứng cuối, chạy từ terminal thường
(không qua agent):**

```powershell
cd E:\App\QTCalendar
$env:PYTHONUTF8="1"
python -X utf8 scripts\probe_desktop_pin.py     # dòng đầu phải ghi: Integrity level: Medium
python -X utf8 scripts\verify_live.py            # mong đợi: parent_class = "Progman", ws_child = true
```

### 5.3 Những gì đã đo được khi đang ghim (pha 2)

| Thao tác Qt khi đang ghim | Kết quả đo |
|---|---|
| `Qt.move(x, y)` | Qt gửi **toạ độ màn hình**; Win32 hiểu là toạ độ client của host ⇒ lệch đúng bằng gốc client host. Trên một màn hình, gốc `Progman` = (0,0) nên vẫn đúng; app vẫn có bước bù bằng `GetWindowRect` |
| `Qt.resize(w, h)` | đúng (kích thước không phụ thuộc gốc) |
| `setWindowOpacity` | vẫn thêm `WS_EX_LAYERED`, giữ `WS_CHILD` (an toàn) |
| `hide()` / `show()` | giữ nguyên quan hệ cha–con |
| `setWindowFlag(WindowStaysOnTopHint)` | **mất** `WS_CHILD`/parent ⇒ app phải unpin trước khi đổi cờ (đã xử lý) |

---

## 6. Hạn chế đã biết

| # | Hạn chế | Ảnh hưởng | Hướng xử lý |
|---|---|---|---|
| 1 | Phát hiện `Win + D` dựa vào thứ tự Z của lớp Desktop (`Progman`/`WorkerW`) so với sentinel | nếu Explorer đổi cấu trúc lớp Desktop ở bản Windows mới, widget có thể bị che khi Show Desktop | cập nhật `get_desktop_icons_host()`; watchdog 2 s và hook foreground là lưới an toàn |
| 2 | Đổi window flags khi đang ghim làm Qt tạo lại native window | nháy nhẹ khi bật "luôn nổi" (tự chuyển sang cửa sổ nổi) | đã unpin trước khi đổi cờ; watchdog 2 s là lưới an toàn |
| 3 | Các script kiểm chứng sống còn theo cơ chế `SetParent` cũ | không dùng được làm bằng chứng cho bản ≥ 1.0.1 | viết lại `verify_live.py`/`verify_pin_visibility.py` theo cơ chế mới |
| 4 | Không ghi được Registry trong sandbox | không tự bật được autostart khi chạy trong agent | chạy từ terminal thường; code đã xử lý lỗi (trả `False`, app vẫn chạy) |
| 5 | Engine HND gốc sai 7 ca (bảng §2) | chỉ khi người dùng chọn engine `hnd` | mặc định `precise`; ghi rõ trong hộp thoại |
| 6 | RAM 82 MB > mục tiêu 60 MB | – | xem §4 |

---

## 7. Đóng gói và phát hành

### 7.1 Chạy trực tiếp (khuyến nghị khi phát triển)

```powershell
pythonw run_qtcalendar.pyw
```

`pythonw.exe` không tạo cửa sổ console. Tạo shortcut: chuột phải Desktop →
New → Shortcut → `"C:\Python314\pythonw.exe" "E:\App\QTCalendar\run_qtcalendar.pyw"`.

### 7.2 Đóng gói .exe bằng PyInstaller

```powershell
# certifi: bộ chứng chỉ gốc đóng gói kèm để kiểm tra cập nhật trên máy chưa có
# sẵn gốc của GitHub trong kho Windows (thiếu ⇒ CERTIFICATE_VERIFY_FAILED)
python -m pip install pyinstaller certifi

pyinstaller --noconfirm --windowed --clean --name "QT Calendar" `
  --icon assets\icon.ico `
  --add-data "assets;assets" `
  --paths src `
  run_qtcalendar.pyw
# → dist\QT Calendar\QT Calendar.exe
```

Ghi chú:

* `--windowed` = không console (bắt buộc với desktop widget).
* `--add-data "assets;assets"` chép icon; thiếu thì app vẫn chạy nhưng icon trống.
* Bản đóng gói nặng ~35–50 MB (PySide6 tối thiểu); nếu đã có Python trên máy
  thì cách chạy `pythonw` nhẹ hơn nhiều.
* Có thể dùng `--onefile` nhưng khởi động chậm hơn (phải giải nén).
* Đường dẫn `run_qtcalendar.pyw` trong Registry được tính tự động từ
  `autostart.build_command()` — chạy bản `.exe` rồi bật "Khởi động cùng
  Windows" sẽ ghi đúng đường dẫn `.exe`.

### 7.3 Danh sách kiểm tra trước khi phát hành

- [ ] `python -X utf8 -m pytest tests -q` xanh (545 passed / 7 xfailed).
- [ ] `python run_qtcalendar.pyw --smoke out.png --view bloc` và `--view month` (bloc + lịch tháng), exit 0.
- [ ] Bấm tab `THÁNG` ở chân: lịch tháng hiện dưới bloc, tab thành `ẨN`; bấm lại thì widget về đúng kích thước cũ.
- [ ] Ở chế độ ghim: lịch **nằm dưới mọi ứng dụng**, nền trong suốt, góc bo
      không có quầng đen; không có trong taskbar/Alt+Tab.
- [ ] Nhấn `Win + D`: lịch vẫn hiện, nằm dưới Taskbar; click lại một ứng
      dụng thì lịch lùi về sau ứng dụng đó.
- [ ] Click/kéo lịch khi đang ghim không làm lịch nhảy lên trên các cửa sổ khác.
- [ ] Kéo widget, thoát, mở lại → đúng vị trí.
- [ ] Bật "Khởi động cùng Windows" → `reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v QTCalendar`.
- [ ] Đổi 4 theme, độ mờ 20 %/100 %, chuyển ngày/tháng, bấm ca dao để đổi câu.
- [ ] Mở lịch tháng lần đầu → thấy RAM tăng (đã biết); quay lại lịch ngày.






