"""Kho ca dao – tục ngữ – danh ngôn offline.

Dữ liệu nằm trong ``qtcalendar/data/quotes.json`` (đi kèm ứng dụng, không cần
mạng). Module này chỉ đọc một lần rồi cache trong bộ nhớ.

Hợp đồng API
============

::

    all_quotes()            -> tuple[Quote, ...]      # toàn bộ kho
    quote_of_day(day)       -> Quote                  # ổn định theo ngày
    random_quote(rng=None)  -> Quote                  # ngẫu nhiên
    quotes_by_topic(topic)  -> tuple[Quote, ...]
    topics()                -> tuple[str, ...]
    reload()                -> int                    # nạp lại, trả số câu
    DB_PATH                 -> Path

Quy ước dữ liệu: tệp JSON dạng ::

    {
      "version": 1,
      "topics": {"ca-dao": "Ca dao", "tuc-ngu": "Tục ngữ", "danh-ngon": "Danh ngôn"},
      "items": [
        {"text": "Một cây làm chẳng nên non…", "author": "", "topic": "ca-dao"},
        …
      ]
    }

Yêu cầu chất lượng dữ liệu:

* **Chỉ dùng ca dao/tục ngữ Việt Nam viết đúng chính tả có dấu**, không
  trùng lặp câu, không có câu rỗng.
* Tối thiểu **400 câu**, nên đủ 3 chủ đề: ``ca-dao`` (tình yêu quê hương,
  lao động, gia đình), ``tuc-ngu`` (kinh nghiệm thời tiết, mùa vụ, ứng xử),
  ``danh-ngon`` (danh ngôn Việt Nam và thế giới, có ghi tác giả khi biết).
* Không có câu quá dài (> 160 ký tự) để vừa khung bloc.

Ghi chú triển khai
==================

* Tệp JSON được đọc **đúng một lần** rồi cache trong bộ nhớ; :func:`reload`
  xoá cache để đọc lại (tiện khi phát triển hoặc khi người dùng thay dữ liệu).
* Tệp thiếu/hỏng/không đúng cấu trúc **không làm module crash**: kho coi như
  chỉ có một câu dự phòng cố định (:data:`FALLBACK_QUOTE`) để giao diện luôn
  có nội dung hiển thị.
* :func:`quote_of_day` băm theo ``date.toordinal()`` nên cùng một ngày luôn
  cho cùng một câu và ổn định giữa các lần chạy (không dùng ``hash()`` vì
  ``hash()`` của chuỗi bị làm muối ngẫu nhiên theo từng tiến trình).
"""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from .types import Quote

__all__ = [
    "DB_PATH",
    "FALLBACK_QUOTE",
    "all_quotes",
    "quote_of_day",
    "random_quote",
    "quotes_by_topic",
    "topics",
    "reload",
]

#: Đường dẫn kho dữ liệu (đi kèm mã nguồn).
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "quotes.json"

#: Câu dự phòng cố định, dùng khi tệp dữ liệu thiếu hoặc hỏng.
FALLBACK_QUOTE = Quote(
    text="Một cây làm chẳng nên non, ba cây chụm lại nên hòn núi cao.",
    author="",
    topic="ca-dao",
)

#: Thứ tự ưu tiên của các chủ đề chuẩn khi liệt kê.
_TOPIC_ORDER: tuple[str, ...] = ("ca-dao", "tuc-ngu", "danh-ngon")

#: Toàn bộ kho sau lần nạp đầu tiên (``None`` = chưa nạp).
_cache: tuple[Quote, ...] | None = None

#: Chỉ mục theo chủ đề, dựng cùng lúc với ``_cache``.
_by_topic: dict[str, tuple[Quote, ...]] = {}


