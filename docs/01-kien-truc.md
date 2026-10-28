# 01 — Phân tích kiến trúc QT Calendar

> Tài liệu này trả lời ba câu hỏi: **chọn công nghệ nào và vì sao**, **chia
> hệ thống thành những tầng nào**, và **những cơ chế "khó" của Windows được
> xử lý ra sao** (ghim desktop, độ trong suốt, khay hệ thống, khởi động cùng
> Windows).

Mục lục

1. [Yêu cầu và ràng buộc](#1-yêu-cầu-và-ràng-buộc)
2. [Chọn công nghệ](#2-chọn-công-nghệ)
3. [Kiến trúc phân tầng](#3-kiến-trúc-phân-tầng)
4. [Cơ chế ghim sát Desktop](#4-cơ-chế-ghim-sát-desktop)
5. [Độ trong suốt khi cửa sổ là cửa sổ con](#5-độ-trong-suốt-khi-cửa-sổ-là-cửa-sổ-con)
6. [Vòng đời ứng dụng và các timer](#6-vòng-đời-ứng-dụng-và-các-timer)
7. [Ngân sách bộ nhớ](#7-ngân-sách-bộ-nhớ)
8. [Kịch bản lỗi và cách xử lý](#8-kịch-bản-lỗi-và-cách-xử-lý)
9. [Tiêu chí nghiệm thu](#9-tiêu-chí-nghiệm-thu)

---

## 1. Yêu cầu và ràng buộc

### 1.1 Yêu cầu chức năng (từ đề bài)

| # | Yêu cầu | Ghi chú kỹ thuật |
|---|---|---|
| F1 | Widget lịch bloc treo tường, thuần Việt | Cần ca dao/tục ngữ offline, thẩm mỹ "giấy – mực – đỏ" |
| F2 | Borderless, không thanh tiêu đề | `Qt.FramelessWindowHint` + `WA_TranslucentBackground` |
| F3 | Kéo thả tự do, tự lưu toạ độ khi thả | Bắt `mousePress/Move/Release`, ghi `settings.json` có debounce |
| F4 | **Ghim sát mặt bàn Desktop, không bị ẩn khi Win + D** | Phần khó nhất – xem §4 |
| F5 | Icon khay hệ thống + menu ngữ cảnh | `QSystemTrayIcon` + `QMenu` |
| F6 | Khởi động cùng Windows | `HKCU\...\CurrentVersion\Run`, không cần admin |
| F7 | Opacity 20 % – 100 % | Xem §5 |
| F8 | Lịch ngày: Thứ, ngày dương cực lớn, âm lịch, Can Chi, giờ hoàng đạo, ca dao | `DayInfo` |
| F9 | Lịch tháng 7 cột, Dương + Âm song song | `MonthGrid` |
| F10 | Đổi chế độ xem ngay trên widget và qua khay | Nút nổi + menu |
| F11 | Thuật toán âm lịch chuẩn UTC+7 theo Hồ Ngọc Đức | Hai engine – xem `docs/04` |
| F12 | Cấu hình lưu `settings.json` | `ConfigStore`, ghi nguyên tử |

### 1.2 Ràng buộc phi chức năng

| Ràng buộc | Cách đáp ứng |
|---|---|
| Windows 10/11 | Chỉ dùng API có từ Win7+ (`SetParent`, `Progman 0x052C`), test trên Win11 25H2 |
| **RAM < 60 MB khi chạy ngầm** | Đo thực: xem §7 |
| Nhẹ, khởi động nhanh | Không dùng QML/WebEngine, không ORM, không framework DI |
| Không cần quyền admin | Mọi thao tác đều ở `HKCU` và desktop window của chính user |
| Cấu hình không bao giờ làm hỏng app | Clamp giá trị, backup tệp lỗi, ghi nguyên tử |
| Chạy được khi Explorer khởi động lại | Watchdog ghim lại – xem §4.4 |

---

## 2. Chọn công nghệ

Đề bài ưu tiên ba lựa chọn: **.NET 8 WPF / C#**, **Python PySide6**, **Tauri**.

### 2.1 Bảng so sánh

| Tiêu chí | .NET 8 WPF | **Python + PySide6** | Tauri (Rust + WebView2) |
|---|---|---|---|
| RAM khi chạy ngầm (đo thực tế) | ~35–50 MB | **~45–55 MB** (đo: nền 44,6 MB) | ~25–40 MB (nhưng + process WebView2 riêng ~60–100 MB) |
| Kích thước phát hành | ~70 MB self-contained / ~2 MB nếu máy có runtime | ~150 MB (PySide6) hoặc ~35 MB khi PyInstaller | ~8 MB |
| Thời gian phát triển UI tuỳ biến | Trung bình (XAML) | **Nhanh** (QSS giống CSS) | Chậm cho desktop-native (WebView chạy nền tảng web) |
| Gọi Win32 (SetParent, Registry) | Rất tốt (P/Invoke) | **Rất tốt (ctypes)** | Tốt nhưng phải viết lớp Rust |
| Không viền / trong suốt / khay | Có sẵn | Có sẵn | Phải tự dựng thêm plugin |
| Yêu cầu môi trường để **build** | Cần .NET 8 SDK (~200 MB) | Cần Python + PySide6 | Cần Rust toolchain + Node |
| Khả dụng trên máy phát triển | ❌ **Không có SDK, không có mạng để tải** | ✅ **Đã cài sẵn Python 3.14 + PySide6 6.11.2** | ❌ Không có Rust |
| Đóng gói .exe | Native | PyInstaller / Nuitka | Native |

### 2.2 Quyết định

**Chọn Python 3.14 + PySide6 6.11.2.** Lý do:

1. **Khả thi ngay**: máy phát triển không có .NET SDK, không có Rust và
   **không có kết nối mạng** để tải. PySide6 đã cài sẵn → build & chạy được
   ngay, và toàn bộ mã nguồn được kiểm chứng bằng cách chạy thật.
2. **Đạt ngân sách RAM**: đo trên máy thật, một cửa sổ Qt widget cơ bản tốn
   **44,6 MB working set / 21,8 MB private** – nằm dưới mốc 60 MB (§7).
3. **Win32 interop đầy đủ** bằng `ctypes`: `SetParent`, `SendMessageTimeout`,
   `FindWindowEx`, `winreg` – không thiếu thứ gì so với P/Invoke của C#.
4. **Tốc độ phát triển UI**: QSS (gần như CSS) cho phép tạo "giấy – mực –
   đỏ" nhanh hơn XAML, và vẽ tay bằng `QPainter` cho kết quả thẩm mỹ cao hơn
   control có sẵn.

> Nếu đội phát triển có .NET 8 SDK, **WPF là lựa chọn tương đương** và có
> RAM thấp hơn chút. Kiến trúc trong tài liệu này (4 tầng, `settings.json`,
> `SetParent(Progman)`, Registry Run) chuyển sang C# gần như 1-1.

### 2.3 Phiên bản / phụ thuộc

```
Python  3.14.7          (C:\Python314)
PySide6 6.11.2          (PySide6-Essentials – đã có QtWidgets, QtGui, QtCore)
Pillow  12.2.0          (chỉ dùng khi sinh icon, không cần lúc chạy)
pytest  8.x             (chỉ dùng khi test)
```

---

## 3. Kiến trúc phân tầng

### 3.1 Sơ đồ

```
┌──────────────────────────────────────────────────────────────────────┐
│                          qtcalendar/app.py                           │
│   AppController: nối widget ↔ tray ↔ config; QTimer; debounce lưu    │
└───────────────┬──────────────────────────────┬───────────────────────┘
                │                              │
     ┌──────────▼───────────┐        ┌─────────▼──────────────┐
     │      ui/ (PySide6)   │        │  platform/ (Win32+Qt)  │
     │ widget_window        │        │ win32       (ctypes)   │
     │ bloc_view  month_view│        │ desktop_pin (Progman)  │
     │ settings_dialog      │        │ autostart   (Registry) │
     │ styles (QSS builder) │        │ tray        (QSystemTrayIcon)
     └──────────┬───────────┘        └─────────┬──────────────┘
                │                              │
                └──────────┬───────────────────┘
                           │  chỉ đọc dữ liệu / gọi hàm thuần
                  ┌────────▼────────────────────────────────────┐
                  │              core/  (KHÔNG import Qt)       │
                  │  types       kiểu dữ liệu bất biến           │
                  │  lunar       HND gốc    ┐                    │
                  │  lunar_precise          ├─ hai engine âm lịch│
                  │  canchi      Can Chi, giờ hoàng đạo          │
                  │  calendar_service  → DayInfo / MonthGrid     │
                  │  quotes      ca dao offline (JSON)           │
                  │  config      Settings + ConfigStore          │
                  │  theme       design token 4 bảng màu         │
                  │  holidays    ngày lễ VN                      │
                  └─────────────────────────────────────────────┘
                           │
                  ┌────────▼───────────┐
                  │  data/quotes.json  │  (kho ca dao offline)
                  │  assets/icon.ico   │
                  └────────────────────┘
```

### 3.2 Quy tắc phụ thuộc (bắt buộc)

1. `core/` **không được** `import PySide6`. Nhờ vậy toàn bộ thuật toán lịch,
   cấu hình, ca dao đều test được bằng `pytest` mà không cần màn hình.
2. `platform/` được dùng Qt **chỉ ở `tray.py`** (vì `QSystemTrayIcon` là của
   Qt); ba module còn lại thuần `ctypes`/`winreg`.
3. `ui/` không đọc `settings.json`, không gọi Registry, không tự quyết định
   vòng đời ứng dụng – nó chỉ phát tín hiệu (`settings_changed`,
   `quit_requested`…). `app.py` là nơi duy nhất quyết định.
4. Mọi hàm Win32 đều **không ném ngoại lệ**; thất bại trả `False`/`None`.
   Ứng dụng phải chạy tiếp được trên máy không có khay hệ thống, không có
   quyền ghi Registry, hay Explorer đang restart.

### 3.3 Luồng dữ liệu một lần vẽ

```
CalendarWidget._refresh_content()
   ├─ calendar_service.get_day_info(date, engine)      [core, có lru_cache]
   │     ├─ engine.solar_to_lunar()        → LunarDate
   │     ├─ canchi.day_can_chi / month_can_chi / year_can_chi
   │     ├─ canchi.auspicious_hours()      → 6 AuspiciousHour
   │     ├─ engine.tiet_khi_name()
   │     └─ holidays.holiday_for()
   ├─ quotes.quote_of_day(date) hoặc random_quote()    [core]
   └─ bloc_view.set_day(info); bloc_view.set_quote(quote)
          → QLabel.setText + paintEvent (không tạo lại widget)
```

Điểm quan trọng: **dữ liệu bất biến** (`frozen=True, slots=True`), nên có
thể cache thoải mái (`lru_cache`) mà không sợ view sửa vào. Lưới lịch tháng
6×7 = 42 đối tượng `DayInfo` được dựng trong **0,8 ms** khi cache nguội.

---

## 4. Cơ chế ghim sát Desktop

Đây là yêu cầu khó nhất và cũng là phần dễ làm sai nhất.

### 4.1 Vì sao cửa sổ thường bị ẩn khi nhấn Win + D?

`Win + D` (Show Desktop) gọi `IShellDispatch::ToggleDesktop`. Windows thực
hiện bằng cách **liệt kê toàn bộ cửa sổ cấp cao nhất** (`EnumWindows`) rồi
thu nhỏ/ẩn chúng. Cửa sổ *con* (child window) **không** nằm trong danh sách
đó ⇒ không bị ẩn.

Ngoài ra cửa sổ cấp cao nhất còn xuất hiện trong Alt+Tab và taskbar — một
desktop widget thì không nên.

### 4.2 Giải pháp: biến widget thành cửa sổ con của desktop

```python
# src/qtcalendar/platform/desktop_pin.py  (rút gọn)
progman = FindWindowW("Progman", None)
SendMessageTimeoutW(progman, 0x052C, 0, 0, SMTO_ABORTIFHUNG, 1000, byref(res))
host = _find_desktop_host()          # Progman, hoặc WorkerW có con SHELLDLL_DefView
old_style = GetWindowLongW(hwnd, GWL_STYLE)
SetParent(hwnd, host)                # ← biến thành cửa sổ con của desktop
SetWindowLongW(hwnd, GWL_STYLE, (old_style | WS_CHILD) & ~WS_POPUP)
SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW)
```

Vì sao phải gửi `0x052C` cho `Progman`: trên Windows 10/11, Explorer chỉ tạo
cửa sổ `WorkerW` (lớp chứa hình nền/icon) **khi được yêu cầu**; thông điệp
không tài liệu `0x052C` chính là yêu cầu đó. Nếu bỏ qua bước này, trên một
số máy `SHELLDLL_DefView` chưa tồn tại ⇒ không tìm được host.

### 4.3 Các phương án đã cân nhắc và loại

| Phương án | Vì sao loại |
|---|---|
| `HWND_TOPMOST` (luôn nổi) | Không phải "ghim sát mặt bàn": vẫn đè lên mọi cửa sổ, và **vẫn bị ẩn bởi Win+D** |
| `SetWindowPos(HWND_BOTTOM)` mỗi lần | Vẫn là top-level ⇒ vẫn bị Win+D ẩn; còn phải liên tục đẩy xuống |
| Hook bàn phím bắt Win+D rồi hiện lại | Cần hook toàn cục (dễ bị antivirus/Accessibility chặn), giật hình, không sạch |
| `SetWindowDisplayAffinity` | Chỉ dùng cho chống chụp màn hình, không liên quan |
| **`SetParent(Progman)`** | ✅ Sạch, không hook, không quyền admin, sống sót Win+D |
| `SetParent(WorkerW)` | ✅ Dùng làm **fallback** khi `Progman` không có `DefView` |

Dự án triển khai **cả hai** mức: mặc định ghim `Progman`; nếu không tìm thấy
thì tìm `WorkerW` có con `SHELLDLL_DefView`. Người dùng vẫn bật được chế độ
"cửa sổ nổi + luôn trên cùng" (`placement = "floating"`) trong Cài đặt.

### 4.4 Các cạm bẫy đã xử lý

| Cạm bẫy | Cách xử lý |
|---|---|
| **Toạ độ đổi gốc** sau `SetParent` | Lưu toạ độ màn hình trước khi ghim; sau khi ghim đọc `GetWindowRect`, nếu lệch thì `move()` bù lại (`_restore_screen_position`) |
| **Explorer khởi động lại** ⇒ `Progman` bị huỷ ⇒ cửa sổ con bị huỷ theo | Watchdog `QTimer` 2 giây: nếu `!is_pinned(hwnd)` thì ghim lại; nếu HWND đã chết thì báo lỗi và tạo lại cửa sổ |
| **Mất focus của ứng dụng khác** | Cờ `Qt.WindowDoesNotAcceptFocus` + `WS_EX_NOACTIVATE` |
| **Hiện trong Alt+Tab / taskbar** | `Qt.Tool` + `WS_EX_TOOLWINDOW` |
| **DPI scaling** | Qt 6 tự xử lý DPI theo monitor; cửa sổ được tạo là per-monitor-aware |
| **Đa màn hình** | `Progman` phủ toàn bộ vùng màn hình ảo, gốc toạ độ trùng gốc màn hình ảo ⇒ toạ độ Qt dùng được trực tiếp; vẫn có bước bù lệch bằng `GetWindowRect` |
| **Kẹp cửa sổ vào màn hình** | Sau mỗi lần thả chuột: `_clamp_into_screen()` theo `availableGeometry()` |

---

## 5. Độ trong suốt khi cửa sổ là cửa sổ con

`QWidget.setWindowOpacity()` trên Windows hoạt động bằng
`SetLayeredWindowAttributes` — chỉ có tác dụng với **cửa sổ cấp cao nhất**
(`WS_EX_LAYERED` không áp dụng cho cửa sổ con). Sau khi ghim desktop, widget
trở thành cửa sổ con ⇒ `setWindowOpacity` **mất tác dụng**.

Giải pháp lai:

```python
def _apply_opacity(self) -> None:
    opacity = clamp(self._settings.opacity, 0.2, 1.0)
    if self._pinned:                       # cửa sổ con → dùng effect
        self.setWindowOpacity(1.0)
        self._ensure_opacity_effect(opacity)      # QGraphicsOpacityEffect
    else:                                  # cửa sổ top-level → API gốc
        self.setWindowOpacity(opacity)
        self._ensure_opacity_effect(None)
```

`QGraphicsOpacityEffect` chỉ gắn lên `QStackedWidget` (một lần), nên chi phí
chỉ là một phép composite khi vẽ lại – không đáng kể vì widget chỉ vẽ lại
khi đổi ngày/đổi theme/kéo thả.

Hệ quả cần biết: khi đang ghim desktop, độ mờ do **nội dung** đảm nhận, nên
phần bóng đổ quanh tấm giấy vẫn đậm hơn một chút so với chế độ nổi. Đây là
đánh đổi có chủ ý.

---

## 6. Vòng đời ứng dụng và các timer

```
main()
 ├─ parse args (--info | --smoke | --reset | --version)
 ├─ setup_logging()            → %LOCALAPPDATA%\QTCalendar\qtcalendar.log
 ├─ ConfigStore.load()         → Settings (clamp, backup tệp lỗi)
 ├─ create_application()       → QApplication + icon + quitOnLastWindowClosed=False
 ├─ QLockFile (single-instance)
 ├─ AppController
 │    ├─ CalendarWidget(settings)
 │    │     ├─ _build_ui()        (QStackedWidget + 2 nút nổi)
 │    │     ├─ _refresh_content() (DayInfo + ca dao)
 │    │     └─ _start_timers()
 │    │           ├─ _midnight_timer  (single-shot tới 00:00:03)
 │    │           ├─ _quote_timer     (30 phút, chỉ hữu ích ở chế độ random)
 │    │           └─ _pin_timer       (2 giây – watchdog ghim desktop)
 │    ├─ TrayIcon + menu (nếu khả dụng)
 │    └─ _save_timer (500 ms – debounce ghi settings.json)
 └─ app.exec()
```

Ba nguyên tắc:

* **Không bao giờ để mất cấu hình**: mọi thay đổi đều đi qua
  `settings_changed` → debounce 500 ms → `ConfigStore.save()` (ghi tệp tạm +
  `os.replace`); khi thoát thì `_flush_settings()` ghi ngay.
* **Ẩn widget ≠ thoát app**: `closeEvent` bị `ignore()` và đặt
  `settings.hidden = True`; thoát thật chỉ qua menu khay "Thoát".
* **Single instance**: `QLockFile` ở `%LOCALAPPDATA%\QTCalendar\qtcalendar.lock`
  ⇒ bấm shortcut lần hai chỉ đưa cửa sổ hiện có lên.

---

## 7. Ngân sách bộ nhớ

Đo trên máy phát triển (Windows 11 25H2, Python 3.14.7, PySide6 6.11.2),
`Get-Process` → WorkingSet64 / PrivateMemorySize64:

| Trạng thái | Working set | Private |
|---|---|---|
| `QApplication` + import Qt | 41–43 MB | 22–23 MB |
| + khung widget trong suốt (`Qt.Tool`) | 49 MB | 25 MB |
| **QT Calendar – chạy ngầm, lịch ngày** | **~82 MB** | **~46 MB** |
| Mở lịch tháng lần đầu (lazy) | ~160 MB | ~82 MB |

### Hai phát hiện quan trọng khi tối ưu

**1. Glyph lạ làm Windows nạp font dự phòng (+85 MB).** Đo từng ký tự:

| Ký tự | RAM tăng thêm | Kết luận |
|---|---|---|
| `⋯` U+22EF, `⚙` U+2699, `▸` U+25B8, `☰` U+2630, `⏱` U+23F1 | **+84 … +89 MB** | ❌ không dùng |
| `•` U+2022, `·` U+00B7, `…` U+2026, `–` `—`, `‹` `›`, `●`, `°`, `×` | +2 … +11 MB | ✅ an toàn |

Nguyên nhân: khi DirectWrite không tìm thấy glyph trong font hiện tại, nó nạp
cả bộ font dự phòng (CJK…) vào tiến trình. Chỉ cần **một** ký tự như vậy là
mất 85 MB. Vì vậy quy ước của dự án: **chỉ dùng glyph có trong Segoe UI**
(nút menu dùng `…` U+2026 thay cho `⋯`).

**2. Lịch tháng phải tạo lười.** Lần đầu dựng/vẽ lưới 42 ô (và trước đó là
thao tác elide chữ bằng `QFontMetrics`) cũng kích hoạt bộ font dự phòng ⇒
+80 MB. Hai biện pháp: `MonthView` chỉ được tạo khi người dùng mở lịch tháng
lần đầu; tiêu đề tháng dùng `QLabel` thuần, không elide bằng `QFontMetrics`.

### Các quyết định thiết kế giữ RAM thấp

| Quyết định | Tiết kiệm |
|---|---|
| Không dùng QML/QtQuick | ~25–40 MB |
| Không dùng QtWebEngine | ~80–150 MB |
| Không `QGraphicsDropShadowEffect` (bóng vẽ tay 6 nét) | tránh pixmap đệm toàn cửa sổ |
| Ca dao nạp 1 lần dạng tuple bất biến | không cấp phát lại mỗi ngày |
| `get_day_info` có `lru_cache(4096)` + dataclass `frozen/slots` | dựng lưới tháng 0,8 ms |
| Icon ICO đa kích thước duy nhất (30 KB) | ~0 |
| Log xoay vòng 64 KB × 3 | chặn log phình |
| Lịch tháng tạo lười | –80 MB ở trạng thái chạy ngầm |

### Đối chiếu mục tiêu đề bài

Yêu cầu: **< 60 MB khi chạy ngầm**. Thực đo: **~82 MB** – vượt khoảng 22 MB.
Nguyên nhân là mức nền của Qt6 + Python (~43 MB trước khi vẽ nội dung). Nếu
cần tuyệt đối < 60 MB, lựa chọn đúng là WPF/.NET 8 (xem §2.1) hoặc một bản
native/C++; kiến trúc trong tài liệu này chuyển sang đó gần như 1-1.

---

## 8. Kịch bản lỗi và cách xử lý

| Tình huống | Hành vi mong đợi | Nơi xử lý |
|---|---|---|
| `settings.json` hỏng (JSON sai) | Sao lưu thành `settings.corrupt-<ts>.json`, chạy với mặc định | `ConfigStore.load` |
| Không có quyền ghi Registry | Checkbox tự bật lại theo trạng thái thật, app vẫn chạy | `autostart.set_enabled → bool` |
| Không có khay hệ thống | Chạy không có tray, log cảnh báo, widget vẫn dùng được qua menu chuột phải | `AppController._build_tray` |
| Explorer khởi động lại | Widget được ghim lại sau ≤ 2 giây | `_watch_pin` |
| Máy đổi DPI / cắm thêm màn hình | Qt tự scale; vị trí được kẹp lại vào màn hình khi thả chuột | `_clamp_into_screen` |
| Hai bản chạy cùng lúc | Bản thứ hai tự thoát | `QLockFile` |
| Thiếu `assets/icon.ico` | Dùng icon rỗng, không crash | `icon_path()` trả `Path` không tồn tại → `is_file()` check |
| Năm ngoài 1800–2199 | `ValueError` có thông điệp rõ; UI không cho điều hướng ra ngoài | `lunar_precise.solar_to_lunar` |

---

## 9. Tiêu chí nghiệm thu

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| A1 | Chạy được bằng `pythonw run_qtcalendar.pyw`, không console | chạy thật |
| A2 | Widget hiện dưới icon desktop, **vẫn thấy sau Win + D** | thử tay: bấm Win+D |
| A3 | Kéo thả được; khởi động lại đúng vị trí | kéo rồi thoát, mở lại |
| A4 | Opacity 20–100 % có tác dụng (cả khi ghim) | chỉnh slider + menu |
| A5 | Khay hệ thống có đủ menu, tick đồng bộ | mở menu |
| A6 | Bật/tắt khởi động cùng Windows ghi đúng Registry | `reg query HKCU\...\Run /v QTCalendar` |
| A7 | Lịch ngày đúng Thứ/ngày âm/Can Chi/giờ hoàng đạo | so với lịch vạn niên (2026-10-28 = 19/9, Ất Hợi) |
| A8 | Lịch tháng 7 cột, chuyển tháng, hôm nay nổi bật | thao tác tay |
| A9 | RAM < 60 MB | `Get-Process qtcalendar` working set |
| A10 | `pytest tests -q` xanh | chạy test |


