# 02 — Cấu trúc thư mục dự án

> Toàn bộ dự án nằm trong `E:\App\QTCalendar`. Đây là bản đồ để người mới đọc
> mã nguồn biết **file nào làm gì, ai gọi ai, và được phép sửa cái gì**.

Mục lục

1. [Cây thư mục](#1-cây-thư-mục)
2. [Trách nhiệm từng file](#2-trách-nhiệm-từng-file)
3. [Quy tắc phụ thuộc giữa các tầng](#3-quy-tắc-phụ-thuộc-giữa-các-tầng)
4. [Dữ liệu và tài nguyên](#4-dữ-liệu-và-tài-nguyên)
5. [Script tiện ích](#5-script-tiện-ích)
6. [Quy ước code](#6-quy-ước-code)
7. [Mở rộng dự án](#7-mở-rộng-dự-án)

---

## 1. Cây thư mục

```
E:\App\QTCalendar\
├── run_qtcalendar.pyw          # trình khởi chạy (không console) – 19 dòng
├── requirements.txt            # PySide6-Essentials
├── README.md                   # giới thiệu + hướng dẫn nhanh
├── .gitignore
│
├── assets/
│   ├── icon.png                # 256×256
│   └── icon.ico                # đa kích thước 16…256
│
├── src/qtcalendar/             # gói ứng dụng (~8.300 dòng)
│   ├── __init__.py             # APP_NAME, APP_ID, __version__
│   ├── app.py                  # bộ điều phối + CLI (--info/--smoke/--reset)
│   ├── core/                   # LOGIC THUẦN – không import Qt
│   │   ├── canchi_constants.py #   Can, Chi, con giáp, 12 thần, 24 tiết khí
│   │   ├── types.py            #   LunarDate, CanChi, AuspiciousHour, DayInfo, MonthGrid, Quote
│   │   ├── lunar.py            #   thuật toán Hồ Ngọc Đức (engine "hnd")
│   │   ├── lunar_precise.py    #   engine chính xác cao (Meeus) – mặc định
│   │   ├── canchi.py           #   Can Chi năm/tháng/ngày, giờ & ngày hoàng đạo
│   │   ├── calendar_service.py #   get_day_info / build_month_grid (+lru_cache)
│   │   ├── holidays.py         #   ngày lễ Dương lịch + Âm lịch Việt Nam
│   │   ├── quotes.py           #   nạp & chọn ca dao offline
│   │   ├── config.py           #   Settings + ConfigStore (ghi nguyên tử)
│   │   └── theme.py            #   4 bảng màu (design token)
│   ├── platform/               # tầng Win32
│   │   ├── __init__.py         #   cờ IS_WINDOWS
│   │   ├── win32.py            #   ctypes wrapper (user32/kernel32)
│   │   ├── desktop_pin.py      #   ghim kiểu Rainmeter (HWND_BOTTOM + sentinel) + monitor()
│   │   ├── autostart.py        #   Registry HKCU Run
│   │   └── tray.py             #   QSystemTrayIcon + 11 tín hiệu
│   ├── ui/                     # giao diện PySide6
│   │   ├── widget_window.py    #   cửa sổ không viền, kéo thả, ghim, menu
│   │   ├── bloc_view.py        #   lịch ngày (vẽ tay toàn bộ)
│   │   ├── month_view.py       #   lịch tháng 7 cột
│   │   ├── month_tab.py        #   tab kéo bật/tắt lịch tháng dưới chân bloc
│   │   ├── settings_dialog.py  #   3 thẻ cài đặt + preview trực tiếp
│   │   └── styles.py           #   sinh QSS từ Theme
│   └── data/
│       └── quotes.json         # 439 câu ca dao/tục ngữ/danh ngôn
│
├── tests/                      # 470 test pytest (~2.900 dòng)
│   ├── conftest.py             #   thêm src/ vào sys.path
│   ├── pytest.ini              #   -p no:cacheprovider, norecursedirs
│   ├── test_lunar_precise.py   # 130 test
│   ├── test_lunar_hnd.py       #  99
│   ├── test_config.py          #  58
│   ├── test_canchi.py          #  55
│   ├── test_calendar_service.py#  44
│   ├── test_holidays.py        #  38
│   ├── test_quotes.py          #  26
│   ├── test_widget_window.py   #  14 (kéo giãn + chế độ ghim)
│   ├── test_theme_paper.py     #  15 (độ mờ nền + màu nền)
│   └── test_audit_calendar.py  #  20
│
├── scripts/
│   ├── make_icon.py            # sinh icon.png + icon.ico (Pillow)
│   ├── audit_calendar.py       # CLI in bảng lịch tháng / cả năm âm lịch
│   ├── preview_bloc.py         # render ảnh bloc 4 theme + tự kiểm bố cục
│   ├── preview_paper.py        # ảnh minh hoạ độ mờ nền + màu nền
│   ├── verify_pin_visibility.py# (cũ, cơ chế SetParent) kiểm chứng lịch hiện rõ khi ghim
│   ├── preview_month.py        # render ảnh lịch tháng + hộp thoại
│   ├── probe_desktop_pin.py    # probe 3 pha cơ chế ghim desktop
│   └── verify_live.py          # chạy app thật: HWND, style, RAM, autostart
│
├── docs/                       # 5 tài liệu (01…05)
└── preview/                    # ~50 ảnh PNG nghiệm thu (không phát hành)
```

---

## 2. Trách nhiệm từng file

### 2.1 Tầng `core` — logic thuần, test không cần màn hình

| File | Dòng | Nhiệm vụ | Phụ thuộc |
|---|---:|---|---|
| `canchi_constants.py` | 52 | Hằng số: Can, Chi, con giáp (Mão = Mèo), 12 thần, 24 tiết khí, nhãn thứ | – |
| `types.py` | 172 | Dataclass `frozen/slots`: `LunarDate`, `CanChi`, `AuspiciousHour`, `Quote`, `DayInfo`, `MonthGrid` | `canchi_constants` |
| `lunar.py` | 305 | Engine **Hồ Ngọc Đức gốc**: `jd_from_date`, `new_moon`, `sun_longitude`, `solar_to_lunar`, `lunar_to_solar`, `lunar_month_days`, `lunar_year_months` | `types` |
| `lunar_precise.py` | 453 | Engine **chính xác cao**: Meeus ch.49/ch.25 + ΔT + bảng tháng liên tục; `month11_start`, `leap_offset`, `tiet_khi_index` | `lunar` (jd), `types` |
| `canchi.py` | 134 | `year_can_chi`, `month_can_chi`, `day_can_chi`, `zodiac_animal`, `auspicious_hours`, `is_auspicious_day` | `lunar`, `types`, constants |
| `calendar_service.py` | 130 | `get_day_info(date, engine)` → `DayInfo`; `build_month_grid`; `shift_month`; cache | `lunar*`, `canchi`, `holidays`, `types` |
| `holidays.py` | 53 | Bảng lễ Dương lịch (12) + Âm lịch (11); `holiday_for()` | `types` |
| `quotes.py` | 167 | `all_quotes`, `quote_of_day` (ổn định theo ordinal), `random_quote`, `quotes_by_topic` | `types`, `data/quotes.json` |
| `config.py` | 269 | `Settings` (26 trường, clamp) + `ConfigStore` (load/save/reset, portable) | `theme` (kiểm tra tên) |
| `theme.py` | 276 | 4 `Theme` + `THEME_ORDER` + helper `rgba()` | – |

### 2.2 Tầng `platform`

| File | Dòng | Nhiệm vụ | Ghi chú |
|---|---:|---|---|
| `win32.py` | 567 | ~25 hàm ctypes: `find_window`, `set_parent`, `get_window_rect`, `map_window_points`, `send_message_timeout`… | Không bao giờ ném lỗi |
| `desktop_pin.py` | 413 | `find_desktop_host`, `pin`, `unpin`, `is_pinned`, `monitor`; lưu style/owner/rect | Điểm nhấn kỹ thuật của dự án |
| `autostart.py` | 217 | `build_command`, `is_enabled`, `enable`, `disable`, `set_enabled`, `read_raw` | dùng `pythonw.exe` |
| `tray.py` | 434 | `TrayIcon(QObject)` – 11 `Signal`, menu khay, `set_state(settings)` | **Module platform duy nhất dùng Qt** |

### 2.3 Tầng `ui` + `app.py`

| File | Dòng | Nhiệm vụ | Phụ thuộc |
|---|---:|---|---|
| `widget_window.py` | 990 | Cửa sổ không viền: kéo thả, **tay nắm kéo giãn ở góc** (`_ResizeGrip`, giới hạn 260×330 … 1000×1300), hệ số phóng nội dung tự suy ra từ kích thước (`content_scale()`), opacity, ghim desktop, watchdog, menu chuột phải, nút menu nổi, xếp dọc bloc + lịch tháng (`set_show_month`, lười tạo lịch tháng), tab kéo `MonthTab` | `core`, `platform`, `bloc_view`, `month_view`, `styles` |
| `bloc_view.py` | 1.694 | Mặt lịch bloc: dải gáy, số ngày auto-fit, Can Chi, badge, 6 chip giờ hoàng đạo, ca dao | `core.types`, `theme` |
| `month_view.py` | 882 | Lưới tháng 5–6 hàng, header ‹ ›, ô tự vẽ, footer `[Ngày] [Hôm nay]` | `calendar_service`, `theme` |
| `settings_dialog.py` | 1.336 | 3 thẻ: Giao diện / Cửa sổ / Nâng cao; preview theme + opacity; lưu bản sao `Settings` | `config`, `theme`, `styles`, `platform.autostart` |
| `styles.py` | 659 | `build_stylesheet(theme, scale)`, `px()`, `qcolor()`, `blend()` – 24 selector | `theme` |
| `app.py` | 412 | `AppController`: widget ↔ tray ↔ config; `--info/--smoke/--reset`; QLockFile single-instance | tất cả |

Tổng: **~8.300 dòng mã nguồn + ~2.900 dòng test + ~1.800 dòng tài liệu**.

---

## 3. Quy tắc phụ thuộc giữa các tầng

```
app.py  ──►  ui/  ──►  core/
  │           │
  └──►  platform/  ──►  core/  (chỉ đọc Settings, không bắt buộc)
```

| Quy tắc | Kiểm tra tự động |
|---|---|
| `core/` **không** import Qt | `rg "PySide6" src/qtcalendar/core/` → rỗng |
| Chỉ `platform/tray.py` dùng Qt | `rg -l "PySide6" src/qtcalendar/platform/` → chỉ `tray.py` |
| `ui/` không đọc tệp cấu hình / Registry | `rg "ConfigStore|winreg" src/qtcalendar/ui/` → rỗng |
| Mọi hàm Win32 trả `False/None` thay vì ném | grep `except Exception` trong `platform/` |
| `core/` không phụ thuộc đường dẫn tuyệt đối | `rg "E:\\\\" src/` → rỗng |

Lý do: nhờ tầng `core` thuần, toàn bộ thuật toán lịch (phần dễ sai nhất) được
kiểm thử bằng `pytest` trong 6 giây, không cần màn hình, không cần Windows.

---

## 4. Dữ liệu và tài nguyên

| Tài nguyên | Vị trí | Kích thước | Sinh ra bởi |
|---|---|---|---|
| Icon | `assets/icon.png`, `assets/icon.ico` | 7,5 KB / 29 KB | `python -X utf8 scripts/make_icon.py` |
| Kho ca dao | `src/qtcalendar/data/quotes.json` | 53 KB, 439 câu | viết tay |
| Chứng cứ ảnh | `preview/*.png` | ~65 ảnh | `preview_bloc.py`, `preview_month.py`, `preview_paper.py`, `--smoke` |

**Cấu trúc `quotes.json`:**

```json
{
  "version": 1,
  "topics": {"ca-dao": "Ca dao", "tuc-ngu": "Tục ngữ", "danh-ngon": "Danh ngôn"},
  "items": [
    {"text": "Một cây làm chẳng nên non…", "author": "", "topic": "ca-dao"},
    {"text": "Có tài mà không có đức là người vô dụng…", "author": "Hồ Chí Minh", "topic": "danh-ngon"}
  ]
}
```

**Dữ liệu lúc chạy:**

```
%LOCALAPPDATA%\QTCalendar\settings.json      # cấu hình người dùng
%LOCALAPPDATA%\QTCalendar\qtcalendar.log     # log xoay vòng 64 KB × 3
%LOCALAPPDATA%\QTCalendar\qtcalendar.lock    # khoá single-instance
```

Chế độ portable: đặt `settings.json` cạnh `run_qtcalendar.pyw`; biến môi
trường `QTCALENDAR_CONFIG=<đường dẫn>` sẽ ép dùng tệp cụ thể.

---

## 5. Script tiện ích

| Script | Công dụng | Lệnh mẫu |
|---|---|---|
| `make_icon.py` | Sinh icon PNG/ICO bằng Pillow | `python -X utf8 scripts\make_icon.py` |
| `audit_calendar.py` | In bảng lịch tháng dạng text để đối chiếu lịch vạn niên | `python -X utf8 scripts\audit_calendar.py 2026 10` · `--year 2023` · `--engine hnd` |
| `preview_bloc.py` | Render ảnh bloc (4 theme × 3 ngày × 8 mức kích thước + trạng thái), tự kiểm tràn chữ | `python -X utf8 scripts\preview_bloc.py --native` |
| `preview_paper.py` | Render ảnh minh hoạ: độ mờ chỉ trên nền (chữ vẫn đặc) và 3 mức màu nền | `python -X utf8 scripts\preview_paper.py` |
| `preview_month.py` | Render ảnh lịch tháng + 4 ảnh hộp thoại cài đặt | `python -X utf8 scripts\preview_month.py` |
| `probe_desktop_pin.py` | *(Cũ — viết cho cơ chế `SetParent` ≤ 1.0.0)* Chứng minh cơ chế ghim 3 pha (Progman / host cùng tiến trình / xuyên tiến trình) | `python -X utf8 scripts\probe_desktop_pin.py` |
| `verify_live.py` | *(Phần kiểm tra ghim còn theo cơ chế `SetParent` cũ)* Chạy app thật 3 giây: tìm HWND, đọc parent/class/style, đo RAM, thử autostart, chụp màn hình | `python -X utf8 scripts\verify_live.py` |

---

## 6. Quy ước code

1. **Docstring và comment tiếng Việt** (có dấu); tên hàm/biến tiếng Anh.
   Ví dụ: `def solar_to_lunar(...)  # Đổi ngày Dương lịch sang Âm lịch Việt Nam`.
2. **Dataclass bất biến**: `@dataclass(frozen=True, slots=True)` cho mọi kiểu
   dữ liệu đi qua các tầng — nhờ vậy cache `lru_cache` an toàn tuyệt đối.
3. **Không ném ngoại lệ ra ngoài tầng `platform`**: trả `False`/`None`/`0`.
4. **Một nguồn sự thật cho màu/kích thước**: mọi màu đi qua `Theme`, mọi cỡ
   chữ đi qua `styles.px(value, scale)`.
5. **Không dùng glyph lạ** (U+22EF `⋯`, U+2699 `⚙`…): chỉ dùng glyph có trong
   Segoe UI — xem `docs/01` §7.
6. **Mỗi view có một hàm nạp dữ liệu duy nhất**: `BlocView.set_day(info)`,
   `MonthView.set_month(y, m)`; UI không tự tính lịch.
7. **Ghi tệp nguyên tử** (`*.tmp` + `os.replace`) cho mọi tệp cấu hình.

---

## 7. Mở rộng dự án

| Muốn thêm | Sửa ở đâu |
|---|---|
| **Bảng màu mới** | thêm một `Theme` trong `core/theme.py`, thêm tên vào `THEME_ORDER`; tự động có trong hộp thoại cài đặt |
| **Ngày lễ mới** | thêm một dòng vào `SOLAR_HOLIDAYS` hoặc `LUNAR_HOLIDAYS` trong `core/holidays.py` |
| **Ca dao mới** | thêm object vào `src/qtcalendar/data/quotes.json` rồi `quotes.reload()` |
| **Engine âm lịch khác** | thêm module cùng API 8 hàm, đăng ký vào `ENGINES` trong `calendar_service.py`, thêm vào `LUNAR_ENGINES` trong `config.py` |
| **Mặt lịch mới** (tuần, năm) | thêm widget vào `ui/`, chèn vào cột dọc trong `widget_window._build_ui` (như lịch tháng ở `set_show_month`) + một ô tick trong menu |
| **Đa ngôn ngữ** | hiện chưa hỗ trợ: chuỗi tiếng Việt nằm rải trong `types.py` (nhãn ngày/tháng), `canchi_constants.py` (Can Chi, tiết khí) và các view. Hướng làm: tách thành `core/i18n.py` với dict theo mã ngôn ngữ, truyền `lang` vào `Settings` |
| **Đóng gói .exe** | xem `docs/05-kiem-thu-va-dong-goi.md` §7 |


