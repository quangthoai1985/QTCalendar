"""Hằng số Can Chi, Địa Chi, con giáp và bảng giờ hoàng đạo.

Tách riêng khỏi ``canchi.py`` để cả ``lunar.py`` lẫn các module giao diện
đều có thể dùng mà không tạo vòng import.
"""

from __future__ import annotations

#: Thập can
CAN = ("Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý")

#: Thập nhị địa chi
CHI = (
    "Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ",
    "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi",
)

#: Con giáp tương ứng với địa chi (Việt Nam dùng Mão = Mèo, không phải Thỏ)
ZODIAC = (
    "Chuột", "Trâu", "Hổ", "Mèo", "Rồng", "Rắn",
    "Ngựa", "Dê", "Khỉ", "Gà", "Chó", "Lợn",
)

#: Tên 12 tháng âm lịch theo cách gọi dân gian Việt Nam.
#: Chỉ số 0 = tháng Giêng … 11 = tháng Chạp.
LUNAR_MONTH_NAMES = (
    "Giêng", "Hai", "Ba", "Tư", "Năm", "Sáu",
    "Bảy", "Tám", "Chín", "Mười", "Mười Một", "Chạp",
)

#: 24 tiết khí, bắt đầu từ Lập Xuân (kinh độ mặt trời 315°).
TIET_KHI = (
    "Lập Xuân", "Vũ Thủy", "Kinh Trập", "Xuân Phân", "Thanh Minh", "Cốc Vũ",
    "Lập Hạ", "Tiểu Mãn", "Mang Chủng", "Hạ Chí", "Tiểu Thử", "Đại Thử",
    "Lập Thu", "Xử Thử", "Bạch Lộ", "Thu Phân", "Hàn Lộ", "Sương Giáng",
    "Lập Đông", "Tiểu Tuyết", "Đại Tuyết", "Đông Chí", "Tiểu Hàn", "Đại Hàn",
)

#: 12 vị thần luân phiên theo giờ và theo ngày.
#: Thứ tự chuẩn: Thanh Long, Minh Đường, Thiên Hình, Chu Tước, Kim Quỹ,
#: Bảo Quang, Bạch Hổ, Ngọc Đường, Thiên Lao, Huyền Vũ, Tư Mệnh, Câu Trần.
HOUR_GODS = (
    "Thanh Long", "Minh Đường", "Thiên Hình", "Chu Tước",
    "Kim Quỹ", "Bảo Quang", "Bạch Hổ", "Ngọc Đường",
    "Thiên Lao", "Huyền Vũ", "Tư Mệnh", "Câu Trần",
)

#: Chỉ số của 6 vị thần thuộc nhóm HOÀNG ĐẠO (tốt).
AUSPICIOUS_GOD_INDEXES = (0, 1, 4, 5, 7, 10)

#: Nhãn thứ trong tuần theo quy ước Việt Nam (tuần bắt đầu Thứ Hai).
WEEKDAY_NAMES = (
    "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm",
    "Thứ Sáu", "Thứ Bảy", "Chủ Nhật",
)

#: Nhãn ngắn dùng cho lưới lịch tháng.
WEEKDAY_SHORT = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")

#: Nhãn thứ viết hoa dùng cho đầu trang lịch bloc.
WEEKDAY_UPPER = (
    "THỨ HAI", "THỨ BA", "THỨ TƯ", "THỨ NĂM",
    "THỨ SÁU", "THỨ BẢY", "CHỦ NHẬT",
)
