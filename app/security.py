"""Проверка ключа доступа для изменяющих эндпоинтов.

В задании о поиске уязвимостей среди прочего перечислены незащищённые
эндпоинты. Здесь реализована простая защита: если в настройках задан
API_KEY, то запросы на изменение данных должны содержать заголовок
X-API-Key с верным значением.

Если API_KEY не задан, проверка выключена - это удобно для локальной
разработки и для запуска лабораторной работы.
"""

from __future__ import annotations

import secrets

from fastapi import Header

from app.config import get_settings
from app.errors import UnauthorizedError

API_KEY_HEADER = "X-API-Key"


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI-зависимость: проверяет заголовок X-API-Key.

    Raises:
        UnauthorizedError: если ключ задан в настройках, но не передан
            или передан неверно.
    """
    settings = get_settings()
    if not settings.api_key_required:
        return

    # Сравнение постоянного времени: обычное == завершается сразу, как только
    # найдено несовпадение, и по времени ответа можно подбирать ключ
    # посимвольно. secrets.compare_digest такого не позволяет.
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise UnauthorizedError("Не передан или неверный ключ доступа")
