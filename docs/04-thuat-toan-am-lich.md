# 04 — Thuật toán Âm lịch Việt Nam

> Tài liệu này giải thích **toàn bộ** phần tính toán Dương ↔ Âm lịch của
> QT Calendar, kèm mã nguồn rút gọn và số liệu kiểm chứng thực đo.
> Mã đầy đủ nằm ở:
>
> * `src/qtcalendar/core/lunar.py` – bản gốc thuật toán Hồ Ngọc Đức
> * `src/qtcalendar/core/lunar_precise.py` – bản chính xác cao (mặc định)
> * `src/qtcalendar/core/canchi.py` – Can Chi, giờ hoàng đạo
> * `src/qtcalendar/core/types.py` – kiểu dữ liệu chung

Mục lục

1. [Nguyên tắc lịch pháp Việt Nam](#1-nguyên-tắc-lịch-pháp-việt-nam)
2. [Thuật toán Hồ Ngọc Đức](#2-thuật-toán-hồ-ngọc-đức)
3. [Hạn chế đo được của bản gốc](#3-hạn-chế-đo-được-của-bản-gốc)
4. [Lớp chính xác cao (engine mặc định)](#4-lớp-chính-xác-cao-engine-mặc-định)
5. [Can Chi](#5-can-chi)
6. [Giờ hoàng đạo và ngày hoàng đạo](#6-giờ-hoàng-đạo-và-ngày-hoàng-đạo)
7. [Tiết khí](#7-tiết-khí)
8. [Bảng kiểm chứng](#8-bảng-kiểm-chứng)

---

## 1. Nguyên tắc lịch pháp Việt Nam

Lịch Âm Việt Nam là **lịch âm dương** (lunisolar), cùng hệ với lịch Trung
Quốc nhưng khác một điểm quyết định: **múi giờ tính là UTC+7 (Hà Nội)**,
trong khi lịch Trung Quốc dùng UTC+8. Chính vì vậy có những năm Tết hai nước
lệch nhau một ngày (1985, 2007, 2030…).

Các quy tắc nền:

| Quy tắc | Nội dung |
|---|---|
| Tháng | Bắt đầu vào **ngày có điểm Sóc** (New Moon) theo giờ UTC+7. Tháng đủ 30 ngày, tháng thiếu 29 ngày. |
| Năm | Bắt đầu từ **Tết Nguyên Đán** (mùng 1 tháng Giêng). |
| Tháng 11 | Là tháng **chứa Đông chí** (kinh độ mặt trời 270°). |
| Tháng nhuận | Nếu giữa hai tháng 11 liên tiếp có **13 tuần trăng**, năm đó có tháng nhuận. Tháng nhuận là tháng **đầu tiên không chứa Trung khí** (một trong 12 mốc 30° của kinh độ mặt trời). |
| Can Chi | Chu kỳ 60 cho ngày; Can Chi tháng/năm suy ra theo quy tắc cổ truyền. |

Hai hệ quả rất dễ sai khi lập trình:

1. **Không thể "dịch" lịch Trung Quốc trừ 1 giờ.** Phải tính lại Sóc và
   Trung khí theo UTC+7 từ đầu.
2. **Trung khí phải xét theo ngày chứ không theo thời điểm.** Tháng âm lịch
   là tập hợp các *ngày*, nên một tháng "có Trung khí" nghĩa là **ngày** của
   Trung khí nằm trong khoảng ngày của tháng. Xét tại thời điểm Sóc (thay vì
   nửa đêm của ngày Sóc) sẽ sai ở các tháng mà Trung khí rơi cùng ngày nhưng
   **trước** giờ Sóc — chính là lỗi làm sai tháng nhuận năm 2014 trong quá
   trình phát triển (xem §4.3).

---

## 2. Thuật toán Hồ Ngọc Đức

Thuật toán được công bố tại <https://www.informatik.uni-leipzig.de/~duc/amlich/>
và là chuẩn de-facto của hầu hết ứng dụng lịch Việt Nam. Nó gồm 6 nguyên hàm.

### 2.1 Số ngày Julius (JDN)

```python
# src/qtcalendar/core/lunar.py
def jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:                      # trước 15/10/1582: lịch Julius
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd

def jd_to_date(jd: int) -> tuple[int, int, int]:
    if jd > 2299160:
        a = jd + 32044
        b = (4 * a + 3) // 146097
        c = a - (b * 146097) // 4
    else:
        b, c = 0, jd + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = b * 100 + d - 4800 + (m // 10)
    return day, month, year
```

### 2.2 Điểm Sóc (New Moon)

Chuỗi Fourier rút gọn (25 số hạng) của Meeus:

```python
def new_moon(k: int) -> float:
    t = k / 1236.85                       # số thế kỷ Julius tính từ 1900
    t2, t3 = t * t, t * t * t
    dr = PI / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m   = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3   # dị thường mặt trời
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3  # dị thường mặt trăng
    f   = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3   # bĩ độ mặt trăng
    c1  = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 -= 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * mpr)
    c1 += 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 -= 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 -= 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 += 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))
    if t < -11:
        deltat = 0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    return jd1 + c1 - deltat
```

Điểm Sóc thứ `k` rơi vào **ngày** nào được làm tròn theo giờ địa phương:

```python
def get_new_moon_day(k: int, timezone: int = 7) -> int:
    return math.floor(new_moon(k) + 0.5 + timezone / 24)
```

### 2.3 Kinh độ mặt trời

```python
def sun_longitude(jdn: float) -> float:
    t = (jdn - 2451545.0) / 36525
    t2 = t * t
    dr = PI / 180
    m  = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(dr * 3 * m)
    l = (l0 + dl) * dr
    return l - PI * 2 * math.floor(l / (PI * 2))      # chuẩn hoá 0..2π
```

Từ kinh độ, xác định **chỉ số Trung khí** (12 đoạn 30°) của một ngày:

```python
def get_sun_longitude(day_number: int, timezone: int = 7) -> int:
    # xét tại nửa đêm địa phương của ngày đó
    return math.floor(sun_longitude(day_number - 0.5 - timezone / 24) / PI * 6)
```

### 2.4 Tháng 11 và tháng nhuận

```python
def get_lunar_month_11(yy: int, timezone: int = 7) -> int:
    """Ngày bắt đầu tháng 11 âm lịch của năm dương lịch yy."""
    off = jd_from_date(31, 12, yy) - 2415021
    k = math.floor(off / 29.530588853)
    nm = get_new_moon_day(k, timezone)
    if get_sun_longitude(nm, timezone) >= 9:   # đã qua Đông chí ⇒ lùi 1 tuần trăng
        nm = get_new_moon_day(k - 1, timezone)
    return nm

def get_leap_month_offset(a11: int, timezone: int = 7) -> int:
    """Vị trí tháng nhuận tính từ tháng 11 (trả 0 nếu không có)."""
    k = math.floor((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last, i = 0, 1
    arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
    while i < 14:
        last = arc
        i += 1
        arc = get_sun_longitude(get_new_moon_day(k + i, timezone), timezone)
        if arc == last:            # hai tháng liên tiếp cùng một đoạn 30° ⇒ tháng trước không có Trung khí
            break
    return i - 1
```

### 2.5 Chuyển đổi hai chiều

```python
def solar_to_lunar(dd, mm, yy, timezone: int = 7) -> LunarDate:
    day_number = jd_from_date(dd, mm, yy)
    k = math.floor((day_number - 2415021.076998695) / 29.530588853)
    month_start = get_new_moon_day(k + 1, timezone)
    if month_start > day_number:
        month_start = get_new_moon_day(k, timezone)

    a11 = get_lunar_month_11(yy, timezone)
    b11 = a11
    if a11 >= month_start:                 # tháng này nằm sau tháng 11 của năm yy
        lunar_year = yy
        a11 = get_lunar_month_11(yy - 1, timezone)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month_11(yy + 1, timezone)

    lunar_day = day_number - month_start + 1
    diff = math.floor((month_start - a11) / 29)
    lunar_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:                    # 13 tuần trăng ⇒ có tháng nhuận
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
```

Chiều ngược lại (`lunar_to_solar`) làm đúng phép đảo: tính `a11`, `b11` của
năm, cộng thêm 1 tháng nếu đã qua tháng nhuận, rồi `month_start + day - 1`.

---

## 3. Hạn chế đo được của bản gốc

Bản gốc dùng chuỗi Fourier **rút gọn** nên sai số điểm Sóc khoảng **±50
phút** và kinh độ mặt trời khoảng **0,01°**. Bình thường vô hại, nhưng khi
điểm Sóc rơi gần nửa đêm giờ Hà Nội thì chỉ cần lệch 40 phút là **sang ngày
khác**.

Tôi đã dựng một bộ tính độc lập (Meeus ch. 49, 25 số hạng chính + 14 số hạng
nhiễu hành tinh + hiệu chỉnh ΔT) để đo sai số của bản gốc trên **185 tuần
trăng liên tiếp (2020 – 2034)**:

| Tuần trăng | Ngày mùng 1 theo HND | Ngày đúng (Meeus) | Sai lệch thời điểm |
|---|---|---|---|
| 05/2020 | 22/05/2020 | **23/05/2020** | −46,9 phút |
| 03/2023 | 21/03/2023 | **22/03/2023** | −44,1 phút |
| 08/2026 | 12/08/2026 | **13/08/2026** | −42,1 phút |
| 04/2031 | 22/04/2031 | **21/04/2031** | +35,2 phút |

Sai số lớn nhất đo được: **49,2 phút**.

Hệ quả nặng nhất nằm ở **tháng nhuận 2023**: vì điểm Sóc bị tính sớm 1 ngày,
tháng nhuận bị gán sai tên. Trên 1990 – 2040, bản gốc khác lịch chuẩn ở hai
năm:

| Năm | HND gốc | Lịch Việt Nam chuẩn |
|---|---|---|
| 2023 | tháng **Giêng** nhuận ❌ | tháng **Hai** nhuận ✔ |
| 2039 | tháng Tư nhuận ❌ | tháng Năm nhuận ✔ |

> Vì vậy dự án giữ **cả hai** engine: `hnd` (bản gốc, để đối chiếu và vì đề
> bài yêu cầu đúng thuật toán Hồ Ngọc Đức) và `precise` (mặc định). Người
> dùng đổi được trong *Cài đặt → Nâng cao → Thuật toán âm lịch*.

---

## 4. Lớp chính xác cao (engine mặc định)

Engine `precise` giữ nguyên **triết lý** của HND nhưng thay ba thành phần.

### 4.1 Điểm Sóc chính xác (Meeus, ch. 49)

25 số hạng chính + 14 số hạng nhiễu hành tinh, cộng hiệu chỉnh ΔT theo đa
thức Espenak–Meeus. Sai số dưới 1 phút.

```python
# src/qtcalendar/core/lunar_precise.py  (rút gọn)
def new_moon_jde(k: float) -> float:
    t = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * t**2 ...
    E = 1 - 0.002516 * t - 0.0000074 * t**2
    M, Mp, F, Om = ...                       # các góc theo công thức Meeus
    corr = (-0.40720 * sin(Mp) + 0.17241 * E * sin(M) + 0.01608 * sin(2*Mp)
            + 0.01039 * sin(2*F) + 0.00739 * E * sin(Mp-M) - 0.00514 * E * sin(Mp+M)
            + ... )                          # tổng 25 số hạng
    for base, amp in _PLANET_TERMS:           # 14 số hạng nhiễu hành tinh
        corr += amp * sin(radians(base) + 0.0000021 * k)
    return jde + corr

def new_moon_jd(k: float) -> float:           # UT = TT − ΔT
    jde = new_moon_jde(k)
    return jde - delta_t_seconds(_jd_to_year(jde)) / 86400.0
```

### 4.2 Trung khí xét tại **nửa đêm ngày mùng 1**

```python
def _sun_segment_at_new_moon(k: int) -> int:
    day = new_moon_day(k)                          # ngày mùng 1
    jd_local_midnight = day - 0.5 - TIMEZONE / 24  # nửa đêm giờ Hà Nội
    return int(math.floor(sun_apparent_longitude(jd_local_midnight) / 30.0)) % 12

def _has_zhongqi(k: int) -> bool:
    return _sun_segment_at_new_moon(k) != _sun_segment_at_new_moon(k + 1)
```

### 4.3 Vì sao phải xét theo ngày — ví dụ năm 2014

| Mốc | Thời điểm (giờ Hà Nội) |
|---|---|
| Sóc tháng 9/2014 | 24/10/2014 |
| **Tiểu tuyết** (Trung khí 240°) | 22/11/2014 **16:38** |
| Sóc tháng 10/2014 | 22/11/2014 **19:32** |

Nếu xét tại **thời điểm Sóc**, kinh độ mặt trời đã vượt 240° ⇒ thuật toán
tưởng tháng 24/10 – 21/11 *có* Trung khí ⇒ bỏ qua tháng nhuận ⇒ gán tháng
nhuận 2014 thành **tháng 10** (sai). Xét tại **nửa đêm 22/11** thì kinh độ
vẫn là 239,6° ⇒ tháng 24/10 không có Trung khí ⇒ tháng nhuận là **tháng 9**
(đúng, khớp lịch vạn niên).

### 4.4 Bảng tháng liên tục — xử lý "tháng 11 nhuận" (bài toán 2033)

Bản gốc đánh số tháng bằng số học chỉ số (`diff + 11`, `diff + 10`). Cách đó
giả định tháng nhuận luôn nằm *giữa* hai tháng 11 liên tiếp và không bao giờ
là **tháng 11 hay tháng 12** – thường đúng, nhưng sai vào năm 2033 (lịch Việt
Nam có **tháng Một nhuận**, đúng bài toán "2033" nổi tiếng của lịch Trung
Quốc).

Engine chính xác dựng **bảng tháng liên tục**:

```python
@dataclass(frozen=True, slots=True)
class _Month:
    number: int      # số tháng 1..12
    leap: bool       # có phải tháng nhuận?
    year: int        # năm âm lịch chứa tháng này
    start: int       # JDN ngày mùng 1
    days: int        # 29 hoặc 30

@lru_cache(maxsize=1024)
def _span(year: int) -> tuple[_Month, ...]:
    """Chuỗi tháng từ tháng 11 năm `year` tới sát tháng 11 năm `year + 1`."""
    k_a, k_b = _k11(year), _k11(year + 1)      # tuần trăng chứa Đông chí
    count = k_b - k_a                          # 12 hoặc 13
    leap_at = 0
    if count >= 13:
        for j in range(1, count):
            if not _has_zhongqi(k_a + j):      # tháng không có Trung khí
                leap_at = j
                break
    months, number, lunar_year = [], 11, year
    for j in range(count):
        is_leap = leap_at > 0 and j == leap_at
        if j > 0 and not is_leap:
            number = _next_number(number)      # 11→12→1→2…→10
            if number == 1:
                lunar_year += 1
        start = new_moon_day(k_a + j)
        months.append(_Month(number, is_leap, lunar_year, start,
                             new_moon_day(k_a + j + 1) - start))
    return tuple(months)
```

Từ bảng này, mọi phép tra cứu trở nên tầm thường và **luôn nhất quán**:

```python
def solar_to_lunar(dd, mm, yy):
    day_number = jd_from_date(dd, mm, yy)
    k = _lunation_of_day(day_number)
    for candidate in (yy - 1, yy, yy + 1):
        if _k11(candidate) <= k < _k11(candidate + 1):
            entry = _span(candidate)[k - _k11(candidate)]
            return LunarDate(day_number - entry.start + 1,
                             entry.number, entry.year, entry.leap)
```

Kết quả đúng cho 2033: tháng Một nhuận bắt đầu **22/12/2033**, tháng Chạp bắt
đầu 20/01/2034, Tết 2034 = **19/02/2034**.

---

## 5. Can Chi

```python
CAN = ("Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý")
CHI = ("Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi")

def year_can_chi(year: int) -> CanChi:
    return CanChi(CAN[(year + 6) % 10], CHI[(year + 8) % 12])

def month_can_chi(month: int, year: int) -> CanChi:
    # "Giáp – Kỷ khởi Bính", "Ất – Canh khởi Mậu"… ⇒ can = 2·can_năm + tháng + 1
    return CanChi(CAN[(2 * ((year + 6) % 10) + month + 1) % 10], CHI[(month + 1) % 12])

def day_can_chi(day: date) -> CanChi:
    jdn = jd_from_date(day.day, day.month, day.year)
    return CanChi(CAN[(jdn + 9) % 10], CHI[(jdn + 1) % 12])   # mốc: 01/01/2000 = Mậu Ngọ
```

Con giáp dùng cách gọi Việt Nam: **Mão = Mèo** (không phải Thỏ), và Ất Mão…

| Địa chi | Tý | Sửu | Dần | Mão | Thìn | Tỵ | Ngọ | Mùi | Thân | Dậu | Tuất | Hợi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Con giáp | Chuột | Trâu | Hổ | **Mèo** | Rồng | Rắn | Ngựa | Dê | Khỉ | Gà | Chó | Lợn |

Mốc kiểm chứng: `01/01/2000` = **Mậu Ngọ**, `10/02/2024` (Tết Giáp Thìn) =
**Giáp Thìn**, tháng Giêng 2024 = **Bính Dần**.

---

## 6. Giờ hoàng đạo và ngày hoàng đạo

### 6.1 Mười hai vị thần theo giờ

Mười hai vị thần luân phiên theo 12 canh giờ, mỗi canh 2 tiếng, khởi đầu
bằng canh **Tý (23h – 01h)**. Vị trí khởi đầu (Thanh Long) phụ thuộc chi của
ngày:

```
Thanh Long = (2 × chi_ngày + 8) mod 12
giờ hoàng đạo: các canh có (canh − Thanh Long) mod 12 ∈ {0, 1, 4, 5, 7, 10}
```

Sáu vị thần hoàng đạo: **Thanh Long, Minh Đường, Kim Quỹ, Bảo Quang, Ngọc
Đường, Tư Mệnh**.

```python
def auspicious_hours(day: date) -> tuple[AuspiciousHour, ...]:
    jdn = jd_from_date(day.day, day.month, day.year)
    day_chi = (jdn + 1) % 12
    thanh_long = (2 * day_chi + 8) % 12
    out = []
    for h in range(12):
        if (h - thanh_long) % 12 in AUSPICIOUS_GOD_INDEXES:
            start = (23 + 2 * h) % 24
            out.append(AuspiciousHour(CHI[h], start, (start + 2) % 24, HOUR_GODS[...]))
    return tuple(out)
```

Ví dụ ngày **Tý** cho ra 6 giờ: Thân, Dậu, Tý, Sửu, Mão, Ngọ — đúng như các
bảng "giờ hoàng đạo" trong lịch vạn niên Việt Nam.

### 6.2 Ngày hoàng đạo / hắc đạo

Cùng chu kỳ 12 thần nhưng theo **tháng âm lịch**: tháng Giêng và tháng Bảy
(chi Dần – Thân) khởi Thanh Long tại ngày Tý, mỗi tháng tiến 2 chi:

```
chi của ngày Thanh Long = (2 × (tháng âm − 1)) mod 12
```

⇒ tháng Giêng có ngày hoàng đạo là **Tý, Sửu, Thìn, Tỵ, Mùi, Tuất** — đúng
câu "tháng Giêng ngày hoàng đạo là Tý, Sửu, Thìn, Tỵ, Mùi, Tuất".

---

## 7. Tiết khí

24 tiết khí chia vòng hoàng đạo thành 24 đoạn 15°. Lập Xuân ở 315°.

**Quy ước hiển thị** (khớp lịch vạn niên): ngày nào có một tiết khí **bắt
đầu** thì ghi tiết khí đó; nếu không thì giữ tiết khí đang hiệu lực từ hôm
trước. Vì vậy phải xét kinh độ mặt trời tại **hai** mốc trong ngày:

```python
def tiet_khi_index(day: date) -> int:
    jdn = jd_from_date(day.day, day.month, day.year)
    start = jdn - 0.5 - 7 / 24.0            # nửa đêm giờ Hà Nội
    step_start = math.floor(sun_apparent_longitude(start) / 15.0)
    step_end = math.floor(sun_apparent_longitude(start + 1.0) / 15.0)
    step = step_end if step_end != step_start else step_start
    return (step - 21) % 24                  # 315°/15° = 21
```

Kết quả kiểm chứng: **04/02/2026 = Lập Xuân**, **20/03/2026 = Xuân Phân**
(Xuân Phân bắt đầu 21:46 giờ VN ngày 20/03), **22/12/2026 = Đông Chí** —
đúng như lịch vạn niên ghi.

> Engine `hnd` gốc chốt kinh độ tại **nửa đêm** nên gọi 04/02 là "Đại Hàn",
> 20/03 là "Kinh Trập", 22/12 là "Đại Tuyết". Đây là khác biệt quy ước, đã
> ghi thành xfail trong `tests/test_lunar_hnd.py`.

| # | Tiết | # | Tiết | # | Tiết |
|---|---|---|---|---|---|
| 0 | Lập Xuân | 8 | Mang Chủng | 16 | Hàn Lộ |
| 1 | Vũ Thủy | 9 | Hạ Chí | 17 | Sương Giáng |
| 2 | Kinh Trập | 10 | Tiểu Thử | 18 | Lập Đông |
| 3 | Xuân Phân | 11 | Đại Thử | 19 | Tiểu Tuyết |
| 4 | Thanh Minh | 12 | Lập Thu | 20 | Đại Tuyết |
| 5 | Cốc Vũ | 13 | Xử Thử | 21 | Đông Chí |
| 6 | Lập Hạ | 14 | Bạch Lộ | 22 | Tiểu Hàn |
| 7 | Tiểu Mãn | 15 | Thu Phân | 23 | Đại Hàn |

---

## 8. Bảng kiểm chứng

Toàn bộ số liệu dưới đây được chạy lại mỗi lần bằng `pytest tests -q` (xem
`docs/05-kiem-thu.md`).

### 8.1 Ngày Tết Nguyên Đán (31 năm, chuẩn Việt Nam)

| Năm | Tết | Năm | Tết | Năm | Tết |
|---|---|---|---|---|---|
| 1985 | 21/01 | 2000 | 05/02 | 2020 | 25/01 |
| 1990 | 27/01 | 2005 | 09/02 | 2021 | 12/02 |
| 1995 | 31/01 | 2010 | 14/02 | 2022 | 01/02 |
| 2015 | 19/02 | 2016 | 08/02 | 2023 | 22/01 |
| 2017 | 28/01 | 2018 | 16/02 | 2024 | 10/02 |
| 2019 | 05/02 | 2025 | 29/01 | 2026 | 17/02 |
| 2027 | 06/02 | 2028 | 26/01 | 2029 | 13/02 |
| **2030** | **02/02** | 2031 | 23/01 | 2032 | 11/02 |
| 2033 | 31/01 | 2034 | 19/02 | 2035 | 08/02 |
| 2036 | 28/01 | 2037 | 15/02 | 2038 | 04/02 |
| 2039 | 24/01 | 2040 | 12/02 | | |

> **2030** là một năm lệch giữa Việt Nam và Trung Quốc: điểm Sóc rơi
> 02/02/2030 lúc 23:06 giờ Hà Nội, nhưng đã là 00:06 ngày 03/02 theo giờ
> Bắc Kinh ⇒ Tết Việt Nam **02/02**, Tết Trung Quốc 03/02. Cả hai engine của
> dự án đều cho 02/02.

### 8.2 Tháng nhuận (18 năm, khớp lịch vạn niên Việt Nam)

| Năm | Nhuận | Năm | Nhuận | Năm | Nhuận |
|---|---|---|---|---|---|
| 1990 | 5 | 1993 | 3 | 1995 | 8 |
| 1998 | 5 | 2001 | 4 | 2004 | 2 |
| 2006 | 7 | 2009 | 5 | 2012 | 4 |
| 2014 | 9 | 2017 | 6 | 2020 | 4 |
| 2023 | 2 | 2025 | 6 | 2028 | 5 |
| 2031 | 3 | **2033** | **11** | 2036 | 6 |

### 8.3 Kiểm tra tính nhất quán

| Phép kiểm | Phạm vi | Kết quả |
|---|---|---|
| Ngày kế tiếp của âm lịch (không nhảy cóc, không trùng) | 1900 – 2200 (109.573 ngày) | **0 lỗi** |
| Chuyển đổi khứ hồi Dương → Âm → Dương | 1900 – 2100 | **0 lỗi** |
| Độ dài năm âm ∈ {353, 354, 355, 383, 384, 385} | 1900 – 2200 | **0 lỗi** |
| Ngày mùng 1 khứ hồi qua `lunar_to_solar` | 1900 – 2200 | **0 lỗi** |
| Thời gian dựng lưới lịch tháng (42 ô, cache nguội) | – | **0,8 ms** |
