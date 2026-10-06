"""Тесты безопасности: заголовки, ключ доступа, валидация и утечки.

Каждый тест соответствует одному пункту из задания о поиске уязвимостей.
"""

from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

from app.api.items import _escape_like
from app.config import get_settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

VALID_BOOK = {
    "isbn": "978-5-17-115205-6",
    "title": "Мастер и Маргарита",
    "author": "Булгаков М.А.",
    "year": 1967,
    "genre": "Художественная литература",
    "total_copies": 3,
}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------- заголовки безопасности


@pytest.mark.parametrize(("header", "expected"), SECURITY_HEADERS.items())
def test_заголовки_безопасности_присутствуют(
    client: TestClient, header: str, expected: str
) -> None:
    """uvicorn не выставляет эти заголовки, добавляем их сами."""
    response = client.get("/health")

    assert response.headers.get(header) == expected


def test_заголовки_есть_и_на_ошибочных_ответах(client: TestClient) -> None:
    """Заголовки ставятся на любой ответ, а не только на успешный."""
    response = client.get("/items/999")

    assert response.status_code == 404
    for header, expected in SECURITY_HEADERS.items():
        assert response.headers.get(header) == expected


def test_приложение_само_не_добавляет_заголовок_server(client: TestClient) -> None:
    """Приложение не выставляет Server и не пытается его удалять.

    На уровне приложения этот заголовок удалить невозможно: uvicorn
    добавляет его после возврата ответа. Отключается флагом запуска
    --no-server-header, что проверяется отдельным тестом ниже.
    """
    response = client.get("/health")

    assert "server" not in {key.lower() for key in response.headers}


@pytest.mark.parametrize("command_file", ["Dockerfile", "README.md"])
def test_флаг_отключения_server_header_прописан(command_file: str) -> None:
    """Флаг --no-server-header должен быть в Dockerfile и в инструкции."""
    with open(os.path.join(REPO_ROOT, command_file), encoding="utf-8") as source_file:
        content = source_file.read()

    assert "--no-server-header" in content, command_file


def test_ошибочный_код_тоже_получает_заголовки(client: TestClient) -> None:
    """Даже 404 отдаётся с защитными заголовками."""
    response = client.get("/nonexistent")

    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# ------------------------------------------------------------------ доступность


def test_чтение_доступно_без_ключа(client: TestClient) -> None:
    """Каталог фонда должен быть виден и без ключа."""
    assert client.get("/items").status_code == 200
    assert client.get("/health").status_code == 200


def test_запись_проходит_без_ключа_когда_он_не_задан(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Пустой API_KEY означает режим разработки без проверки."""
    assert get_settings().api_key == ""

    response = client.post("/items", json=book_payload)

    assert response.status_code == 201


@pytest.fixture
def client_with_key() -> TestClient:
    """Тестовый клиент с включённой проверкой ключа."""
    from app.database import Base, engine
    from app.main import create_app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    os.environ["API_KEY"] = "secret-key-123"
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as test_client:
            yield test_client
    finally:
        del os.environ["API_KEY"]
        get_settings.cache_clear()
        Base.metadata.drop_all(bind=engine)


def test_запись_без_ключа_даёт_401(client_with_key: TestClient) -> None:
    """Изменение данных без ключа запрещено."""
    response = client_with_key.post("/items", json=VALID_BOOK)

    assert response.status_code == 401
    assert response.json()["error_type"] == "UnauthorizedError"


def test_запись_с_неверным_ключом_даёт_401(client_with_key: TestClient) -> None:
    """Неверный ключ равносилен его отсутствию."""
    response = client_with_key.post(
        "/items", json=VALID_BOOK, headers={"X-API-Key": "wrong"}
    )

    assert response.status_code == 401


def test_запись_с_верным_ключом_проходит(client_with_key: TestClient) -> None:
    """С верным ключом изменение данных разрешено."""
    response = client_with_key.post(
        "/items", json=VALID_BOOK, headers={"X-API-Key": "secret-key-123"}
    )

    assert response.status_code == 201


def test_удаление_без_ключа_даёт_401(client_with_key: TestClient) -> None:
    """Защита распространяется и на удаление."""
    book_id = client_with_key.post(
        "/items", json=VALID_BOOK, headers={"X-API-Key": "secret-key-123"}
    ).json()["id"]

    response = client_with_key.delete(f"/items/{book_id}")

    assert response.status_code == 401


def test_чтение_доступно_даже_с_включённым_ключом(client_with_key: TestClient) -> None:
    """Ключ защищает только запись, чтение остаётся открытым."""
    assert client_with_key.get("/items").status_code == 200


# ------------------------------------------------------------- mass assignment


def test_лишнее_поле_при_создании_даёт_422(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """extra=forbid не даёт молча принять неизвестное поле."""
    response = client.post("/items", json={**book_payload, "is_admin": True})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_нельзя_подставить_идентификатор_из_запроса(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Идентификатор назначает сервер, клиент его задать не может."""
    response = client.post("/items", json={**book_payload, "id": 999})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_свободные_экземпляры_из_запроса_не_превышают_общее_число(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """available_copies - разрешённое поле, но сервер ограничивает его сверху."""
    response = client.post("/items", json={**book_payload, "available_copies": 999})

    assert response.status_code == 201
    assert response.json()["available_copies"] == book_payload["total_copies"]


# -------------------------------------------------------- экранирование LIKE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Булгаков", "Булгаков"),
        ("100%", "100\\%"),
        ("a_b", "a\\_b"),
        ("a\\b", "a\\\\b"),
        ("50% скидка_в_чёрный", "50\\% скидка\\_в\\_чёрный"),
    ],
)
def test_спецсимволы_like_экранируются(raw: str, expected: str) -> None:
    """Символы % и _ не должны работать как маски."""
    assert _escape_like(raw) == expected


