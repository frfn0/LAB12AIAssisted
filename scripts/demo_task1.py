"""Демонстрация задания 1: все операции CRUD основной сущности (книга).

Скрипт обращается к запущенному приложению по HTTP и печатает фактические
ответы сервера вместе с кодами статуса.

Запуск:
    uvicorn app.main:app --port 8000
    python scripts/demo_task1.py
"""

from __future__ import annotations

import os
import sys

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

BOOK_MASTER = {
    "isbn": "978-5-17-115205-6",
    "title": "Мастер и Маргарита",
    "author": "Булгаков М.А.",
    "year": 1967,
    "genre": "Художественная литература",
    "total_copies": 3,
}

BOOK_CLEAN_CODE = {
    "isbn": "978-0-13-235088-4",
    "title": "Clean Code",
    "author": "Роберт Мартин",
    "year": 2008,
    "genre": "Программирование",
    "total_copies": 1,
}

INVALID_BOOK = {
    "isbn": "123",
    "title": "",
    "author": "X",
    "year": 999,
    "genre": "G",
    "total_copies": -4,
}


def show(
    client: httpx.Client,
    number: str,
    title: str,
    method: str,
    path: str,
    **kwargs: object,
) -> None:
    """Выполняет запрос и печатает его вместе с ответом."""
    response = client.request(method, path, **kwargs)
    print(f"{number} {method} {path} - {title}")
    print(f"    HTTP {response.status_code}")
    print(f"    {response.text}")
    print()


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        try:
            health = client.get("/health")
        except httpx.RequestError as exc:
            print(f"Сервер не отвечает на {BASE_URL}: {exc}")
            print("Запустите его командой: uvicorn app.main:app --port 8000")
            return 1

        print(f"Приложение: {BASE_URL}")
        print("GET /health - проверка состояния")
        print(f"    HTTP {health.status_code}")
        print(f"    {health.text}")
        print()

        show(client, "1.", "создание книги", "POST", "/items", json=BOOK_MASTER)
        show(
            client,
            "2.",
            "создание второй книги",
            "POST",
            "/items",
            json=BOOK_CLEAN_CODE,
        )
        show(client, "3.", "дубликат ISBN -> 409", "POST", "/items", json=BOOK_MASTER)
        show(client, "4.", "список книг", "GET", "/items")
        show(client, "5.", "книга по id", "GET", "/items/1")
        show(client, "6.", "несуществующий id -> 404", "GET", "/items/999")
        show(
            client,
            "7.",
            "частичное обновление (PUT)",
            "PUT",
            "/items/1",
            json={"genre": "Классика", "total_copies": 5},
        )
        show(
            client,
            "8.",
            "невалидные данные -> 422",
            "POST",
            "/items",
            json=INVALID_BOOK,
        )
        show(
            client,
            "9.",
            "поиск по автору в другом регистре",
            "GET",
            "/items",
            params={"search": "булгаков"},
        )
        show(
            client,
            "10.",
            "поиск по названию в другом регистре",
            "GET",
            "/items",
            params={"search": "МАСТЕР"},
        )
        show(
            client,
            "11.",
            "поиск без совпадений",
            "GET",
            "/items",
            params={"search": "книга"},
        )
        show(client, "12.", "удаление книги -> 204", "DELETE", "/items/2")
        show(client, "13.", "удаление ещё раз -> 404", "DELETE", "/items/2")
        show(client, "14.", "сводка по фонду", "GET", "/items/stats/summary")
        show(
            client,
            "15.",
            "выход за пределы пагинации -> 422",
            "GET",
            "/items",
            params={"limit": 9999},
        )

        spec = client.get("/openapi.json").json()
        print("16. Состав API по спецификации OpenAPI")
        for path, operations in sorted(spec["paths"].items()):
            methods = ", ".join(sorted(method.upper() for method in operations))
            print(f"    {methods:<20} {path}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
