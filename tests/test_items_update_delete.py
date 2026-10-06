"""Тесты обновления и удаления книг (PUT, DELETE)."""

from __future__ import annotations

from fastapi.testclient import TestClient

ERROR_422 = 422


def test_частичное_обновление_меняет_только_переданные_поля(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Остальные поля сохраняют прежние значения."""
    response = client.put(f"/items/{created_book['id']}", json={"genre": "Классика"})

    assert response.status_code == 200
    body = response.json()
    assert body["genre"] == "Классика"
    assert body["title"] == created_book["title"]
    assert body["total_copies"] == created_book["total_copies"]


def test_пустое_тело_не_меняет_книгу(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Запрос без полей оставляет книгу без изменений."""
    response = client.put(f"/items/{created_book['id']}", json={})

    assert response.status_code == 200
    assert response.json() == created_book


def test_увеличение_общего_числа_пересчитывает_свободные(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Новые экземпляры сразу попадают в свободные."""
    response = client.put(f"/items/{created_book['id']}", json={"total_copies": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["total_copies"] == 5
    assert body["available_copies"] == 5


def test_свободные_экземпляры_не_увеличиваются_при_добавлении(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Если часть экземпляров выдана, новые идут в общий счёт, а не в свободные."""
    created = client.post(
        "/items",
        json={**book_payload, "total_copies": 5, "available_copies": 2},
    ).json()

    response = client.put(f"/items/{created['id']}", json={"total_copies": 9})

    body = response.json()
    assert body["total_copies"] == 9
    assert body["available_copies"] == 6  # было 5-2=3 выдано, добавили 4 -> 2+4


def test_нельзя_уменьшить_число_экземпляров_ниже_выданных(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """total_copies меньше числа выданных экземпляров даёт 409."""
    created = client.post(
        "/items",
        json={**book_payload, "total_copies": 5, "available_copies": 1},
    ).json()

    response = client.put(f"/items/{created['id']}", json={"total_copies": 2})

    assert response.status_code == 409
    assert "в выдаче 4 шт." in response.json()["detail"]


def test_невалидные_данные_при_обновлении_дают_422(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Ограничения Pydantic действуют и на обновление."""
    response = client.put(f"/items/{created_book['id']}", json={"year": 1200})

    assert response.status_code == ERROR_422


def test_неизвестное_поле_при_обновлении_даёт_422(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """ItemUpdate запрещает поля, которых нет в модели."""
    response = client.put(
        f"/items/{created_book['id']}",
        json={"isbn": "978-5-17-115205-5"},
    )

    assert response.status_code == ERROR_422


def test_обновление_несуществующей_книги_даёт_404(client: TestClient) -> None:
    """PUT по отсутствующему идентификатору даёт 404."""
    response = client.put("/items/999", json={"genre": "Художественная литература"})

    assert response.status_code == 404


def test_удаление_книги(client: TestClient, created_book: dict[str, object]) -> None:
    """Удаление возвращает 204 без тела ответа."""
    response = client.delete(f"/items/{created_book['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/items/{created_book['id']}").status_code == 404


def test_повторное_удаление_даёт_404(
    client: TestClient, created_book: dict[str, object]
) -> None:
    """Второе удаление той же книги даёт 404."""
    client.delete(f"/items/{created_book['id']}")

    response = client.delete(f"/items/{created_book['id']}")

    assert response.status_code == 404


def test_нельзя_удалить_книгу_с_выданными_экземплярами(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Книга, у которой выдан хотя бы один экземпляр, не удаляется."""
    created = client.post(
        "/items",
        json={**book_payload, "total_copies": 3, "available_copies": 1},
    ).json()

    response = client.delete(f"/items/{created['id']}")

    assert response.status_code == 409
    assert "в выдаче 2 шт." in response.json()["detail"]