@pytest.mark.parametrize("mask", ["%", "_", "%%", "%%_"])
def test_спецсимволы_не_превращаются_в_маску(
    client: TestClient, book_payload: dict[str, object], mask: str
) -> None:
    """Запрос из одних спецсимволов не возвращает весь каталог."""
    client.post("/items", json=book_payload)
    client.post("/items", json={**book_payload, "isbn": "978-0-13-235088-4"})

    response = client.get("/items", params={"search": mask})

    assert response.status_code == 200
    assert response.json() == []


def test_поиск_со_знаком_процента_по_настоящему_работает(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Экранирование не ломает поиск по названиям со знаком процента."""
    client.post("/items", json={**book_payload, "title": "Скидки 50% и выше"})

    response = client.get("/items", params={"search": "50%"})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Скидки 50% и выше"


# ------------------------------------------------------- утечка внутренних деталей


def test_ошибка_валидации_не_возвращает_входные_значения(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Стандартный ответ Pydantic повторяет значения, здесь - нет."""
    response = client.post("/items", json={**book_payload, "year": 1200})

    body = response.json()
    assert response.status_code == 422
    assert body["error_type"] == "ValidationError"
    for error in body["detail"]:
        assert set(error) == {"type", "loc", "msg"}
    assert "1200" not in response.text


def test_непредвиденная_ошибка_не_раскрывает_детали(client: TestClient) -> None:
    """Клиент получает обезличенный текст вместо текста исключения."""
    from app.main import create_app

    application = create_app()

    @application.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("sqlite://user:secret@host/db - таблица books повреждена")

    with TestClient(application, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_test/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Внутренняя ошибка сервера"
    assert body["error_type"] == "InternalServerError"
    assert "secret" not in response.text
    assert "books" not in response.text


def test_конфликт_не_раскрывает_внутренние_детали(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Ответ о конфликте не содержит SQL и имён таблиц."""
    client.post("/items", json=book_payload)

    response = client.post("/items", json=book_payload)

    assert response.status_code == 409
    assert response.json()["error_type"] == "ConflictError"
    assert "INSERT" not in response.text
    assert "UNIQUE" not in response.text


# ---------------------------------------------------------------- SQL-инъекции


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1--",
        "' UNION SELECT 1,2,3,4,5,6,7,8--",
        "'; DROP TABLE books;--",
        "1' AND SLEEP(5)--",
    ],
)
def test_sql_инъекция_в_поиске_не_проходит(
    client: TestClient, book_payload: dict[str, object], payload: str
) -> None:
    """SQLAlchemy параметризует запросы, инъекция не выполняется."""
    client.post("/items", json=book_payload)

    response = client.get("/items", params={"search": payload})

    assert response.status_code == 200
    assert response.json() == []
    # Таблица на месте - DROP не выполнился.
    assert len(client.get("/items").json()) == 1


def test_кавычки_в_данных_сохраняются_как_есть(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Кавычки в названии не ломают сохранение и поиск."""
    client.post("/items", json={**book_payload, "title": "O'Reilly's Books"})

    response = client.get("/items", params={"search": "O'Reilly"})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "O'Reilly's Books"


# ---------------------------------------------------------------------- XSS


def test_ответ_отдаётся_как_json_а_не_как_html(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Внедрённый скрипт хранится как текст, а не как разметка."""
    client.post("/items", json={**book_payload, "title": "<script>alert(1)</script>"})

    response = client.get("/items")

    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json()[0]["title"] == "<script>alert(1)</script>"


def test_неизвестный_маршрут_не_отдаёт_страницу_с_внутренностями(
    client: TestClient,
) -> None:
    """404 не подставляет HTML-шаблон с отладочной информацией."""
    response = client.get("/nonexistent")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


# ------------------------------------------------------ незакрытые соединения


def test_сессии_базы_закрываются_после_каждого_запроса(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Много запросов подряд не оставляют открытых соединений."""
    from sqlalchemy import event

    from app.database import engine

    counters = {"checkout": 0, "checkin": 0}

    def on_checkout(*_: object) -> None:
        counters["checkout"] += 1

    def on_checkin(*_: object) -> None:
        counters["checkin"] += 1

    event.listen(engine, "checkout", on_checkout)
    event.listen(engine, "checkin", on_checkin)
    try:
        for _ in range(5):
            client.post("/items", json=book_payload)
            client.get("/items")
    finally:
        event.remove(engine, "checkout", on_checkout)
        event.remove(engine, "checkin", on_checkin)

    assert counters["checkout"] > 0
    assert counters["checkin"] == counters["checkout"]


def test_пул_соединений_не_исчерпывается(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """После серии запросов приложение продолжает отвечать."""
    for _ in range(30):
        client.get("/items")

    assert client.get("/items").status_code == 200


def test_в_исходном_коде_нет_сборки_sql_из_строк() -> None:
    """Ни в одном модуле не должно быть f-string и format в SQL."""
    pattern = re.compile(r"(text|execute)\s*\(\s*f[\"']")
    offenders: list[str] = []

    for directory in ("app",):
        for root, _, files in os.walk(os.path.join(REPO_ROOT, directory)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as source_file:
                    for line_number, line in enumerate(source_file, start=1):
                        if pattern.search(line):
                            offenders.append(f"{path}:{line_number}")

    assert offenders == []
