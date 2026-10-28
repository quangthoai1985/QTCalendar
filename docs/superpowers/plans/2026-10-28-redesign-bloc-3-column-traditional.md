# Kế hoạch thiết kế lại Lịch Bloc theo bố cục truyền thống 3 cột (Kiểu Lịch Bloc Đại Việt Nam)

> **Dành cho kỹ sư thực hiện:** Kỹ năng áp dụng: Sử dụng `superpowers:executing-plans` hoặc `superpowers:subagent-driven-development`. Các bước sử dụng cú pháp checkbox (`- [ ]`) để theo dõi.

**Mục tiêu:** Tái tạo chính xác bố cục tờ lịch bloc đại truyền thống của Việt Nam (phong cách An Hảo / Lịch bloc siêu đại):
1. Phần đỉnh: Dải hoa văn nghệ thuật truyền thống vector mềm mại + câu danh ngôn/châm ngôn cuộc sống thanh nhã.
2. Phần thân giữa: Số ngày Dương lịch siêu lớn ở tâm điểm + câu danh ngôn / tục ngữ chiêm nghiệm.
3. Phần chân lịch: Cấu trúc 3 cột kinh điển:
   - Cột trái: Tháng dương (`THÁNG MƯỜI / OCTOBER`), năm, giờ hoàng đạo, tuần trong năm & ngày trong năm.
   - Cột giữa: Thứ song ngữ (`THỨ TƯ / WEDNESDAY`) + **Số ngày Âm lịch cỡ lớn nổi bật**.
   - Cột phải: Tháng âm (`THÁNG CHÍN (Đ)`), chi tiết Can Chi (Tháng, Ngày, Giờ, Năm), Tiết khí & Trực ngày.

**Kiến trúc:**
- `src/qtcalendar/core/calendar_service.py`: Bổ sung các trường tiện ích trong `DayInfo` nếu cần (tháng âm đủ/thiếu `(Đ)/(T)`, ngày thứ trong năm `day_of_year`, tuần trong năm `week_of_year`, can chi giờ Tý).
- `src/qtcalendar/ui/bloc_view.py`: Tái cấu trúc toàn diện bố cục `BlocView`:
  - Thêm thành phần vẽ hoa văn nghệ thuật đỉnh lịch `_TopArtBanner`.
  - Căn chỉnh thân giữa: Số ngày dương siêu lớn + danh ngôn.
  - Xây dựng cụm chân lịch 3 cột: `_FooterLeftCol` (Dương lịch & Hoàng đạo), `_FooterCenterCol` (Thứ + Số ngày Âm cực to), `_FooterRightCol` (Tháng âm, Can chi 4 trụ, Tiết khí).
- `src/qtcalendar/ui/styles.py`: Cập nhật stylesheet hỗ trợ các nhãn mới.

**Tech Stack:** Python 3.14, PySide6 (QPainter, QPainterPath, QFontMetricsF).

---

## Chi tiết các tác vụ thực hiện

### Tác vụ 1: Bổ sung dữ liệu bổ trợ trong `core/calendar_service.py` & `core/canchi.py`
**Files:**
- Sửa đổi: `src/qtcalendar/core/types.py`, `src/qtcalendar/core/calendar_service.py`
- Kiểm thử: `tests/test_calendar_service.py`

- [ ] **Bước 1: Viết test cho các trường bổ trợ**
  Kiểm tra `day_of_year`, `week_of_year`, `lunar_month_length_char` ('Đ' hoặc 'T'), `english_month_upper` ('OCTOBER').

- [ ] **Bước 2: Cập nhật `DayInfo` và `get_day_info`**
  Thêm các thuộc tính vào `DayInfo` để tầng UI sử dụng trực tiếp mà không cần tính toán lại.

- [ ] **Bước 3: Chạy test kiểm chứng**
  Chạy: `python -m pytest tests/test_calendar_service.py`

---

### Tác vụ 2: Xây dựng dải hoa văn nghệ thuật đỉnh lịch trong `bloc_view.py`
**Files:**
- Sửa đổi: `src/qtcalendar/ui/bloc_view.py`

- [ ] **Bước 1: Tạo widget `_TopArtBanner`**
  Vẽ dải hoa văn mây cuộn / sóng lượn truyền thống cách điệu bằng `QPainterPath`, thanh mảnh, nhã nhặn, chiếm ~10-12% chiều cao đỉnh lịch.
  Hiển thị câu châm ngôn cuộc sống / danh ngôn ngắn ở trung tâm dải hoa văn.

---

### Tác vụ 3: Thiết kế lại Thân giữa và Chân lịch 3 cột trong `bloc_view.py`
**Files:**
- Sửa đổi: `src/qtcalendar/ui/bloc_view.py`

- [ ] **Bước 1: Tối ưu vùng Thân giữa**
  Số ngày Dương lịch siêu lớn ở tâm điểm, nét đậm đà, màu sắc ấn tượng. Ngay dưới chân là câu tục ngữ / danh ngôn ngắn in nghiêng.

- [ ] **Bước 2: Dàn layout cụm chân lịch 3 cột hoàn chỉnh**
  - **Cột Trái (~30% cw)**:
    - Năm + Tháng tiếng Anh (`2026 · OCTOBER`)
    - Tháng tiếng Việt (`THÁNG MƯỜI`)
    - Danh sách Giờ hoàng đạo (`Sửu, Thìn, Ngọ...`)
    - Dải tuần & ngày trong năm (`Tuần 44 · Ngày 301/365`)
  - **Cột Giữa (~40% cw)**:
    - Thứ song ngữ (`THỨ TƯ / WEDNESDAY`) kèm hoa văn nhỏ hai bên
    - **Số ngày Âm lịch cỡ lớn** ở trung tâm, font số đậm, màu sắc nổi bật
  - **Cột Phải (~30% cw)**:
    - Tháng âm lịch kèm trạng thái đủ/thiếu (`THÁNG CHÍN (Đ)`)
    - 4 dòng Can Chi rõ ràng: Tháng, Ngày, Giờ, Năm
    - Tiết khí & Trực ngày (`Sương Giáng`)

- [ ] **Bước 3: Tối ưu co giãn (Responsive layout)**
  Đảm bảo widget co giãn mượt mà từ kích thước nhỏ (260x330) đến kích thước lớn (1000x1300) mà không bị tràn chữ hay vỡ layout.

---

### Tác vụ 4: Kiểm tra kiểm thử tự động và xuất ảnh kiểm chứng trực quan
- [ ] Chạy `python -m pytest tests/` để đảm bảo 100% test vượt qua.
- [ ] Chạy lệnh chụp ảnh smoke render: `py -3.14 E:\App\QTCalendar\run_qtcalendar.pyw --smoke preview\smoke_bloc_3col.png --view bloc`
- [ ] So sánh trực quan với ảnh mẫu thực tế của người dùng.
