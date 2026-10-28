"""Kiểm thử kho ca dao – tục ngữ – danh ngôn offline.

Chạy độc lập::

    $env:PYTHONUTF8="1"; python -X utf8 -m pytest tests/test_quotes.py -q

Tệp test tự thêm ``src/`` vào ``sys.path`` nên không phụ thuộc cấu hình
``pytest``/``PYTHONPATH`` của môi trường.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

# --- Bảo đảm import được gói nằm trong src/ khi chạy pytest từ thư mục gốc ---
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qtcalendar.core import quotes  # noqa: E402  (phải sau khối sys.path)
from qtcalendar.core.types import Quote  # noqa: E402

EXPECTED_TOPICS = ("ca-dao", "tuc-ngu", "danh-ngon")
MIN_QUOTES = 420
MAX_LEN = 160
SHORT_LEN = 110

#: Ký tự Latinh có dấu – đủ để nhận diện văn bản tiếng Việt có dấu.
VIETNAMESE_CHARS = set(
    "ăâđêôơư"
    "ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    "ýàáãèéìíòóõùú"
)


@pytest.fixture(scope="module")
def raw_data() -> dict:
    """Nội dung JSON gốc đọc trực tiếp từ đĩa (UTF-8)."""
    return json.loads(quotes.DB_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tệp dữ liệu
# ---------------------------------------------------------------------------


def test_db_path_points_to_packaged_data() -> None:
    assert quotes.DB_PATH.name == "quotes.json"
    assert quotes.DB_PATH.parent.name == "data"
    assert quotes.DB_PATH.parent.parent.name == "qtcalendar"
    assert quotes.DB_PATH.is_file(), f"Thiếu tệp dữ liệu: {quotes.DB_PATH}"


def test_json_structure(raw_data: dict) -> None:
    assert isinstance(raw_data, dict)
    assert raw_data["version"] >= 1
    labels = raw_data["topics"]
    assert isinstance(labels, dict)
    assert set(labels) == set(EXPECTED_TOPICS)
    assert all(isinstance(v, str) and v.strip() for v in labels.values())
    assert isinstance(raw_data["items"], list)


def test_enough_quotes_overall() -> None:
    assert len(quotes.all_quotes()) >= MIN_QUOTES


def test_topic_distribution(raw_data: dict) -> None:
    counts = Counter(item["topic"] for item in raw_data["items"])
    assert set(counts) == set(EXPECTED_TOPICS)
    # Phân bổ mục tiêu ~200/150/70, kiểm tra ngưỡng tối thiểu rộng rãi.
    assert counts["ca-dao"] >= 180, counts
    assert counts["tuc-ngu"] >= 140, counts
    assert counts["danh-ngon"] >= 65, counts
    # Tổng theo chủ đề = tổng kho sau khi nạp.
    assert sum(counts.values()) == len(quotes.all_quotes())


def test_no_duplicates() -> None:
    normalized = [" ".join(q.text.lower().split()) for q in quotes.all_quotes()]
    duplicates = [text for text, count in Counter(normalized).items() if count > 1]
    assert duplicates == [], f"Câu trùng: {duplicates}"


def test_texts_not_empty_and_clean() -> None:
    for quote in quotes.all_quotes():
        assert quote.text == quote.text.strip()
        assert "  " not in quote.text
        assert quote.text.isprintable()


def test_text_lengths() -> None:
    texts = [q.text for q in quotes.all_quotes()]
    assert max(len(t) for t in texts) <= MAX_LEN
    short_ratio = sum(1 for t in texts if len(t) < SHORT_LEN) / len(texts)
    # Phần lớn câu phải đủ ngắn để vừa khung lịch bloc.
    assert short_ratio >= 0.9, f"Chỉ {short_ratio:.0%} câu ngắn dưới {SHORT_LEN} ký tự"


def test_all_texts_are_vietnamese_with_diacritics() -> None:
    for quote in quotes.all_quotes():
        assert set(quote.text) & VIETNAMESE_CHARS, f"Không có dấu tiếng Việt: {quote.text!r}"


def test_topics_are_known() -> None:
    for quote in quotes.all_quotes():
        assert quote.topic in EXPECTED_TOPICS


def test_authors_are_consistent() -> None:
    for quote in quotes.all_quotes():
        if quote.topic == "danh-ngon":
            assert quote.author.strip(), f"Danh ngôn thiếu tác giả: {quote.text!r}"
        elif quote.topic == "ca-dao":
            assert quote.author == "", f"Ca dao không nên ghi tác giả: {quote.text!r}"
        else:
            assert quote.author.strip(), f"Tục ngữ thiếu nguồn: {quote.text!r}"


# ---------------------------------------------------------------------------
# API truy xuất
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topic", EXPECTED_TOPICS)
def test_quotes_by_topic(topic: str) -> None:
    selected = quotes.quotes_by_topic(topic)
    assert selected, f"Chủ đề {topic!r} rỗng"
    assert all(q.topic == topic for q in selected)
    assert all(isinstance(q, Quote) for q in selected)


def test_quotes_by_topic_partitions_all() -> None:
    total = sum(len(quotes.quotes_by_topic(topic)) for topic in quotes.topics())
    assert total == len(quotes.all_quotes())


def test_quotes_by_topic_unknown_is_empty() -> None:
    assert quotes.quotes_by_topic("khong-ton-tai") == ()
    assert quotes.quotes_by_topic("") == ()


def test_topics() -> None:
    codes = quotes.topics()
    assert set(codes) == set(EXPECTED_TOPICS)
    assert codes == quotes.topics(), "topics() phải ổn định giữa các lần gọi"


def test_quote_of_day_is_stable() -> None:
    day = date(2026, 10, 28)
    first = quotes.quote_of_day(day)
    assert quotes.quote_of_day(day) == first
    assert first in quotes.all_quotes()
    # Ngày khác ngày đầu cũng ổn định.
    second = quotes.quote_of_day(date(2027, 1, 1))
    assert quotes.quote_of_day(date(2027, 1, 1)) == second


def test_quote_of_day_defaults_to_today() -> None:
    today = date.today()
    assert quotes.quote_of_day() == quotes.quote_of_day(today)


def test_quote_of_day_covers_days_evenly() -> None:
    start = date(2024, 1, 1)
    picked = {quotes.quote_of_day(start + timedelta(days=offset)) for offset in range(400)}
    assert len(picked) >= 100, f"Chỉ phủ {len(picked)} câu khác nhau trong 400 ngày"
    assert picked <= set(quotes.all_quotes())


def test_random_quote_is_reproducible() -> None:
    first = [quotes.random_quote(random.Random(2026)) for _ in range(25)]
    second = [quotes.random_quote(random.Random(2026)) for _ in range(25)]
    assert first == second
    assert all(isinstance(q, Quote) for q in first)
    assert all(q in quotes.all_quotes() for q in first)


def test_random_quote_without_rng() -> None:
    assert quotes.random_quote() in quotes.all_quotes()


def test_reload_returns_count() -> None:
    expected = len(quotes.all_quotes())
    assert quotes.reload() == expected
    assert len(quotes.all_quotes()) == expected


# ---------------------------------------------------------------------------
# UTF-8 và tình huống tệp thiếu/hỏng
# ---------------------------------------------------------------------------


def test_utf8_roundtrip() -> None:
    """Đọc/ghi UTF-8 không làm hỏng dấu tiếng Việt."""
    raw_bytes = quotes.DB_PATH.read_bytes()
    text = raw_bytes.decode("utf-8")
    data = json.loads(text)
    encoded_again = json.dumps(data, ensure_ascii=False).encode("utf-8")
    loaded = json.loads(encoded_again.decode("utf-8"))
    assert loaded == data
    assert any(set(item["text"]) & VIETNAMESE_CHARS for item in loaded["items"])


def test_missing_file_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    original = quotes.DB_PATH
    missing = ROOT / "tests" / "khong-ton-tai-quotes.json"
    try:
        monkeypatch.setattr(quotes, "DB_PATH", missing)
        quotes.reload()
        assert quotes.quote_of_day(date(2026, 10, 28)).text
        assert len(quotes.all_quotes()) >= 1
        assert quotes.quotes_by_topic("ca-dao")
        assert quotes.topics()
        assert quotes.random_quote(random.Random(7)) in quotes.all_quotes()
    finally:
        monkeypatch.setattr(quotes, "DB_PATH", original)
        quotes.reload()


def test_corrupt_file_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tệp mã nguồn .py chắc chắn không phải JSON hợp lệ.
    original = quotes.DB_PATH
    broken = Path(quotes.__file__)
    try:
        monkeypatch.setattr(quotes, "DB_PATH", broken)
        quotes.reload()
        fallback_quotes = quotes.all_quotes()
        assert len(fallback_quotes) >= 1
        assert fallback_quotes[0].text
        assert quotes.quote_of_day(date(2026, 1, 1)).text
        assert quotes.reload() == len(fallback_quotes)
    finally:
        monkeypatch.setattr(quotes, "DB_PATH", original)
        quotes.reload()


def test_fallback_quote_constant() -> None:
    assert isinstance(quotes.FALLBACK_QUOTE, Quote)
    assert quotes.FALLBACK_QUOTE.text.strip()
    assert quotes.FALLBACK_QUOTE.topic in EXPECTED_TOPICS
