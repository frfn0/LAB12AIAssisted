"""Подключение к базе данных и фабрика сессий SQLAlchemy."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Базовый класс для всех моделей приложения."""


def _engine_kwargs(url: str) -> dict[str, object]:
    """Параметры движка, зависящие от типа базы.

    SQLite проверяет, что соединение используется из того же потока, в котором
    было открыто. FastAPI обрабатывает запросы в пуле потоков, поэтому для
    SQLite это ограничение нужно снять.

    Для базы в памяти дополнительно нужен StaticPool: по умолчанию SQLite
    создаёт новую пустую базу на каждое соединение, и данные из одной сессии
    были бы не видны другой. Такой режим используется в тестах.
    """
    if not url.startswith("sqlite"):
        return {}

    kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if url in {"sqlite", "sqlite+pysqlite://", "sqlite://", "sqlite:///:memory:"}:
        kwargs["poolclass"] = StaticPool

    return kwargs


def create_db_engine() -> Engine:
    """Создаёт движок SQLAlchemy по строке подключения из настроек."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.sql_echo,
        future=True,
        **_engine_kwargs(settings.database_url),
    )


engine: Engine = create_db_engine()


def _unicode_lower(value: str | None) -> str | None:
    """Версия SQL lower() с поддержкой Unicode."""
    return value.lower() if value is not None else None


@event.listens_for(engine, "connect")
def _register_sqlite_helpers(dbapi_connection: object, _: object) -> None:
    """Регистрирует в SQLite вспомогательную функцию lower().

    Встроенная lower() в SQLite меняет регистр только для символов ASCII,
    поэтому поиск по автору не находил «Булгакова» по запросу «булгаков».
    Функция на Python корректно работает с кириллицей и автоматически
    подхватывается конструкцией ilike().

    В PostgreSQL lower() уже работает с Unicode, поэтому вмешательство
    требуется только для SQLite.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("lower", 1, _unicode_lower)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """FastAPI-зависимость: отдаёт сессию базы и закрывает её после запроса."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет.

    Работает поверх метаданных моделей, поэтому важно, чтобы все модели
    были импортированы до вызова.
    """
    from app import models  # noqa: F401  - регистрация моделей в метаданных

    Base.metadata.create_all(bind=engine)
