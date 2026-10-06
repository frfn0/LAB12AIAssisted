"""Готовит SQL-файл для проверки запросов задания 9 на PostgreSQL.

Схема и данные создаются обычным SQL, поэтому файл можно передать в psql
внутри контейнера и убедиться, что аналитические запросы совместимы
с PostgreSQL, а не только с SQLite.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo_task9 import REPORTS, SINCE  # noqa: E402

OUT_PATH = (
    Path(__file__).resolve().parent.parent / "results" / "task9_postgres_check.sql"
)

SCHEMA = """
DROP TABLE IF EXISTS loans, books, readers CASCADE;

CREATE TABLE readers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(32),
    registered_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(17) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    genre VARCHAR(64) NOT NULL,
    total_copies INTEGER NOT NULL,
    available_copies INTEGER NOT NULL,
    CONSTRAINT ck_books_total_non_negative CHECK (total_copies >= 0)
);

CREATE TABLE loans (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    reader_id INTEGER NOT NULL REFERENCES readers(id) ON DELETE CASCADE,
    issued_at TIMESTAMP NOT NULL,
    due_at TIMESTAMP NOT NULL,
    returned_at TIMESTAMP,
    fine DOUBLE PRECISION NOT NULL DEFAULT 0,
    notes TEXT
);
"""

READERS = [
    ("Иванов Иван", "ivanov@example.com", "+7 900 000-00-01"),
    ("Петрова Анна", "petrova@example.com", "+7 900 000-00-02"),
    ("Сидоров Пётр", "sidorov@example.com", None),
    ("Кузнецова Мария", "kuznetsova@example.com", "+7 900 000-00-04"),
]

BOOKS = [
    (
        "978-5-17-115205-6",
        "Мастер и Маргарита",
        "Булгаков М.А.",
        1967,
        "Художественная литература",
        5,
        2,
    ),
    ("978-0-13-235088-4", "Clean Code", "Мартин Р.", 2008, "Программирование", 4, 1),
    ("978-5-01-000001-2", "Дюна", "Герберт Ф.", 1965, "Фантастика", 6, 6),
    (
        "978-0-19-283866-6",
        "English Grammar in Use",
        "Свободный Т.",
        2000,
        "Учебники",
        10,
        8,
    ),
    (
        "978-5-17-090717-4",
        "Анна Каренина",
        "Толстой Л.Н.",
        1877,
        "Художественная литература",
        7,
        5,
    ),
]

# (book_id, reader_id, issued_days_ago, due_days_ago, returned_days_ago_or_None, fine)
LOANS = [
    (1, 1, 3, -11, None, 18.0),
    (1, 2, 9, -5, 4, 9.0),
    (1, 3, 14, 0, 1, 3.0),
    (2, 2, 5, -9, None, 10.5),
    (2, 4, 12, -2, 6, 21.0),
    (3, 3, 6, -8, None, 12.0),
    (3, 1, 20, 6, 8, 0.0),
    (3, 4, 25, 11, 15, 0.0),
    (4, 1, 2, -12, None, 6.0),
    (4, 2, 7, -7, 2, 7.5),
    (4, 3, 11, -3, 5, 13.5),
    (5, 4, 18, 4, 10, 0.0),
    (1, 3, 45, 31, 33, 0.0),
    (5, 2, 60, 46, 40, 15.0),
]


def sql_string(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def timestamp(days_ago: int) -> str:
    return (datetime(2026, 10, 7, 9, 0) - timedelta(days=days_ago)).isoformat(sep=" ")


def build() -> str:
    parts = [
        "-- Проверка совместимости аналитических запросов задания 9 с PostgreSQL.",
        "-- Файл выполняется через: docker compose exec -T db psql -U library -d library",
        "",
        SCHEMA,
        "INSERT INTO readers (id, full_name, email, phone) VALUES",
    ]
    values = ", ".join(
        f"({index + 1}, {sql_string(name)}, {sql_string(email)}, {sql_string(phone)})"
        for index, (name, email, phone) in enumerate(READERS)
    )
    parts.append(values + ";")

    parts.append("")
    parts.append(
        "INSERT INTO books (id, isbn, title, author, year, genre, "
        "total_copies, available_copies) VALUES"
    )
    values = ", ".join(
        f"({index + 1}, {sql_string(isbn)}, {sql_string(title)}, {sql_string(author)}, "
        f"{year}, {sql_string(genre)}, {total}, {available})"
        for index, (isbn, title, author, year, genre, total, available) in enumerate(
            BOOKS
        )
    )
    parts.append(values + ";")

    parts.append("")
    parts.append(
        "INSERT INTO loans (book_id, reader_id, issued_at, due_at, "
        "returned_at, fine) VALUES"
    )
    values = ", ".join(
        f"({book}, {reader}, '{timestamp(issued)}'::timestamp, "
        f"'{timestamp(due)}'::timestamp, "
        + ("NULL" if returned is None else f"'{timestamp(returned)}'::timestamp")
        + f", {fine})"
        for book, reader, issued, due, returned, fine in LOANS
    )
    parts.append(values + ";")

    since = SINCE.isoformat(sep=" ")
    for report in REPORTS:
        sql = str(report["sql"]).strip()
        if report["params"]:
            sql = sql.replace(":since", f"'{since}'::timestamp")
        parts.append("")
        parts.append("\\echo '=== " + str(report["title"]) + " ==='")
        parts.append(sql.rstrip(";") + ";")

    return "\n".join(parts) + "\n"


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = build()
    OUT_PATH.write_text(content, encoding="utf-8")
    print(f"SQL-файл записан: {OUT_PATH}")
    print(f"строк: {len(content.splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
