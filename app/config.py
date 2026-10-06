"""Настройки приложения из переменных окружения и файла .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация системы управления библиотекой."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Система управления библиотекой"
    app_version: str = "1.0.0"

    # Подключение к базе. По умолчанию - локальный файл SQLite,
    # чтобы приложение запускалось без внешних сервисов.
    database_url: str = "sqlite+pysqlite:///./library.db"
    sql_echo: bool = False

    # Бизнес-правила предметной области.
    loan_days: int = 14
    fine_per_day: float = 1.50

    # Ключ доступа к изменяющим эндпоинтам. Пустое значение означает,
    # что проверка выключена - это режим разработки. В контейнере
    # ключ задаётся переменной окружения.
    api_key: str = ""

    @property
    def api_key_required(self) -> bool:
        """Включена ли проверка ключа доступа."""
        return bool(self.api_key)


@lru_cache
def get_settings() -> Settings:
    """Возвращает настройки, создавая объект только один раз."""
    return Settings()
