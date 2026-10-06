# Сборка и запуск приложения в контейнере.
#
# Образ намеренно не содержит исходников тестов и результатов прогонов:
# в контейнере нужен только рабочий код и зависимости.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Зависимости копируются отдельным слоем, чтобы при изменении кода
# пересобирался только последний слой.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY .env.example ./.env

# Приложение слушает на всех интерфейсах: внутри контейнера localhost
# недоступен снаружи.
EXPOSE 8000

# --no-server-header убирает заголовок Server: uvicorn. На уровне
# приложения его удалить нельзя, uvicorn добавляет его после возврата
# ответа. Миграции применяются до запуска сервера, чтобы база была готова.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-server-header"]