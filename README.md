# QT Calendar — Lịch Bloc Dương – Âm cho Windows

**Desktop widget lịch Việt** mang dáng tờ lịch bloc treo tường: giấy ngà, mực
đậm, đỏ lịch bloc truyền thống kết hợp nét hiện đại. Chạy trên Windows 10/11, **ghim sát mặt bàn Desktop**
(không bị ẩn khi nhấn Win + D), có icon khay hệ thống, khởi động cùng
Windows, kéo thả tự do, tự động phát hiện bản mới và cập nhật ngầm.

![Lịch bloc](preview/app_final_bloc.png)

---

## Tải về & Cài đặt

Tải bản phát hành mới nhất từ trang [GitHub Releases](https://github.com/quangthoai1985/QTCalendar/releases):

* **Bộ cài đặt Windows (QTCalendar_Setup_v1.0.0.exe)**: Bộ cài Inno Setup chuẩn Microsoft, cài đặt tại %LOCALAPPDATA%\Programs\QT Calendar (không yêu cầu quyền Admin UAC), tự tạo shortcut Desktop & Start Menu, đăng ký Registry trong **Installed apps** / **Apps & features** để gỡ cài đặt sạch sẽ, hỗ trợ lệnh chạy nhanh QTCalendar trong hộp thoại Run (Win + R).
* **Bản cập nhật ngầm (QTCalendar_Update.zip)**: Dành riêng cho cơ chế tự động cập nhật ngầm của ứng dụng.

---
## Tính năng

| Nhóm | Chi tiết |
|---|---|
| **Lịch ngày (bloc)** | Thứ · ngày dương cực lớn · tháng/năm · **khối Âm lịch nổi bật** (số ngày âm lớn trong viên thuốc, tháng + năm âm, nhãn "Mùng 1"/"Rằm"/"(nhuận)") · Can Chi tháng/ngày · con giáp · 6 giờ hoàng đạo · ngày hoàng đạo/hắc đạo · tiết khí · ngày lễ Việt Nam · ca dao/tục ngữ |
| **Lịch tháng** | Bấm **tab kéo** ở chân widget để lịch tháng hiện **ngay dưới lịch bloc** (xem cùng lúc hai lịch, widget dài thêm xuống dưới); lưới 7 cột, mỗi ô hiển thị song song dương + âm lịch, hôm nay tô nổi bật, ngày đang xem ở bloc có viền nhấn, Chủ nhật/mùng 1/rằm/ngày lễ có màu riêng, chuyển tháng bằng ‹ › |
| **Cửa sổ** | Không viền, kéo thả tự do, tự lưu toạ độ, tự kẹp vào màn hình, khoá vị trí |
| **Kéo giãn** | Tay nắm ở góc dưới phải: kéo để phóng to/thu nhỏ (260×330 → 1000×1300), nội dung tự phóng theo kích thước, tự lưu kích thước; menu có "Đặt lại kích thước (344×468)" |
| **Ghim Desktop** | Cơ chế kiểu Rainmeter: widget vẫn là cửa sổ cấp cao nhất nằm ở `HWND_BOTTOM` (dưới mọi ứng dụng, trên hình nền), cờ `WS_EX_TOOLWINDOW` + `WS_EX_NOACTIVATE` nên không có trong taskbar/Alt+Tab và không cướp focus; một cửa sổ *sentinel* vô hình phát hiện `Win + D` để nâng widget lên ngay dưới Taskbar; giữ nguyên nền trong suốt, góc bo và bóng đổ (không quầng đen) |
| **Độ mờ nền** | 20 % – 100 %, **chỉ nền giấy trong đi – chữ luôn đặc 100 %** nên vẫn đọc rõ trên mọi hình nền; áp dụng cả ở chế độ cửa sổ nổi lẫn ghim Desktop |
| **Màu nền** | 10 màu gợi ý + chọn màu tuỳ ý (bảng màu Windows) + "Theo giao diện"; nền tối tự chuyển chữ sang màu sáng để không mất chữ |
| **Khay hệ thống** | Menu đầy đủ: hiện/ẩn, hiện lịch tháng, độ mờ, ghim, luôn nổi, khoá vị trí, khởi động cùng Windows, về hôm nay, đặt lại vị trí, kiểm tra bản cập nhật, cài đặt, thoát |
| **Tự động cập nhật** | Tự động kiểm tra bản mới từ GitHub Releases qua API, tải bản cập nhật ngầm an toàn có kiểm tra mã SHA-256, tự động hoán đổi tệp khi ứng dụng thoát hoặc khởi động lại ngay |
| **Khởi động cùng Windows** | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (không cần quyền admin) |
| **Cấu hình** | `settings.json` ghi nguyên tử; 26 trường; hỏng tệp thì tự sao lưu và về mặc định |
| **Giao diện** | 4 bảng màu: Giấy đỏ, Xanh ngọc, Hoàng hôn, Đêm sao; tỉ lệ nội dung 75 – 200 % |
| **Âm lịch** | Hai engine: chính xác cao (mặc định, khớp lịch vạn niên) và bản gốc Hồ Ngọc Đức |
| **Dữ liệu offline** | 439 câu ca dao/tục ngữ/đan ngôn nhúng sẵn, không cần mạng |

---

## Chạy nhanh

```powershell
cd E:\App\QTCalendar

# Chạy (không cửa sổ console)
pythonw run_qtcalendar.pyw

# Xem nhanh thông tin âm lịch hôm nay
$env:PYTHONUTF8="1"; python -X utf8 run_qtcalendar.pyw --info

# Kiểm thử
python -X utf8 -m pytest tests -q
```

Yêu cầu: **Python 3.10+** và **PySide6** (`pip install PySide6-Essentials`).
Đã phát triển và kiểm chứng trên Python 3.14.7 + PySide6 6.11.2, Windows 11
25H2.

### Thao tác

| Thao tác | Kết quả |
|---|---|
| Kéo chuột trái | Di chuyển widget, tự lưu vị trí khi thả |
| Kéo tay nắm ở góc dưới phải | Phóng to / thu nhỏ widget, nội dung tự co giãn theo |
| Bấm tab `THÁNG` / `ẨN` ở chân widget | Hiện / ẩn lịch tháng ngay dưới lịch bloc |
| Nháy đúp | Hiện / ẩn lịch tháng |
| Bấm một ngày trong lịch tháng | Lịch bloc chuyển sang ngày đó (lịch tháng vẫn mở) |
| Chuột phải | Menu nhanh (hiện lịch tháng, độ mờ, ghim, cài đặt…) |
| Rê chuột vào widget | Hiện nút menu nổi ở góc trên |
| Menu khay hệ thống | Toàn bộ chức năng, kể cả thoát |

### Vị trí tệp cấu hình

```
%LOCALAPPDATA%\QTCalendar\settings.json     # mặc định
%LOCALAPPDATA%\QTCalendar\qtcalendar.log    # log xoay vòng 64 KB
```

**Chế độ portable**: đặt một tệp `settings.json` cạnh `run_qtcalendar.pyw`,
ứng dụng sẽ dùng tệp đó thay vì `%LOCALAPPDATA%`.

---

## Cấu trúc dự án (rút gọn)

```
QTCalendar/
├── run_qtcalendar.pyw          # trình khởi chạy (không console)
├── requirements.txt            # PySide6-Essentials
├── src/qtcalendar/
│   ├── app.py                  # bộ điều phối: widget ↔ tray ↔ cấu hình
│   ├── core/                   # logic thuần, KHÔNG import Qt
│   │   ├── lunar.py            #   thuật toán Hồ Ngọc Đức
│   │   ├── lunar_precise.py    #   engine chính xác cao (Meeus)
│   │   ├── canchi.py           #   Can Chi, giờ hoàng đạo
│   │   ├── calendar_service.py #   DayInfo / MonthGrid
│   │   ├── quotes.py           #   ca dao offline
│   │   ├── config.py           #   Settings + ConfigStore
│   │   ├── theme.py            #   4 bảng màu
│   │   └── types.py            #   dataclass bất biến
│   ├── platform/               # Win32
│   │   ├── win32.py            #   ctypes wrapper
│   │   ├── desktop_pin.py      #   ghim Desktop kiểu Rainmeter (HWND_BOTTOM + sentinel)
│   │   ├── autostart.py        #   Registry Run
│   │   └── tray.py             #   QSystemTrayIcon + menu
│   ├── ui/                     # PySide6
│   │   ├── widget_window.py    #   cửa sổ không viền + kéo thả + ghim
│   │   ├── bloc_view.py        #   lịch ngày
│   │   ├── month_view.py       #   lịch tháng
│   │   ├── month_tab.py        #   tab kéo bật/tắt lịch tháng
│   │   ├── settings_dialog.py  #   hộp thoại cài đặt
│   │   └── styles.py           #   sinh QSS từ theme
│   └── data/quotes.json        # 439 câu ca dao/tục ngữ/danh ngôn
├── tests/                      # 499+ test pytest
├── scripts/                    # audit, preview, probe, verify
├── docs/                       # 5 tài liệu thiết kế & kỹ thuật
└── assets/                     # icon.png / icon.ico
```

---

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [01 — Phân tích kiến trúc](docs/01-kien-truc.md) | Chọn công nghệ, sơ đồ 4 tầng, cơ chế ghim desktop, ngân sách RAM, kịch bản lỗi |
| [02 — Cấu trúc thư mục](docs/02-cau-truc-thu-muc.md) | Cây thư mục, trách nhiệm từng file, quy tắc phụ thuộc, quy ước code |
| [03 — Từng bước code](docs/03-tung-buoc-code.md) | 12 bước từ máy trắng tới app, kèm mã nguồn âm lịch & ghim desktop |
| [04 — Thuật toán âm lịch](docs/04-thuat-toan-am-lich.md) | Công thức Hồ Ngọc Đức, hạn chế đo được, lớp chính xác cao, Can Chi, giờ hoàng đạo |
| [05 — Kiểm thử & đóng gói](docs/05-kiem-thu-va-dong-goi.md) | Chiến lược test, số liệu đo, hạn chế, hướng dẫn PyInstaller |

---

## Kết quả đo (máy phát triển)

| Hạng mục | Kết quả |
|---|---|
| Test | 545 passed, 7 xfailed (các ca khác biệt có chủ đích của engine HND) |
| Đối chứng âm lịch | 31/31 ngày Tết (1985–2040), 18/18 tháng nhuận, 109.938 ngày liên tục 1900–2200 **0 lỗi** |
| Dựng lưới lịch tháng | ~0,8 ms cho 42 ô (cache nguội) |
| Độ mờ nền | ảnh kiểm: 60 % → alpha nền 152/255, chữ vẫn 255/255 |
| RAM khi chạy ngầm | ~82 MB working set / ~46 MB private |
| Kích thước mã nguồn | ~8.300 dòng Python + ~2.900 dòng test + ~1.800 dòng tài liệu |

> **Về mục tiêu 60 MB**: Qt6 + Python có mức nền ~43 MB trước khi vẽ bất cứ
> thứ gì; ứng dụng dừng ở ~82 MB. Muốn xuống dưới 60 MB một cách chắc chắn
> cần chuyển sang WPF/native (xem bảng so sánh trong `docs/01`).

---

## Hạn chế đã biết

1. **Bật "luôn nổi trên cùng" khi đang ghim**: hai chế độ loại trừ nhau, nên
   ứng dụng tự bỏ ghim và chuyển sang cửa sổ nổi (Qt tạo lại cửa sổ khi đổi
   window flags), có thể thấy nháy nhẹ.
2. **Phát hiện `Win + D`** dựa trên thứ tự Z của lớp Desktop (`Progman` trên
   Windows 11 24H2+, `WorkerW` chứa `SHELLDLL_DefView` trên bản cũ) so với
   cửa sổ sentinel. Nếu Explorer đổi cách tổ chức các lớp này ở bản Windows
   sau, có thể cần cập nhật `desktop_pin.get_desktop_icons_host()`.
3. **Engine Hồ Ngọc Đức gốc** sai 1 ngày ở một số tuần trăng hiếm (Tết 1991,
   05/2020, 03/2023, 08/2026, 04/2031) và sai tên tháng nhuận 2023, 2039 —
   đây là sai số của chuỗi Fourier rút gọn trong bản gốc. Mặc định dùng
   engine `precise`; người dùng đổi được trong *Cài đặt → Nâng cao*.
4. **Tên tháng 11 nhuận** (năm 2033) là trường hợp lịch pháp đặc biệt; engine
   `precise` xử lý đúng theo lịch Việt Nam hiện hành.

---

## Giấy phép

Dự án được phân phối theo giấy phép [MIT](LICENSE).

Thuật toán âm lịch dựa trên công trình công bố của **Hồ Ngọc Đức** (Đại học Leipzig) và chuỗi thiên văn của **Jean Meeus** (*Astronomical Algorithms*). Kho ca dao/tục ngữ là văn học dân gian Việt Nam.


