"""Доменные исключения и их преобразование в ответы HTTP."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Базовая ошибка предметной области."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """Запрошенная запись не найдена."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """Запись уже существует."""

    status_code = status.HTTP_409_CONFLICT


class BusinessRuleError(DomainError):
    """Действие нарушает бизнес-правило."""

    status_code = status.HTTP_409_CONFLICT


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует обработчики ошибок приложения."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        """Единый формат ответа для ошибок предметной области."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_type": type(exc).__name__},
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        """Нарушение уникальности или внешнего ключа возвращается как 409."""
        logger.warning("нарушение целостности данных: %s", exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Нарушение целостности данных",
                "error_type": "IntegrityError",
            },
        )
