"""Промежуточное ПО для заголовков безопасности.

uvicorn сам по себе не выставляет защитные заголовки, поэтому добавляем их
здесь. Набор соответствует тому, что перечислено в задании о поиске
уязвимостей: защита от подмены MIME-типа, от встраивания в iframe и от
кэширования ответов API.

Заголовок Server: uvicorn удалить отсюда нельзя: uvicorn добавляет его на
уровне транспорта уже после того, как приложение вернуло ответ. Поэтому он
отключается флагом запуска --no-server-header, см. Dockerfile и README.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

SECURITY_HEADERS = {
    # Браузер не будет угадывать MIME-тип ответа.
    "X-Content-Type-Options": "nosniff",
    # Страницу нельзя встроить в iframe (защита от кликджекинга).
    "X-Frame-Options": "DENY",
    # Запрет кэширования ответов API.
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    # Не передавать полный адрес страницы в заголовке Referer.
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Добавляет заголовки безопасности к каждому ответу."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        return response
