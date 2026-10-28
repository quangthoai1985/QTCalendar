# Kế hoạch thiết kế lại giao diện Lịch Bloc và Lịch Tháng (Truyền thống pha Hiện đại)

> **Dành cho kỹ sư thực hiện:** Kỹ năng áp dụng: Sử dụng `superpowers:executing-plans` hoặc `superpowers:subagent-driven-development`. Các bước sử dụng cú pháp checkbox (`- [ ]`) để theo dõi.

**Mục tiêu:** Thiết kế lại toàn diện giao diện Lịch Bloc và Lịch Tháng theo phong cách ấn phẩm lịch truyền thống Việt Nam kết hợp nét tinh tế hiện đại, loại bỏ khối viên thuốc oval thô cứng ở phần âm lịch, căn chỉnh bố cục đối xứng, hài hòa và thoáng đãng.

**Kiến trúc:**
- `src/qtcalendar/ui/bloc_view.py`: Thay thế widget `_LunarPill` bằng thành phần `_LunarDayBlock` cân đối trục giữa. Tái cấu trúc layout âm lịch: Số ngày âm trang trọng ở tâm điểm, dòng Tháng Âm / Năm Can Chi, dòng Can Chi Ngày / Tháng, badge Tiết khí & Ngày hoàng đạo, và lưới Giờ hoàng đạo thanh lịch.
- `src/qtcalendar/ui/month_view.py`: Tinh chỉnh typography tiêu đề tháng/năm, làm nổi bật ngày Rằm và Mùng 1 trong lưới ngày, phân biệt rõ Chủ Nhật / Thứ Bảy, và cải thiện thanh footer cùng nút thao tác.
- `src/qtcalendar/ui/styles.py`: Bổ sung stylesheet cho các thành phần mới, tối ưu màu sắc và bo góc.

**Tech Stack:** Python 3.14, PySide6 (Qt GUI, QPainter, QFontMetricsF).

---

## Ràng buộc chung
- Giữ nguyên các hợp đồng API công khai của `BlocView` và `MonthView` (`set_day`, `apply_theme`, `set_month`, `quote_clicked`, `day_activated`...).
- Giữ vững hiệu năng vẽ: toàn bộ thành phần động được vẽ bằng `QPainter`, không dùng `QGraphicsEffect` để tối ưu RAM dưới 50MB.
- Không phá vỡ các bài kiểm thử hiện có trong `tests/`.

---

## Chi tiết các tác vụ thực hiện

### Tác vụ 1: Thiết kế lại thành phần hiển thị Âm Lịch trong `bloc_view.py`
**Files:**
- Sửa đổi: `src/qtcalendar/ui/bloc_view.py`
- Kiểm thử: `tests/test_widget_window.py` và kiểm tra smoke render `run_qtcalendar.pyw --smoke`

- [ ] **Bước 1: Viết test kiểm tra hiển thị khối Âm lịch mới**
  Kiểm tra các thuộc tính text, ngày âm, mùng 1, rằm hiển thị chuẩn xác không lỗi giao diện.

- [ ] **Bước 2: Thay thế `_LunarPill` bằng `_LunarDayBlock` cân đối truyền thống**
  - Bỏ hình oval hẹp ngang lệch bên trái.
  - Xây dựng cụm âm lịch căn giữa (Center-aligned):
    - Số ngày âm cỡ lớn (font số ấn phẩm truyền thống thanh thoát, sắc nét).
    - Với ngày Mùng 1 và Rằm: Hiển thị chữ cách điệu "Mùng Một" / "Ngày Rằm" trang trọng.
    - Cột thông tin: Dòng 1 là `Tháng <Tên Tháng> · Năm <Can Chi Năm>`, Dòng 2 là `Ngày <Can Chi Ngày> · Tháng <Can Chi Tháng>`.
    - Viền hoa văn hoặc gạch chỉ mảnh tinh tế phong cách ấn phẩm sách xưa pha nét tối giản hiện đại.

- [ ] **Bước 3: Tối ưu hoá bố cục các chip Tiết khí, Hoàng đạo và Giờ hoàng đạo**
  - Sắp xếp chip Tiết khí & Ngày hoàng đạo đối xứng, bo tròn mềm mại.
  - Lưới 6 giờ hoàng đạo hiển thị 2 hàng x 3 cột với viền mảnh nhã nhặn, khoảng cách thở hợp lý.

- [ ] **Bước 4: Kiểm tra trực quan qua smoke render**
  Chạy lệnh tạo ảnh kiểm tra `py E:\App\QTCalendar\run_qtcalendar.pyw --smoke preview\test_bloc_redesign.png --view bloc`

---

### Tác vụ 2: Tinh chỉnh và hiện đại hoá Lịch Tháng trong `month_view.py`
**Files:**
- Sửa đổi: `src/qtcalendar/ui/month_view.py`
- Kiểm thử: `tests/test_widget_window.py`

- [ ] **Bước 1: Cải thiện Header Lịch Tháng**
  - Tách bạch Tháng/Năm Dương và Tháng/Năm Âm với tỷ lệ phân cấp thị giác rõ ràng.
  - Các nút chuyển tháng ‹ › thiết kế thanh thoát, hiệu ứng hover mềm mại.

- [ ] **Bước 2: Tối ưu ô hiển thị ngày (`_DayCell`)**
  - Phân cấp ngày Dương (rõ, đậm vừa phải) và ngày Âm (nhỏ gọn ở góc dưới).
  - Điểm xuyết ngày Mùng 1 và ngày Rằm (15 âm lịch) bằng ký hiệu chấm son / màu nhấn truyền thống.
  - Thứ Bảy và Chủ Nhật mang màu sắc dễ phân biệt.
  - Ô "Hôm nay" có vòng tròn/khung viền chỉn chu, nổi bật.

- [ ] **Bước 3: Hoàn thiện Footer**
  - Chú thích ngày hôm nay hiển thị trang nhã.
  - Nút "Hôm nay" và nút "Lịch Ngày" thiết kế đồng bộ với hệ thống theme.

- [ ] **Bước 4: Chụp ảnh kiểm thử trực quan**
  Chạy lệnh tạo ảnh `py E:\App\QTCalendar\run_qtcalendar.pyw --smoke preview\test_month_redesign.png --view month`

---

### Tác vụ 3: Chạy toàn bộ test suite và nghiệm thu giao diện
- [ ] Chạy toàn bộ pytest `python -m pytest` để đảm bảo 100% test vượt qua.
- [ ] Dọn dẹp các tệp ảnh kiểm thử tạm thời.
