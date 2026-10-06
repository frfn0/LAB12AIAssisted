"""Тесты служебных эндпоинтов и обработки ошибок."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings


def test_проверка_состояния(client: TestClient) -> None:
    """GET /health отвечает статусом ok и версией приложения."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "Система управления библиотекой"
    assert body["version"] == "1.0.0"


def _test_client_with_extra_routes() -> TestClient:
    """Клиент с маршрутом, возвращающим ошибку предметной области."""
    from fastapi import APIRouter

    from app.database import Base, engine
    from app.errors import BusinessRuleError, NotFoundError, register_exception_handlers
    from app.main import create_app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    application = create_app()
    router: APIRouter = APIRouter()

    @router.get("/_test/not-found")
    def not_found() -> None:
        raise NotFoundError("Запись не найдена")

    @router.get("/_test/rule")
    def rule() -> None:
        raise BusinessRuleError("Нарушено бизнес-правило")

    application.include_router(router)
    register_exception_handlers(application)

    return TestClient(application)


def test_доменная_ошибка_превращается_в_404() -> None:
    """NotFoundError возвращается клиенту как 404 с типом ошибки."""
    with _test_client_with_extra_routes() as client:
        response = client.get("/_test/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Запись не найдена",
        "error_type": "NotFoundError",
    }


def test_бизнес_правило_возвращает_409() -> None:
    """Нарушение бизнес-правила возвращается как 409."""
    with _test_client_with_extra_routes() as client:
        response = client.get("/_test/rule")

    assert response.status_code == 409
    assert response.json()["error_type"] == "BusinessRuleError"


def test_настройки_читаются_из_окружения(monkeypatch) -> None:
    """Переменные окружения переопределяют значения по умолчанию."""
    monkeypatch.setenv("LOAN_DAYS", "21")
    monkeypatch.setenv("FINE_PER_DAY", "2.75")

    settings = Settings()

    assert settings.loan_days == 21
    assert settings.fine_per_day == 2.75


def test_бизнес_правила_по_умолчанию() -> None:
    """Значения по умолчанию соответствуют правилам предметной области."""
    settings = Settings(_env_file=None)

    assert settings.loan_days == 14
    assert settings.fine_per_day == 1.50


def test_спецификация_openapi_содержит_все_эндпоинты(client: TestClient) -> None:
    """Спецификация описывает все пять операций CRUD."""
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/items"]) == {"get", "post"}
    assert set(paths["/items/{item_id}"]) == {"get", "put", "delete"}
