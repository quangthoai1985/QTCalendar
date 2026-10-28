"""Cấu hình pytest dùng chung cho bộ test của QT Calendar.

Hai việc chính:

1. **Thêm ``src/`` vào ``sys.path``** – dự án dùng layout ``src/`` và không
   cài gói vào môi trường, nên nếu không thêm đường dẫn này thì
   ``import qtcalendar`` sẽ thất bại khi chạy ``pytest tests``.

2. **Fixture :func:`tmp_config_dir`** – tạo thư mục tạm *nằm trong*
   ``tests/`` thay vì ``%TEMP%``. Lý do: môi trường chạy của dự án có thể
   chặn ghi tệp vào thư mục tạm hệ thống (sandbox), trong khi ``tests/``
   luôn ghi được vì nằm trong workspace. Fixture tự dọn sạch sau mỗi test.
"""

from __future__ import annotations

import shutil
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

#: Thư mục gốc dự án (chứa ``src/``, ``tests/``, ``scripts/``).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Thư mục chứa mã nguồn gói ``qtcalendar``.
SRC_DIR = PROJECT_ROOT / "src"

#: Thư mục test – để các test import được module dữ liệu dùng chung nếu có.
TESTS_DIR = Path(__file__).resolve().parent

for _duong_dan in (SRC_DIR, TESTS_DIR):
    if str(_duong_dan) not in sys.path:
        sys.path.insert(0, str(_duong_dan))


@pytest.fixture()
def tmp_config_dir() -> Iterator[Path]:
    """Thư mục tạm riêng cho mỗi test, nằm trong ``tests/_tmp_work``.

    Dùng cho các test ghi/đọc tệp cấu hình. Không dùng fixture ``tmp_path``
    của pytest vì nó tạo thư mục dưới ``%TEMP%`` – nơi môi trường có thể
    chặn ghi tệp.
    """
    base = Path(__file__).resolve().parent / "_tmp_work"
    base.mkdir(parents=True, exist_ok=True)
    work = base / uuid.uuid4().hex[:12]
    work.mkdir()
    try:
        yield work
    finally:
        shutil.rmtree(work, ignore_errors=True)
        # Dọn thư mục cha nếu không còn ai dùng; nhiều test chạy song song
        # (hoặc cùng lúc) có thể làm thư mục còn tồn tại – bỏ qua lỗi.
        try:
            base.rmdir()
        except OSError:
            pass
