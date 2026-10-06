"""Точка входа приложения FastAPI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.items import router as items_router
from app.config import get_settings
from app.database import init_db
from app.errors import register_exception_handlers
from app.models import today
from app.schemas import HealthResponse

DESCRIPTION = """
Система управления библиотекой.

Книги, читатели, выдача и возврат, штрафы за просрочку и поиск по фонду.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Создаёт таблицы при старте приложения."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Собирает приложение FastAPI со всеми маршрутами."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    register_exception_handlers(application)
    application.include_router(items_router, prefix="/items", tags=["Книги"])

    @application.get("/health", response_model=HealthResponse, tags=["Служебные"])
    def health() -> HealthResponse:
        """Проверка состояния сервиса."""
        return HealthResponse(
            status="ok",
            app_name=settings.app_name,
            version=settings.app_version,
            today=today(),
        )

    return application


app = create_app()