def _load(path: Path) -> tuple[Quote, ...]:
    """Đọc và kiểm tra tệp JSON; trả về tuple rỗng nếu không dùng được."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()

    if not isinstance(payload, dict):
        return ()
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return ()

    quotes: list[Quote] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        text = " ".join(text.split())
        if not text or text in seen:
            continue
        seen.add(text)

        author = item.get("author")
        if isinstance(author, str):
            author = " ".join(author.split())
        else:
            author = ""

        topic = item.get("topic")
        if isinstance(topic, str) and topic.strip():
            topic = topic.strip().lower()
        else:
            topic = "ca-dao"

        quotes.append(Quote(text=text, author=author, topic=topic))
    return tuple(quotes)


def _group(quotes: tuple[Quote, ...]) -> dict[str, tuple[Quote, ...]]:
    """Nhóm câu theo chủ đề (mã chủ đề đã chuẩn hoá chữ thường)."""
    grouped: dict[str, list[Quote]] = {}
    for quote in quotes:
        grouped.setdefault(quote.topic, []).append(quote)
    return {code: tuple(items) for code, items in grouped.items()}


def _ensure_loaded() -> tuple[Quote, ...]:
    """Nạp kho lần đầu nếu cần rồi trả về cache (luôn khác rỗng)."""
    global _cache, _by_topic
    if _cache is None:
        loaded = _load(DB_PATH)
        # Tệp thiếu/hỏng: vẫn phải có ít nhất một câu để UI không trống.
        _cache = loaded if loaded else (FALLBACK_QUOTE,)
        _by_topic = _group(_cache)
    return _cache


def all_quotes() -> tuple[Quote, ...]:
    """Toàn bộ kho ca dao (đã cache sau lần đọc đầu)."""
    return _ensure_loaded()


def quote_of_day(day: date | None = None) -> Quote:
    """Câu ca dao của ngày – phải **ổn định** với cùng một ngày.

    Dùng ``date.toordinal()`` (số ngày tuyệt đối) thay cho ``hash()`` để kết
    quả giống nhau ở mọi lần chạy và mọi tiến trình. Khi ``day`` là ``None``
    thì lấy ngày hôm nay.
    """
    quotes = _ensure_loaded()
    if day is None:
        day = date.today()
    return quotes[day.toordinal() % len(quotes)]


def random_quote(rng: random.Random | None = None) -> Quote:
    """Một câu ngẫu nhiên (dùng ``rng`` nếu được truyền để tái lập được).

    Truyền ``random.Random(seed)`` để chuỗi kết quả lặp lại được giữa các lần
    chạy; bỏ qua ``rng`` thì dùng bộ sinh ngẫu nhiên toàn cục của module
    :mod:`random`.
    """
    quotes = _ensure_loaded()
    if rng is None:
        return random.choice(quotes)
    return rng.choice(quotes)


def quotes_by_topic(topic: str) -> tuple[Quote, ...]:
    """Các câu thuộc một chủ đề.

    ``topic`` được so khớp sau khi bỏ khoảng trắng thừa và không phân biệt
    chữ hoa/chữ thường. Chủ đề không tồn tại trả về tuple rỗng.
    """
    if not isinstance(topic, str):
        return ()
    _ensure_loaded()
    return _by_topic.get(topic.strip().lower(), ())


def topics() -> tuple[str, ...]:
    """Danh sách mã chủ đề có trong kho.

    Các chủ đề chuẩn (``ca-dao``, ``tuc-ngu``, ``danh-ngon``) đứng trước theo
    đúng thứ tự, chủ đề lạ (nếu tệp dữ liệu bổ sung) xếp sau theo alphabet.
    """
    _ensure_loaded()
    known = [code for code in _TOPIC_ORDER if code in _by_topic]
    extra = sorted(code for code in _by_topic if code not in _TOPIC_ORDER)
    return tuple(known + extra)


def reload() -> int:
    """Nạp lại tệp JSON (dùng khi phát triển), trả về số câu."""
    global _cache, _by_topic
    _cache = None
    _by_topic = {}
    return len(_ensure_loaded())
