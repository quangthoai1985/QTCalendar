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
5. [Độ trong suốt](#5-độ-trong-suốt)
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
| Windows 10/11 | Chỉ dùng API có từ Win7+ (`SetWindowPos`, `SetWinEventHook`, `FindWindowEx`), test trên Win11 25H2 |
| **RAM < 60 MB khi chạy ngầm** | Đo thực: xem §7 |
| Nhẹ, khởi động nhanh | Không dùng QML/WebEngine, không ORM, không framework DI |
| Không cần quyền admin | Mọi thao tác đều ở `HKCU` và desktop window của chính user |
| Cấu hình không bao giờ làm hỏng app | Clamp giá trị, backup tệp lỗi, ghi nguyên tử |
| Chạy được khi Explorer khởi động lại | Widget là cửa sổ top-level của chính app + watchdog – xem §4.4 |

---

## 2. Chọn công nghệ

Đề bài ưu tiên ba lựa chọn: **.NET 8 WPF / C#**, **Python PySide6**, **Tauri**.

### 2.1 Bảng so sánh

| Tiêu chí | .NET 8 WPF | **Python + PySide6** | Tauri (Rust + WebView2) |
|---|---|---|---|
| RAM khi chạy ngầm (đo thực tế) | ~35–50 MB | **~45–55 MB** (đo: nền 44,6 MB) | ~25–40 MB (nhưng + process WebView2 riêng ~60–100 MB) |
| Kích thước phát hành | ~70 MB self-contained / ~2 MB nếu máy có runtime | ~150 MB (PySide6) hoặc ~35 MB khi PyInstaller | ~8 MB |
| Thời gian phát triển UI tuỳ biến | Trung bình (XAML) | **Nhanh** (QSS giống CSS) | Chậm cho desktop-native (WebView chạy nền tảng web) |
| Gọi Win32 (SetWindowPos, Registry) | Rất tốt (P/Invoke) | **Rất tốt (ctypes)** | Tốt nhưng phải viết lớp Rust |
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
3. **Win32 interop đầy đủ** bằng `ctypes`: `SetWindowPos`, `SetWinEventHook`,
   `FindWindowEx`, `winreg` – không thiếu thứ gì so với P/Invoke của C#.
4. **Tốc độ phát triển UI**: QSS (gần như CSS) cho phép tạo "giấy – mực –
   đỏ" nhanh hơn XAML, và vẽ tay bằng `QPainter` cho kết quả thẩm mỹ cao hơn
   control có sẵn.

> Nếu đội phát triển có .NET 8 SDK, **WPF là lựa chọn tương đương** và có
> RAM thấp hơn chút. Kiến trúc trong tài liệu này (4 tầng, `settings.json`,
> ghim Desktop kiểu Rainmeter, Registry Run) chuyển sang C# gần như 1-1.

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
     │ bloc_view  month_view│        │ desktop_pin (Rainmeter)│
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

Đây là yêu cầu khó nhất và cũng là phần dễ làm sai nhất. Từ bản 1.0.1 (hoàn
thiện ở 1.0.2), dự án dùng **cơ chế kiểu Rainmeter**: widget **vẫn là cửa sổ
cấp cao nhất**, không gắn làm cửa sổ con của desktop nữa.

### 4.1 Vì sao cửa sổ thường bị ẩn khi nhấn Win + D?

`Win + D` (Show Desktop) không thu nhỏ từng ứng dụng mà **nâng lớp Desktop**
của Explorer lên trên mọi cửa sổ thường. Lớp Desktop là:

* `Progman` (chứa trực tiếp `SHELLDLL_DefView`) trên Windows 11 24H2 trở đi;
* `WorkerW` có con `SHELLDLL_DefView` trên Windows 10/11 bản cũ hơn.

Trong lúc đó Windows còn gửi cho cửa sổ các lệnh dời ra toạ độ
`(-32000, -32000)` hoặc cờ `SWP_HIDEWINDOW`. Một cửa sổ bình thường vì thế
hoặc bị che, hoặc bị giấu đi.

Ngoài ra cửa sổ cấp cao nhất còn xuất hiện trong Alt+Tab và taskbar — một
desktop widget thì không nên.

### 4.2 Giải pháp: cửa sổ top-level ở đáy Z-order + sentinel

```python
# src/qtcalendar/platform/desktop_pin.py  (rút gọn)
def pin(hwnd):
    exstyle = GetWindowLong(hwnd, GWL_EXSTYLE)
    SetWindowLong(hwnd, GWL_EXSTYLE, exstyle | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    _ensure_sentinel()        # cửa sổ STATIC 1×1 vô hình, đặt ở HWND_BOTTOM
    _setup_event_hook()       # SetWinEventHook(EVENT_SYSTEM_FOREGROUND)
    update_z_order(hwnd)

def update_z_order(hwnd):
    if is_show_desktop_active():                 # đang Win + D
        SetWindowPos(hwnd, HWND_TOPMOST, ...)    # nổi trên lớp Desktop
        SetWindowPos(hwnd, taskbar, ...)         # nhưng nằm dưới Taskbar
    else:
        SetWindowPos(hwnd, HWND_BOTTOM, ...)     # dưới mọi app, trên hình nền
```

Mọi lệnh `SetWindowPos` nội bộ dùng cờ `SWP_NOSENDCHANGING` để không tự
kích hoạt bộ lọc `WM_WINDOWPOSCHANGING` ở dưới.

**Phát hiện Show Desktop** (`is_show_desktop_active`), theo đúng thuật toán
Rainmeter:

1. Sentinel nằm ở `HWND_BOTTOM`. Bình thường lớp Desktop ở dưới sentinel.
2. Khi `Win + D`, Explorer nâng lớp Desktop lên ⇒ tìm cửa sổ *đứng sau* lớp
   Desktop trong Z-order (`FindWindowEx(0, host, "STATIC", "QTCalendarSystem")`)
   mà gặp sentinel ⇒ đang Show Desktop.
3. Bổ sung: nếu cửa sổ foreground chính là lớp Desktop (hoặc con của nó) thì
   cũng coi là Show Desktop.

**Phản ứng tức thì**: hook `EVENT_SYSTEM_FOREGROUND` (out-of-context, bỏ qua
tiến trình của chính mình) gọi `update_z_order` mỗi khi đổi cửa sổ active,
nên bấm `Win + D` hay click lại vào ứng dụng thì widget đổi tầng ngay, không
phải chờ timer.

**Chặn thông điệp** trong `CalendarWidget.nativeEvent` khi đang ghim:

| Thông điệp | Xử lý (`handle_windowposchanging`) |
|---|---|
| `WM_WINDOWPOSCHANGING` không mang `SWP_NOSENDCHANGING` (click, kéo thả) | thêm `SWP_NOZORDER` ⇒ click không làm widget nhảy lên trên các app |
| Toạ độ `≤ -30000` | thêm `SWP_NOMOVE \| SWP_NOSIZE` ⇒ không bị dời ra ngoài màn hình |
| Cờ `SWP_HIDEWINDOW` | đổi thành `SWP_SHOWWINDOW` ⇒ không bị giấu |
| `WM_SYSCOMMAND / SC_MINIMIZE` | nuốt luôn ⇒ không bị thu nhỏ |

### 4.3 Các phương án đã thử và loại

| Phương án | Vì sao loại |
|---|---|
| `HWND_TOPMOST` (luôn nổi) | Không phải "ghim sát mặt bàn": đè lên mọi cửa sổ |
| Chỉ `SetWindowPos(HWND_BOTTOM)` | Không có sentinel ⇒ không biết khi nào `Win + D`, widget bị lớp Desktop che |
| Hook bàn phím bắt Win+D | Hook toàn cục dễ bị antivirus chặn, không bắt được các cách Show Desktop khác (ví dụ nút ở góc phải taskbar) |
| `SetParent(Progman / WorkerW)` (bản ≤ 1.0.0) | Sống sót qua Win+D nhưng: cửa sổ con không ghép alpha từng điểm ảnh ⇒ phải vẽ **đục**, mất góc bo/bóng đổ, có quầng đen; bị UIPI chặn khi Explorer khác integrity level; gắn với màn hình chính; Explorer khởi động lại là mất cửa sổ |
| **Top-level `HWND_BOTTOM` + sentinel + WinEvent hook** | ✅ Giữ `WA_TranslucentBackground`, không cần quyền admin, không hook bàn phím, hoạt động trên mọi màn hình |

Người dùng vẫn chọn được chế độ "cửa sổ nổi + luôn trên cùng"
(`placement = "floating"`) trong Cài đặt.

### 4.4 Các cạm bẫy đã xử lý

| Cạm bẫy | Cách xử lý |
|---|---|
| **Click/kéo làm widget nhảy lên trên app khác** | `SWP_NOZORDER` trong `WM_WINDOWPOSCHANGING` (§4.2) |
| **Z-order bị app khác hoặc Explorer xáo trộn** | Watchdog `QTimer` 2 giây (`_watch_pin`): ghim lại nếu `!is_pinned(hwnd)`, hiện lại nếu bị ẩn (`SW_SHOWNOACTIVATE`), gọi lại `update_z_order` |
| **Explorer khởi động lại** | Widget và sentinel là cửa sổ của chính app nên không bị huỷ theo; `get_desktop_icons_host()` tìm lại lớp Desktop mới ở lần kiểm tra kế tiếp |
| **Mất focus của ứng dụng khác** | `Qt.WindowDoesNotAcceptFocus` + `WA_ShowWithoutActivating` + `WS_EX_NOACTIVATE` |
| **Hiện trong Alt+Tab / taskbar** | `Qt.Tool` + `WS_EX_TOOLWINDOW` |
| **Bỏ ghim** | `unpin()` khôi phục `GWL_EXSTYLE` đã lưu, đặt `HWND_NOTOPMOST`; khi không còn cửa sổ ghim nào thì gỡ hook và huỷ sentinel |
| **Đổi window flags khi đang ghim** | Qt tạo lại cửa sổ ⇒ `_unpin_before_flag_change()` bỏ ghim và lưu toạ độ trước, rồi ghim lại sau |
| **DPI scaling** | Qt 6 tự xử lý DPI theo monitor; cửa sổ được tạo là per-monitor-aware |
| **Đa màn hình** | Cửa sổ top-level dùng toạ độ màn hình ảo trực tiếp ⇒ ghim được ở mọi màn hình |
| **Kẹp cửa sổ vào màn hình** | Sau mỗi lần thả chuột: `_clamp_into_screen()` theo `availableGeometry()` |

---

## 5. Độ trong suốt

Vì widget luôn là cửa sổ cấp cao nhất (cả khi nổi lẫn khi ghim), Qt tự quản
lý `WS_EX_LAYERED` + `UpdateLayeredWindow` cho cửa sổ có
`WA_TranslucentBackground`, tức là **alpha từng điểm ảnh**.

Dự án **không** dùng `setWindowOpacity()` (nó làm mờ cả chữ) cũng như
`QGraphicsOpacityEffect`:

```python
def _apply_opacity(self) -> None:
    effect = self._stack.graphicsEffect()
    if effect is not None:
        self._stack.setGraphicsEffect(None)
    self.setWindowOpacity(1.0)

def _paper_opacity(self) -> float:
    """Độ mờ áp vào **màu giấy** (nền trong suốt, chữ đục 100%)."""
    return float(self._settings.opacity)
```

Độ mờ 20–100 % được nhúng thẳng vào **màu nền giấy** khi vẽ; chữ và chip
là widget con vẽ sau nên luôn đục 100 %. Kết quả giống nhau ở cả hai chế độ:
góc bo tròn trong suốt, bóng đổ giấy giữ nguyên, không quầng đen viền.

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
| Explorer khởi động lại | Widget không mất; Z-order được đặt lại sau ≤ 2 giây | `_watch_pin` |
| Máy đổi DPI / cắm thêm màn hình | Qt tự scale; vị trí được kẹp lại vào màn hình khi thả chuột | `_clamp_into_screen` |
| Hai bản chạy cùng lúc | Bản thứ hai tự thoát | `QLockFile` |
| Thiếu `assets/icon.ico` | Dùng icon rỗng, không crash | `icon_path()` trả `Path` không tồn tại → `is_file()` check |
| Năm ngoài 1800–2199 | `ValueError` có thông điệp rõ; UI không cho điều hướng ra ngoài | `lunar_precise.solar_to_lunar` |

---

## 9. Tiêu chí nghiệm thu

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| A1 | Chạy được bằng `pythonw run_qtcalendar.pyw`, không console | chạy thật |
| A2 | Widget nằm dưới mọi ứng dụng, **vẫn thấy sau Win + D** và không che Taskbar | thử tay: bấm Win+D, click app khác |
| A3 | Kéo thả được; khởi động lại đúng vị trí | kéo rồi thoát, mở lại |
| A4 | Opacity 20–100 % có tác dụng (cả khi ghim) | chỉnh slider + menu |
| A5 | Khay hệ thống có đủ menu, tick đồng bộ | mở menu |
| A6 | Bật/tắt khởi động cùng Windows ghi đúng Registry | `reg query HKCU\...\Run /v QTCalendar` |
| A7 | Lịch ngày đúng Thứ/ngày âm/Can Chi/giờ hoàng đạo | so với lịch vạn niên (2026-10-28 = 19/9, Ất Hợi) |
| A8 | Lịch tháng 7 cột, chuyển tháng, hôm nay nổi bật | thao tác tay |
| A9 | RAM < 60 MB | `Get-Process qtcalendar` working set |
| A10 | `pytest tests -q` xanh | chạy test |


