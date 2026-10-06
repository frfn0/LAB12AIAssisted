"""Тесты создания и чтения книг (POST /items, GET /items)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.isbn import make_isbn13

ERROR_422 = 422


def test_создание_книги(client: TestClient, book_payload: dict[str, object]) -> None:
    """Книга создаётся, свободные экземпляры равны общему числу."""
    response = client.post("/items", json=book_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == "Мастер и Маргарита"
    assert body["author"] == "Булгаков М.А."
    assert body["year"] == 1967
    assert body["total_copies"] == 3
    assert body["available_copies"] == 3


def test_свободные_экземпляры_явно_указываются(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Переданное число свободных экземпляров сохраняется."""
    response = client.post("/items", json={**book_payload, "available_copies": 1})

    assert response.status_code == 201
    assert response.json()["available_copies"] == 1


def test_свободные_экземпляры_не_превышают_общее_число(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Значение сверх total_copies уменьшается до total_copies."""
    response = client.post("/items", json={**book_payload, "available_copies": 99})

    assert response.status_code == 201
    assert response.json()["available_copies"] == book_payload["total_copies"]


def test_пробелы_в_строковых_полях_убираются(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Вокруг названия и автора обрезаются лишние пробелы."""
    payload = {**book_payload, "title": "  Мастер и Маргарита  "}
    response = client.post("/items", json=payload)

    assert response.status_code == 201
    assert response.json()["title"] == "Мастер и Маргарита"


def test_строка_из_одних_пробелов_отклоняется(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Поле, состоящее только из пробелов, не проходит валидацию."""
    response = client.post("/items", json={**book_payload, "title": "   "})

    assert response.status_code == ERROR_422
    assert response.json()["detail"][0]["loc"][1] == "title"


def test_дубликат_isbn_отклоняется(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Вторая книга с тем же ISBN даёт 409."""
    client.post("/items", json=book_payload)
    response = client.post("/items", json={**book_payload, "title": "Другая книга"})

    assert response.status_code == 409
    assert response.json()["error_type"] == "ConflictError"


def test_невалидные_данные_дают_422_со_всеми_ошибками(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Pydantic возвращает ошибки по каждому неверному полю сразу."""
    invalid = {"isbn": "123", "title": "", "year": 999, "total_copies": -4}
    response = client.post("/items", json={**book_payload, **invalid})

    assert response.status_code == ERROR_422
    fields = {error["loc"][1] for error in response.json()["detail"]}
    assert fields == {"isbn", "title", "year", "total_copies"}


def test_слишком_длинное_поле_отклоняется(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Название длиннее 255 символов не принимается."""
    response = client.post("/items", json={**book_payload, "title": "а" * 256})

    assert response.status_code == ERROR_422


def test_пустой_список_книг(client: TestClient) -> None:
    """В пустой базе список пуст."""
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == []


def test_список_содержит_созданные_книги(
    client: TestClient, book_payload: dict[str, object], created_book: dict[str, object]
) -> None:
    """Созданная книга появляется в списке."""
    client.post("/items", json={**book_payload, "isbn": "978-0-13-235088-4"})

    response = client.get("/items")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_пагинация_сдвигает_выборку(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Параметры skip и limit ограничивают выборку."""
    for index in range(3):
        # Номер формируется с корректной контрольной цифрой: иначе
        # проверка ISBN из задания 10 отвергла бы эти книги.
        isbn = make_isbn13(f"978517115{index:03d}")
        client.post(
            "/items",
            json={**book_payload, "isbn": isbn, "title": f"Книга {index}"},
        )

    response = client.get("/items", params={"skip": 1, "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Книга 1"


def test_лимит_вне_диапазона_даёт_422(client: TestClient) -> None:
    """Значение limit больше максимума отклоняется."""
    response = client.get("/items", params={"limit": 9999})

    assert response.status_code == ERROR_422
    assert response.json()["detail"][0]["loc"][1] == "limit"


def test_чтение_книги_по_id(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Книга читается по идентификатору."""
    response = client.get(f"/items/{created_book['id']}")

    assert response.status_code == 200
    assert response.json()["isbn"] == created_book["isbn"]


def test_чтение_несуществующей_книги_даёт_404(client: TestClient) -> None:
    """Отсутствующий идентификатор даёт 404."""
    response = client.get("/items/999")

    assert response.status_code == 404
    assert response.json()["error_type"] == "NotFoundError"
