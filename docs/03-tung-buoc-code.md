# 03 — Từng bước xây dựng QT Calendar (kèm mã nguồn)

> Tài liệu này là "công thức nấu" đầy đủ: đi từ máy trắng tới ứng dụng đang
> chạy trên desktop Windows, **theo đúng thứ tự thực tế đã triển khai**.
> Mỗi bước gồm: mục tiêu → làm gì → mã nguồn cốt lõi → cách kiểm chứng.
>
> Hai phần được yêu cầu riêng và in đầy đủ ở đây: **thuật toán âm lịch**
> (§4–§5) và **ghim cửa sổ xuống Desktop** (§8).

Mục lục

1. [Chuẩn bị môi trường](#1-chuẩn-bị-môi-trường)
2. [Dựng khung dự án](#2-dựng-khung-dự-án)
3. [Kiểu dữ liệu và bảng màu](#3-kiểu-dữ-liệu-và-bảng-màu)
4. [Thuật toán âm lịch Hồ Ngọc Đức](#4-thuật-toán-âm-lịch-hồ-ngọc-đức)
5. [Lớp chính xác cao + Can Chi + tầng dịch vụ](#5-lớp-chính-xác-cao--can-chi--tầng-dịch-vụ)
6. [Cấu hình và kho ca dao](#6-cấu-hình-và-kho-ca-dao)
7. [Tầng Win32: đo đạc bằng ctypes](#7-tầng-win32-đo-đạc-bằng-ctypes)
8. [Ghim cửa sổ xuống Desktop](#8-ghim-cửa-sổ-xuống-desktop)
9. [Khởi động cùng Windows và khay hệ thống](#9-khởi-động-cùng-windows-và-khay-hệ-thống)
10. [Cửa sổ widget không viền](#10-cửa-sổ-widget-không-viền)
11. [Hai mặt lịch: bloc và lịch tháng](#11-hai-mặt-lịch-bloc-và-lịch-tháng)
12. [Bộ điều phối, kiểm thử và đóng gói](#12-bộ-điều-phối-kiểm-thử-và-đóng-gói)

---

## 1. Chuẩn bị môi trường

Máy phát triển dùng trong dự án: **Windows 11 25H2 (build 26200), Python 3.14.7,
PySide6 6.11.2, màn hình 1920×1200 @100 %**. Không cần .NET SDK, không cần
mạng để chạy.

```powershell
# Kiểm tra
python --version            # Python 3.14.7
python -c "import PySide6; print(PySide6.__version__)"   # 6.11.2

# Nếu máy chưa có PySide6 (cần mạng):
#   python -m pip install PySide6-Essentials
```

> **Bẫy 1 — mã hoá console.** PowerShell trên Windows không in được tiếng
> Việt nếu thiếu UTF-8. Luôn đặt trước khi chạy:
> `$env:PYTHONUTF8="1"` và gọi `python -X utf8 ...`.
>
> **Bẫy 2 — Qt không có font.** Khi render ảnh bằng `QT_QPA_PLATFORM=offscreen`,
> Qt không nạp font hệ thống ⇒ chữ thành ô vuông. Muốn ảnh đúng phải render
> trên nền tảng `windows` thật (xem `scripts/preview_bloc.py --native`).

---

## 2. Dựng khung dự án

```powershell
New-Item -ItemType Directory -Force E:\App\QTCalendar\src\qtcalendar\core
New-Item -ItemType Directory -Force E:\App\QTCalendar\src\qtcalendar\ui
New-Item -ItemType Directory -Force E:\App\QTCalendar\src\qtcalendar\platform
New-Item -ItemType Directory -Force E:\App\QTCalendar\src\qtcalendar\data
New-Item -ItemType Directory -Force E:\App\QTCalendar\tests, E:\App\QTCalendar\scripts, E:\App\QTCalendar\docs, E:\App\QTCalendar\assets
```

Bốn quy tắc kiến trúc được chốt **trước khi viết dòng code đầu tiên**:

1. `core/` **không được** import Qt → test bằng pytest không cần màn hình.
2. `platform/` chỉ `tray.py` dùng Qt; phần còn lại thuần `ctypes`/`winreg`.
3. `ui/` không đọc tệp cấu hình, không gọi Registry — chỉ phát tín hiệu.
4. Mọi lời gọi Win32 **không ném ngoại lệ**.

Điểm vào không console — `run_qtcalendar.pyw`:

```python
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from qtcalendar.app import main
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

---

## 3. Kiểu dữ liệu và bảng màu

`core/types.py` – mọi thứ UI cần nằm trong một `DayInfo` **bất biến**:

```python
@dataclass(frozen=True, slots=True)
class DayInfo:
    solar: date
    lunar: LunarDate
    weekday_index: int
    year_can_chi: CanChi
    month_can_chi: CanChi
    day_can_chi: CanChi
    zodiac: str
    tiet_khi: str
    auspicious_hours: tuple[AuspiciousHour, ...] = ()
    is_auspicious_day: bool = False
    holiday: str | None = None

    @property
    def lunar_day_text(self) -> str:        # "Mùng 1" / "Rằm" / "Ngày 12"
        d = self.lunar.day
        return "Rằm" if d == 15 else ("Mùng 1" if d == 1 else
               (f"Mùng {d}" if d < 10 else f"Ngày {d}"))
```

`core/theme.py` gom toàn bộ màu vào 4 bảng màu (`giay_do`, `xanh_ngoc`,
`hoang_hon`, `dem_sao`). Đổi giao diện = đổi một dict, không sửa view.

---

## 4. Thuật toán âm lịch Hồ Ngọc Đức

Đây là "trái tim" của ứng dụng. Toàn bộ nằm ở `core/lunar.py` (~330 dòng).
Sáu nguyên hàm, theo đúng công bố gốc:

### 4.1 Số ngày Julius (JDN) – quy mọi ngày về một số nguyên

```python
def jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:                       # trước 15/10/1582 dùng lịch Julius
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd
```

### 4.2 Điểm Sóc (New Moon) – chuỗi 25 số hạng của Meeus

```python
def new_moon(k: int) -> float:
    t = k / 1236.85
    t2, t3 = t * t, t * t * t
    dr = PI / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m   = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f   = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1  = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 -= 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * mpr)
    c1 += 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 -= 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 -= 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 += 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))
    if t < -11:
        deltat = (0.001 + 0.000839 * t + 0.0002261 * t2
                  - 0.00000845 * t3 - 0.000000081 * t * t3)
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    return jd1 + c1 - deltat          # JDN có phần lẻ

def get_new_moon_day(k: int, timezone: int = 7) -> int:
    return math.floor(new_moon(k) + 0.5 + timezone / 24)   # ngày giờ Hà Nội
```

### 4.3 Kinh độ mặt trời và 12 trung khí

```python
def sun_longitude(jdn: float) -> float:
    t = (jdn - 2451545.0) / 36525
    m  = 357.52910 + 35999.05030 * t - 0.0001559 * t * t
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t * t
    dl = (1.914600 - 0.004817 * t) * math.sin(m * PI / 180)
    dl += 0.019993 * math.sin(2 * m * PI / 180) + 0.000290 * math.sin(3 * m * PI / 180)
    l = (l0 + dl) * PI / 180
    return l - 2 * PI * math.floor(l / (2 * PI))

def get_sun_longitude(day_number: int, timezone: int = 7) -> int:
    """Chỉ số trung khí 0..11 tại nửa đêm giờ địa phương của ngày đó."""
    return math.floor(sun_longitude(day_number - 0.5 - timezone / 24) / PI * 6)
```

### 4.4 Tháng 11 và tháng nhuận

```python
def get_lunar_month_11(yy: int, timezone: int = 7) -> int:
    """Ngày bắt đầu tháng 11 âm lịch = tháng chứa Đông chí."""
    off = jd_from_date(31, 12, yy) - 2415021
    k = math.floor(off / 29.530588853)
    nm = get_new_moon_day(k, timezone)
    if get_sun_longitude(nm, timezone) >= 9:      # đã qua Đông chí ⇒ lùi 1 sóc
        nm = get_new_moon_day(k - 1, timezone)
    return nm

def get_leap_month_offset(a11: int, timezone: int = 7) -> int:
    """Tháng nhuận = tháng đầu tiên không chứa trung khí."""
    k = math.floor((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last, i = 0, 1
    arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
    while i < 14:
        last, i = arc, i + 1
        arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
        if arc == last:      # hai tháng cùng đoạn 30° ⇒ tháng trước thiếu trung khí
            break
    return i - 1
```

### 4.5 Chuyển đổi hai chiều

```python
def solar_to_lunar(dd, mm, yy, timezone: int = 7) -> LunarDate:
    day_number = jd_from_date(dd, mm, yy)
    k = math.floor((day_number - 2415021.076998695) / 29.530588853)
    month_start = get_new_moon_day(k + 1, timezone)
    if month_start > day_number:
        month_start = get_new_moon_day(k, timezone)

    a11 = get_lunar_month_11(yy, timezone)
    b11 = a11
    if a11 >= month_start:
        lunar_year, a11 = yy, get_lunar_month_11(yy - 1, timezone)
    else:
        lunar_year, b11 = yy + 1, get_lunar_month_11(yy + 1, timezone)

    lunar_day = day_number - month_start + 1
    diff = math.floor((month_start - a11) / 29)
    lunar_leap, lunar_month = False, diff + 11
    if b11 - a11 > 365:                      # 13 tuần trăng ⇒ có tháng nhuận
        leap_month_diff = get_leap_month_offset(a11, timezone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return LunarDate(lunar_day, lunar_month, lunar_year, lunar_leap)

def lunar_to_solar(day, month, year, leap=False, timezone: int = 7) -> date:
    if month < 11:
        a11, b11 = (get_lunar_month_11(year - 1, timezone),
                    get_lunar_month_11(year, timezone))
    else:
        a11, b11 = (get_lunar_month_11(year, timezone),
                    get_lunar_month_11(year + 1, timezone))
    k = math.floor((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    off = month - 11
    if off < 0:
        off += 12
    if b11 - a11 > 365:
        leap_off = get_leap_month_offset(a11, timezone)
        leap_month = leap_off - 2
        if leap_month < 0:
            leap_month += 12
        if leap and month != leap_month:
            raise ValueError(f"Tháng {month} không phải tháng nhuận của năm {year}")
        elif leap or off >= leap_off:
            off += 1
    elif leap:
        raise ValueError(f"Năm {year} không có tháng nhuận")
    month_start = get_new_moon_day(k + off, timezone)
    dd, mm, yy = jd_to_date(month_start + day - 1)
    return date(yy, mm, dd)
```

### 4.6 Kiểm chứng

```powershell
$env:PYTHONUTF8="1"
python -X utf8 scripts\audit_calendar.py 2026 10     # bảng tháng 7 cột
python -X utf8 scripts\audit_calendar.py --year 2023 # 13 tháng, có "Tháng Hai (nhuận)"
python -X utf8 -m pytest tests -q                    # 448+ test
```

Kết quả đã kiểm: 31/31 ngày Tết (1985–2040), 18/18 tháng nhuận, quét liên
tục 109.938 ngày (1900–2200) **0 lỗi**.

---

## 5. Lớp chính xác cao + Can Chi + tầng dịch vụ

### 5.1 Vì sao cần lớp thứ hai

Công thức gốc có sai số ±50 phút. Đo trên 185 tuần trăng (2020–2034) thấy
**4 lần lệch hẳn 1 ngày**, trong đó tháng nhuận 2023 bị gán sai tên. Vì vậy
`core/lunar_precise.py` giữ nguyên triết lý HND nhưng thay:

* sóc: 25 số hạng + 14 số hạng nhiễu hành tinh của Meeus, có ΔT;
* trung khí: xét tại **nửa đêm ngày mùng 1** (tháng âm tính theo ngày);
* đánh số tháng: **bảng tháng liên tục** neo theo tháng chứa Đông chí
  (xử lý được cả tháng 11/12 nhuận – bài toán "2033").

### 5.2 Can Chi

```python
def year_can_chi(year):  return CanChi(CAN[(year+6) % 10], CHI[(year+8) % 12])
def month_can_chi(m, y): return CanChi(CAN[(2*((y+6) % 10) + m + 1) % 10],
                                       CHI[(m+1) % 12])
def day_can_chi(day):
    jdn = jd_from_date(day.day, day.month, day.year)
    return CanChi(CAN[(jdn+9) % 10], CHI[(jdn+1) % 12])   # mốc 01/01/2000 = Mậu Ngọ
```

### 5.3 Giờ hoàng đạo

```python
def auspicious_hours(day: date) -> tuple[AuspiciousHour, ...]:
    jdn = jd_from_date(day.day, day.month, day.year)
    thanh_long = (2 * ((jdn + 1) % 12) + 8) % 12   # Thanh Long theo chi ngày
    out = []
    for h in range(12):                            # h = 0 là canh Tý 23h–01h
        if (h - thanh_long) % 12 in (0, 1, 4, 5, 7, 10):
            start = (23 + 2 * h) % 24
            out.append(AuspiciousHour(CHI[h], start, (start + 2) % 24,
                                      HOUR_GODS[(h - thanh_long) % 12]))
    return tuple(out)
```

### 5.4 Tầng dịch vụ

`core/calendar_service.py` là nơi duy nhất UI lấy dữ liệu:

```python
@lru_cache(maxsize=4096)
def get_day_info(day: date, engine: str = "precise") -> DayInfo: ...

def build_month_grid(year, month, engine="precise", first_day_of_week=0) -> MonthGrid:
    first = date(year, month, 1)
    lead = (first.weekday() - first_day_of_week) % 7
    start = first - timedelta(days=lead)
    rows = -(-(lead + calendar.monthrange(year, month)[1]) // 7)
    weeks = tuple(tuple(get_day_info(start + timedelta(days=r*7+c), engine)
                        for c in range(7)) for r in range(rows))
    return MonthGrid(year, month, weeks)
```

Cache + dataclass bất biến ⇒ dựng lưới tháng (42 ô) chỉ tốn **0,8 ms**.

---

## 6. Cấu hình và kho ca dao

`core/config.py`: `Settings` (26 trường) + `ConfigStore` ghi **nguyên tử**
(`.tmp` → `os.replace`), kẹp mọi giá trị sai về khoảng hợp lệ, sao lưu tệp
hỏng thành `settings.corrupt-<ts>.json`.

```python
def config_path() -> Path:
    if override := os.environ.get("QTCALENDAR_CONFIG"):
        return Path(override)
    portable = app_root() / "settings.json"       # chế độ portable
    if portable.is_file():
        return portable
    return data_dir() / "settings.json"           # %LOCALAPPDATA%\QTCalendar
```

`core/quotes.py` + `data/quotes.json` (439 câu: 200 ca dao, 160 tục ngữ,
79 danh ngôn). `quote_of_day()` dùng `date.toordinal()` nên ổn định giữa các
lần chạy; tệp hỏng thì trả câu dự phòng.

---

## 7. Tầng Win32: đo đạc bằng ctypes

`platform/win32.py` khai báo `user32`, `shell32`, `kernel32` và bọc mọi hàm:

```python
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = ctypes.c_void_p
user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.SetParent.restype = ctypes.c_void_p

def get_parent(hwnd: int) -> int:
    try:
        return int(user32.GetParent(ctypes.c_void_p(hwnd)) or 0)
    except Exception:
        return 0
```

Quy ước: HWND dùng `c_void_p` (an toàn 32/64-bit), `GetWindowLongW` được che
`& 0xFFFFFFFF` để không dính bit dấu của `WS_POPUP`.

---

## 8. Ghim cửa sổ xuống Desktop

> Từ bản 1.0.1 dự án bỏ `SetParent(Progman)` và chuyển sang **cơ chế kiểu
> Rainmeter**. Lý do và phân tích đầy đủ ở `docs/01-kien-truc.md` §4.

### 8.1 Nguyên lý

* Widget **vẫn là cửa sổ cấp cao nhất**, nằm ở `HWND_BOTTOM`: dưới mọi ứng
  dụng, trên hình nền. Nhờ vậy Qt giữ nguyên `WA_TranslucentBackground`
  (alpha từng điểm ảnh, góc bo, bóng đổ).
* `WS_EX_TOOLWINDOW` ⇒ không có trong taskbar/Alt+Tab; `WS_EX_NOACTIVATE`
  ⇒ click không cướp focus.
* `Win + D` nâng lớp Desktop (`Progman` trên Win11 24H2+, `WorkerW` chứa
  `SHELLDLL_DefView` trên bản cũ) lên trên. Một cửa sổ **sentinel** vô hình ở
  `HWND_BOTTOM` giúp phát hiện điều đó; khi ấy widget được nâng lên
  `HWND_TOPMOST` rồi chèn ngay dưới Taskbar.

### 8.2 Mã nguồn chính

`platform/desktop_pin.py` (rút gọn):

```python
SENTINEL_CLASS = "STATIC"
SENTINEL_TITLE = "QTCalendarSystem"
ZPOS_FLAGS = (SWP_NOMOVE | SWP_NOSIZE | SWP_NOOWNERZORDER
              | SWP_NOACTIVATE | SWP_NOSENDCHANGING)


def is_show_desktop_active() -> bool:
    host = get_desktop_icons_host()          # Progman hoặc WorkerW chứa DefView
    if not host or not win32.is_window_visible(host):
        return False
    sentinel = _ensure_sentinel()
    # Lớp Desktop bị nâng lên trên sentinel ⇒ đang Show Desktop
    if sentinel and win32.find_window_ex(0, host, SENTINEL_CLASS, SENTINEL_TITLE) == sentinel:
        return True
    fg = win32.get_foreground_window()
    return bool(fg and (fg == host or win32.get_ancestor(fg, 2) == host))


def update_z_order(hwnd: int) -> None:
    if is_show_desktop_active():
        win32.set_window_pos(hwnd, win32.HWND_TOPMOST, 0, 0, 0, 0, ZPOS_FLAGS)
        taskbar = win32.find_window("Shell_TrayWnd")
        if taskbar and win32.is_window_visible(taskbar):
            win32.set_window_pos(hwnd, taskbar, 0, 0, 0, 0, ZPOS_FLAGS)
    else:
        win32.set_window_pos(hwnd, win32.HWND_BOTTOM, 0, 0, 0, 0, ZPOS_FLAGS)


def pin(hwnd: int) -> bool:
    exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
    style = win32.get_window_long(hwnd, win32.GWL_STYLE)
    _saved_states[hwnd] = _PinState(hwnd=hwnd, exstyle=exstyle, style=style)
    win32.set_window_long(hwnd, win32.GWL_EXSTYLE,
                          exstyle | win32.WS_EX_TOOLWINDOW | win32.WS_EX_NOACTIVATE)
    _ensure_sentinel()
    _setup_event_hook()                      # SetWinEventHook(EVENT_SYSTEM_FOREGROUND)
    update_z_order(hwnd)
    _pinned_hwnds.add(hwnd)
    return True


def unpin(hwnd: int) -> bool:
    if hwnd in _saved_states:
        win32.set_window_long(hwnd, win32.GWL_EXSTYLE, _saved_states.pop(hwnd).exstyle)
    win32.set_window_pos(hwnd, win32.HWND_NOTOPMOST, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOSENDCHANGING)
    _pinned_hwnds.discard(hwnd)
    if not _pinned_hwnds:                    # không còn ai ghim ⇒ dọn dẹp
        _cleanup_event_hook()
        _cleanup_sentinel()
    return True
```

Hook `EVENT_SYSTEM_FOREGROUND` (cờ `WINEVENT_OUTOFCONTEXT |
WINEVENT_SKIPOWNPROCESS`) gọi `update_z_order` cho mọi cửa sổ đang ghim mỗi
khi cửa sổ active thay đổi, nên widget đổi tầng ngay khi bấm `Win + D` hoặc
click lại vào ứng dụng. Tham chiếu tới callback ctypes được giữ trong biến
module (`_hook_proc_ref`) để không bị GC thu hồi.

### 8.3 Các cạm bẫy phải xử lý ở tầng UI

| Cạm bẫy | Cách xử lý trong `ui/widget_window.py` |
|---|---|
| **Windows giấu/dời cửa sổ khi Show Desktop** (toạ độ `-32000`, cờ `SWP_HIDEWINDOW`) | `nativeEvent` bắt `WM_WINDOWPOSCHANGING` và gọi `desktop_pin.handle_windowposchanging()`: bỏ dời, đổi `SWP_HIDEWINDOW` thành `SWP_SHOWWINDOW`; nuốt `WM_SYSCOMMAND / SC_MINIMIZE` |
| **Click/kéo làm widget nhảy lên trên app khác** | Cũng trong `handle_windowposchanging`: thông điệp không mang `SWP_NOSENDCHANGING` (tức không phải lệnh nội bộ) được thêm `SWP_NOZORDER` |
| **Z-order bị xáo trộn theo thời gian** | Watchdog `_pin_timer` 2 giây (`_watch_pin`): ghim lại nếu `!is_pinned`, hiện lại bằng `SW_SHOWNOACTIVATE` nếu bị ẩn, gọi `update_z_order` |
| **Đổi window flags khi đang ghim** (Qt tạo lại native window) | `_unpin_before_flag_change()` bỏ ghim và lưu toạ độ từ `GetWindowRect` trước mọi `setWindowFlags`, sau đó `_apply_placement()` ghim lại |
| **"Luôn nổi" và "ghim" loại trừ nhau** | `set_always_on_top(True)` khi đang ghim thì tự chuyển `placement = "floating"` |

Ngoài ra: `Qt.WindowDoesNotAcceptFocus` + `WA_ShowWithoutActivating` để
không cướp focus, `Qt.Tool` để không có trong taskbar/Alt+Tab.

### 8.4 Độ trong suốt khi đã ghim

Không cần xử lý riêng: cửa sổ vẫn là top-level nên alpha từng điểm ảnh hoạt
động như ở chế độ nổi. Độ mờ được nhúng vào **màu giấy** (xem §10.2), còn
`_apply_opacity()` chỉ bảo đảm `windowOpacity = 1.0` và không có
`QGraphicsOpacityEffect`:

```python
def _apply_opacity(self) -> None:
    effect = self._stack.graphicsEffect()
    if effect is not None:
        self._stack.setGraphicsEffect(None)
    self.setWindowOpacity(1.0)
```

---

## 9. Khởi động cùng Windows và khay hệ thống

### 9.1 Registry (không cần admin)

```python
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def build_command() -> str:
    exe = Path(sys.executable).with_name("pythonw.exe")   # KHÔNG dùng python.exe
    launcher = project_root() / "run_qtcalendar.pyw"
    return f'"{exe}" "{launcher}"'

def enable() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, build_command())
        return True
    except OSError:
        log.warning("Không bật được khởi động cùng Windows")
        return False
```

Dùng `pythonw.exe` để **không hiện cửa sổ console đen** khi khởi động.

### 9.2 Khay hệ thống

`platform/tray.py` dựng `QSystemTrayIcon` + `QMenu` với 11 tín hiệu
(`toggled_visibility`, `view_requested`, `opacity_requested`, `pin_toggled`,
`topmost_toggled`, `lock_toggled`, `autostart_toggled`, `settings_requested`,
`today_requested`, `reset_position_requested`, `quit_requested`) và
`set_state(settings)` để đồng bộ dấu tick.

---

## 10. Cửa sổ widget không viền

`ui/widget_window.py` (~700 dòng) – phần "khung xương":

```python
flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
if settings.always_on_top and settings.placement == "floating":
    flags |= Qt.WindowStaysOnTopHint
self.setWindowFlags(flags)
self.setAttribute(Qt.WA_TranslucentBackground, True)
self.setAttribute(Qt.WA_ShowWithoutActivating, True)
```

Kéo thả + lưu vị trí:

```python
def mousePressEvent(self, event):
    if event.button() == Qt.LeftButton and not self._settings.lock_position:
        self._dragging = True
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

def mouseMoveEvent(self, event):
    if self._dragging:
        self.move(event.globalPosition().toPoint() - self._drag_offset)

def mouseReleaseEvent(self, event):
    if self._dragging and event.button() == Qt.LeftButton:
        self._dragging = False
        self._clamp_into_screen()      # không để widget lọt ra ngoài màn hình
        self._store_geometry()         # ghi settings.x/y (dùng GetWindowRect nếu đang ghim)
        self.settings_changed.emit()   # app.py lưu có debounce 500 ms
```

Bóng đổ vẽ tay (rẻ hơn `QGraphicsDropShadowEffect`):

```python
def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing, True)
    rect, radius = self._card_rect(), self._theme.radius
    shadow = QColor(self._theme.shadow)
    for i in range(6, 0, -1):
        painter.setPen(QPen(QColor(shadow.red(), shadow.green(), shadow.blue(),
                                   int(6 + (7 - i) * 4))))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(-i, -i + 1, i, i + 2),
                                radius + i, radius + i)
```

### 10.1 Tay nắm kéo giãn + nội dung tự phóng theo kích thước

Widget có một tay nắm nhỏ ở góc dưới phải để người dùng kéo to/nhỏ. Tay nắm
là widget con vẽ ba nét chéo; nó chuyển sự kiện chuột cho cửa sổ:

```python
GRIP_SIZE = 18
MIN_WIDTH, MIN_HEIGHT = 260, 330
MAX_WIDTH, MAX_HEIGHT = 1000, 1300


class _ResizeGrip(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setToolTip("Kéo để phóng to / thu nhỏ widget")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(self._color); pen.setWidthF(1.6); pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        size, margin = min(self.width(), self.height()), 4.0
        for step in range(3):
            offset = margin + step * (size - 2 * margin) / 2.6
            painter.drawLine(int(size - offset), self.height() - int(margin),
                             int(size - margin), self.height() - int(offset))

    def mousePressEvent(self, event):
        self._owner.begin_resize(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._owner.drag_resize(event.globalPosition().toPoint())
```

Logic nằm ở cửa sổ (một chỗ duy nhất), có kẹp giới hạn và kẹp theo màn hình:

```python
def begin_resize(self, global_pos):
    self._resizing = True
    self._resize_start_size = QSize(self.width(), self.height())
    self._resize_start_pos = global_pos

def drag_resize(self, global_pos):
    if not self._resizing:
        return
    delta = global_pos - self._resize_start_pos
    avail = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
    max_w = min(MAX_WIDTH, max(MIN_WIDTH, avail.width() - 2 * SHADOW_MARGIN))
    max_h = min(MAX_HEIGHT, max(MIN_HEIGHT, avail.height() - 2 * SHADOW_MARGIN))
    self.resize(_clamp_size(self._resize_start_size.width() + delta.x(), MIN_WIDTH, max_w),
                _clamp_size(self._resize_start_size.height() + delta.y(), MIN_HEIGHT, max_h))

def end_resize(self):
    self._resizing = False
    self._clamp_into_screen()
    self._store_geometry()          # ghi settings.width/height
    self.settings_changed.emit()    # app.py lưu ngay (debounce 500 ms)
```

Để kéo to mà nội dung cũng to (không phải chỉ thêm giấy trống), hệ số phóng
truyền cho các view được suy ra từ kích thước cửa sổ:

```python
def content_scale(self) -> float:
    ratio = min(self.width() / BASE_WIDTH, self.height() / BASE_HEIGHT)
    return max(0.5, min(2.6, self._settings.scale * ratio))

def resizeEvent(self, event):
    super().resizeEvent(event)
    self._layout_grip()
    self._content_scale_timer.start()      # gộp 90 ms rồi mới áp dụng
```

`BlocView`/`MonthView` nhận hệ số này qua `apply_theme(theme, scale)` và tự
giới hạn lại một lần nữa theo kích thước thật của chúng, nên không bao giờ
tràn. Menu chuột phải có thêm **"Đặt lại kích thước (344×468)"**.

### 10.2 Độ mờ **chỉ trên nền** + màu nền tuỳ chọn

Yêu cầu của người dùng: *"khoá opacity của chữ, chỉ giảm độ trong suốt của
nền"*. Cách làm sai (và là cách cũ) là `setWindowOpacity()` hoặc
`QGraphicsOpacityEffect` — cả hai làm mờ **toàn bộ** nội dung, chữ nhạt nhoà
trên hình nền sáng.

Cách đúng: nhúng độ mờ vào **màu giấy**. Ở `core/theme.py`:

```python
def paper_theme(theme: Theme, opacity: float = 1.0, bg_color: str = "") -> Theme:
    base = with_background(theme, bg_color)          # đổi màu nền (nếu có)
    a = max(0.0, min(1.0, float(opacity)))
    if a >= 0.999:
        return base
    return replace(                                   # dataclasses.replace
        base,
        paper=_with_alpha(base.paper, a),             # "#AARRGGBB"
        paper_2=_with_alpha(base.paper_2, a),
        paper_edge=_with_alpha(base.paper_edge, min(1.0, a + 0.18)),
    )
```

Còn `with_background()` đổi màu giấy và **tự đổi bộ mực** theo độ sáng nền
(nền tối → chữ sáng như theme "Đêm sao"), nhờ vậy người dùng chọn nền đen vẫn
đọc được chữ:

```python
def with_background(theme: Theme, color: str) -> Theme:
    if not color or not is_valid_color(color):
        return theme
    dark_bg = _luminance(color) < 0.42
    base = theme if dark_bg == theme.dark else THEMES["dem_sao" if dark_bg else "giay_do"]
    toward = "#FFFFFF" if dark_bg else "#000000"
    return replace(base, name=theme.name, display_name=theme.display_name,
                   dark=dark_bg, paper=color,
                   paper_2=_mix(color, toward, 0.07),
                   paper_edge=_mix(color, toward, 0.16),
                   hover_bg=_mix(color, toward, 0.09))
```

Hai view vẽ nền cần hai thay đổi nhỏ:

1. **Phải vẽ nền trong một lớp ảnh riêng rồi mới áp độ mờ**, vì vân giấy/ánh
   sáng/vignette là nhiều lớp trong suốt cộng dồn — nếu vẽ trực tiếp với
   `painter.setOpacity()` thì các lớp cộng lại làm nền gần như đục trở lại:

```python
def paintEvent(self, event):
    alpha = alpha_of(self._theme.paper)
    painter = QPainter(self)
    if alpha < 0.999:
        painter.setOpacity(alpha)                 # chỉ nền mờ
        painter.drawPixmap(0, 0, self._background_layer())   # lớp nền đục, có cache
    else:
        self._paint_background(painter)
    painter.end()                                 # chữ/chip là widget con ⇒ vẽ sau, đục 100 %
```

2. Cửa sổ **luôn** `setWindowOpacity(1.0)` và gỡ mọi `QGraphicsOpacityEffect`;
   độ mờ do màu giấy quyết định.

Menu chuột phải có thêm hai mục: **"Độ trong suốt (nền)"** và **"Màu nền
giấy"** (10 màu gợi ý trong `BACKGROUND_PRESETS`, "Theo giao diện", và "Màu
tuỳ chọn…" mở `QColorDialog`).

Kiểm chứng tự động bằng kênh alpha của ảnh render:

| Độ mờ | alpha nền | alpha chữ |
|---|---|---|
| 100 % | 255 | 255 |
| 60 % | **152** | **255** |
| 30 % | **75** | **255** |

(tức là chỉ nền trong đi, chữ giữ nguyên độ đục — xem
`scripts/preview_paper.py` và `tests/test_theme_paper.py`).

**Bài học hiệu năng quan trọng**: không dùng các glyph tượng hình như `⋯`
(U+22EF), `⚙`, `▸` làm chữ trong nút. Khi Windows không tìm thấy glyph,
DirectWrite nạp cả bộ font dự phòng, tốn thêm **~85 MB RAM** (đo thực nghiệm).
Chỉ dùng glyph có trong Segoe UI: `• · … – — ‹ › ● ° ×`. Nút menu vì vậy
dùng `"…"` (U+2026), không dùng `"⋯"`.

---

## 11. Hai mặt lịch: bloc và lịch tháng

### 11.1 Lịch bloc (`ui/bloc_view.py`, ~1.100 dòng)

Vẽ tay toàn bộ trên `QPainter` (không dùng widget con cho từng dòng) theo
bố cục: dải gáy 5 lỗ → THỨ (chữ giãn cách) → số ngày cực lớn (tự fit cả
rộng lẫn cao) → "THÁNG 10 · 2026" → divider → âm lịch → Can Chi → badge tiết
khí/ngày lễ/ngày hoàng đạo → 6 chip giờ hoàng đạo → ca dao (≤3 dòng, tự
giảm 3→2→1 khi khung thấp) → nguồn.

### 11.2 Lịch tháng (`ui/month_view.py`, ~1.000 dòng)

Lưới `QGridLayout` 7 cột × 5–6 hàng, ô là `_DayCell` tự vẽ (không widget
con), số hàng co theo số tuần thực tế của tháng. Header ‹ Tháng 10 / 2026 ›,
chân có `● Hôm nay…` + cặp nút `[Ngày] [Hôm nay]`.

Hai bẫy hiệu năng đã xử lý:

1. **Tạo lười**: `MonthView` chỉ được tạo ở lần đầu người dùng mở lịch tháng
   (`_ensure_month()`), vì lần vẽ đầu tốn thêm ~80 MB cho bộ font dự phòng.
2. **Không elide bằng `QFontMetrics` lúc `setText`** (cũng kích hoạt bộ font
   dự phòng): tiêu đề dùng `QLabel` thuần, để layout tự cắt.

### 11.3 QSS (`ui/styles.py`)

`build_stylesheet(theme, scale)` sinh QSS từ token; mọi màu/cỡ chữ đều đi
qua helper `px()`. Selector được đặt tên theo vai trò (`#WeekdayLabel`,
`#SolarDayLabel`, `#DayCell`, `#NavButton`…).

---

## 12. Bộ điều phối, kiểm thử và đóng gói

### 12.1 `app.py` – nối mọi thứ

```python
class AppController(QObject):
    def __init__(self, app, settings, store, lock):
        self._widget = CalendarWidget(settings)
        self._build_tray()       # nếu khay hệ thống không có thì vẫn chạy
        self._wire()             # nối 11 tín hiệu tray ↔ widget

    def start(self):
        self._widget.restore_position()
        if not self._settings.hidden:
            self._widget.show()
        QTimer.singleShot(0, self._apply_placement_later)   # ghim sau khi có HWND
```

Ba timer: `_midnight_timer` (đổi ngày), `_quote_timer` (30 phút, chế độ ngẫu
nhiên), `_pin_timer` (2 giây, watchdog desktop). Ghi cấu hình có debounce
500 ms; khi thoát ghi ngay.

### 12.2 Chế độ dòng lệnh để kiểm thử

```powershell
python run_qtcalendar.pyw --info                        # in JSON âm lịch hôm nay
python run_qtcalendar.pyw --smoke out.png --view month  # dựng widget, chụp ảnh
python run_qtcalendar.pyw --reset                       # xoá cấu hình
python run_qtcalendar.pyw --version
```

### 12.3 Kiểm thử

```powershell
$env:PYTHONUTF8="1"
python -X utf8 -m pytest tests -q                       # ~448 passed, 11 xfailed
python -X utf8 scripts\preview_bloc.py --native         # ảnh bloc 4 theme
python -X utf8 scripts\preview_month.py                 # ảnh lịch tháng + hộp thoại
python -X utf8 scripts\verify_live.py                   # chạy app thật, đo RAM, đọc HWND
```

### 12.4 Đóng gói

```powershell
# 1) Chạy trực tiếp (khuyến nghị khi phát triển)
pythonw run_qtcalendar.pyw

# 2) Đóng gói bằng PyInstaller
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name "QT Calendar" `
  --icon assets\icon.ico --add-data "assets;assets" `
  --paths src run_qtcalendar.pyw
# → dist\QT Calendar\QT Calendar.exe
```

`--windowed` là bắt buộc để không có cửa sổ console. `--add-data` chép icon
vào bản đóng gói; nếu thiếu, ứng dụng vẫn chạy nhưng icon trống.

---

### Bảng tóm tắt thứ tự thực hiện

| Bước | File | Dòng | Kiểm chứng |
|---|---|---|---|
| 1 | môi trường | – | `python -c "import PySide6"` |
| 2 | khung dự án | – | `run_qtcalendar.pyw` import được |
| 3 | `core/types.py`, `theme.py` | ~500 | `python -c "from qtcalendar.core.types import DayInfo"` |
| 4 | `core/lunar.py` | ~330 | audit_calendar 2026 10, 2023 3 |
| 5 | `lunar_precise.py`, `canchi.py`, `calendar_service.py` | ~1.000 | pytest tests/test_lunar_precise.py |
| 6 | `config.py`, `quotes.py`, `data/quotes.json` | ~600 | pytest tests/test_config.py tests/test_quotes.py |
| 7 | `platform/win32.py` | ~700 | `scripts/probe_desktop_pin.py` |
| 8 | `platform/desktop_pin.py` | ~460 | `pytest tests/test_desktop_pin.py` + thử tay `Win + D` |
| 9 | `platform/autostart.py`, `tray.py` | ~600 | `reg query HKCU\...\Run` |
| 10 | `ui/widget_window.py` | ~700 | smoke + kéo thả tay |
| 11 | `bloc_view.py`, `month_view.py`, `styles.py` | ~2.700 | ảnh trong `preview/` |
| 12 | `app.py`, tests, scripts | ~1.200 | `pytest`, `verify_live.py` |
