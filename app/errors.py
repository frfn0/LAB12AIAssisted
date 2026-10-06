"""Доменные исключения и их преобразование в ответы HTTP."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# Константа 422 названа числом: в разных версиях Starlette имя менялось
# (HTTP_422_UNPROCESSABLE_ENTITY -> HTTP_422_UNPROCESSABLE_CONTENT),
# а числовой код остаётся тем же.
HTTP_422_UNPROCESSABLE = 422


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


class UnauthorizedError(DomainError):
    """Не передан или передан неверный ключ доступа."""

    status_code = status.HTTP_401_UNAUTHORIZED


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
        """Нарушение уникальности или внешнего ключа возвращается как 409.

        Клиенту не отправляется текст SQL: он раскрывает структуру таблиц.
        Подробности остаются только в логе сервера.
        """
        logger.warning("нарушение целостности данных: %s", exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Нарушение целостности данных",
                "error_type": "IntegrityError",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Ошибки валидации возвращаются в сокращённом виде.

        Стандартный ответ Pydantic повторяет входные значения в каждой
        ошибке (например, переданный пароль), поэтому клиенту отправляются
        только поле, тип ошибки и сообщение.
        """
        details = [
            {
                "type": error["type"],
                "loc": list(error["loc"]),
                "msg": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE,
            content={"detail": details, "error_type": "ValidationError"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Непредвиденная ошибка не раскрывает деталей клиенту.

        Без этого обработчика FastAPI отдаёт текст исключения, который может
        содержать названия таблиц, столбцов и строки подключения.
        """
        logger.exception("непредвиденная ошибка при обработке %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Внутренняя ошибка сервера",
                "error_type": "InternalServerError",
            },
        )
