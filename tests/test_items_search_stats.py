"""Тесты поиска и сводки по фонду."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import _unicode_lower


def test_поиск_по_автору_не_зависит_от_регистра(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Регрессия: поиск по кириллице обязан работать в любом регистре.

    Встроенная lower() в SQLite умеет менять регистр только для ASCII,
    поэтому функция lower() заменена на Python-реализацию.
    """
    for query in ("булгаков", "БУЛГАКОВ", "Булгаков"):
        response = client.get("/items", params={"search": query})

        assert response.status_code == 200, query
        assert len(response.json()) == 1, query
        assert response.json()[0]["id"] == created_book["id"], query


def test_поиск_по_названию_не_зависит_от_регистра(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Название книги находится в любом регистре."""
    response = client.get("/items", params={"search": "МАСТЕР"})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Мастер и Маргарита"


def test_поиск_без_совпадений_возвращает_пустой_список(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Запрос, которому ничего не соответствует, даёт пустой список."""
    response = client.get("/items", params={"search": "Толстой"})

    assert response.status_code == 200
    assert response.json() == []


def test_пустой_поиск_не_ограничивает_выборку(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Пустая строка поиска не превращается в шаблон «%» с потерей данных."""
    response = client.get("/items", params={"search": ""})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_поиск_находит_несколько_книг(
    client: TestClient, book_payload: dict[str, object], created_book: dict[str, object]
) -> None:
    """Совпадения по разным полям объединяются в один результат."""
    client.post(
        "/items",
        json={
            **book_payload,
            "isbn": "978-0-13-235088-4",
            "title": "Clean Code",
            "author": "Мартин",
        },
    )

    response = client.get("/items", params={"search": "м"})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_сводка_по_пустому_фонду(client: TestClient) -> None:
    """В пустой базе сводка нулевая, а не падает."""
    response = client.get("/items/stats/summary")

    assert response.status_code == 200
    assert response.json() == {
        "titles": 0,
        "total_copies": 0,
        "available_copies": 0,
        "issued_copies": 0,
    }


def test_сводка_учитывает_выданные_экземпляры(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Число выданных экземпляров считается как разница."""
    client.post(
        "/items", json={**book_payload, "total_copies": 5, "available_copies": 2}
    )

    response = client.get("/items/stats/summary")

    body = response.json()
    assert body["titles"] == 1
    assert body["total_copies"] == 5
    assert body["available_copies"] == 2
    assert body["issued_copies"] == 3


def test_unicode_lower_сохраняет_none() -> None:
    """Хелпер lower() корректно обрабатывает NULL."""
    assert _unicode_lower(None) is None
    assert _unicode_lower("ПРИВЕТ") == "привет"
    assert _unicode_lower("") == ""
