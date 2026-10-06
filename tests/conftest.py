"""Общие фикстуры тестов.

Переменная DATABASE_URL выставляется до импорта приложения: движок создаётся
на этапе импорта app.database, и база в памяти избавляет тесты от файлов на
диске и от взаимного влияния друг на друга.
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite://"
os.environ["SQL_ECHO"] = "false"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import create_app  # noqa: E402

BOOK = {
    "isbn": "978-5-17-115205-5",
    "title": "Мастер и Маргарита",
    "author": "Булгаков М.А.",
    "year": 1967,
    "genre": "Художественная литература",
    "total_copies": 3,
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Тестовый клиент с чистой базой на каждый тест."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(create_app()) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def book_payload() -> dict[str, object]:
    """Корректное тело запроса для создания книги."""
    return dict(BOOK)


@pytest.fixture
def created_book(
    client: TestClient, book_payload: dict[str, object]
) -> dict[str, object]:
    """Созданная книга, чтобы тестам не приходилось повторять POST."""
    response = client.post("/items", json=book_payload)
    assert response.status_code == 201
    result: dict[str, object] = response.json()
    return result
