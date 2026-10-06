"""Задание 9. Аналитические SQL-запросы по предметной области.

Запросы сформулированы на естественном языке, а затем превращены в SQL. Чтобы
один и тот же текст работал и на SQLite, и на PostgreSQL, порог по дате не
вычисляется функциями базы (они различаются: date('now', ...) против
NOW() - INTERVAL), а передаётся параметром :since.

Запуск:
    python scripts/demo_task9.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import Book, Loan, Reader  # noqa: E402

TODAY = date(2026, 10, 7)
SINCE = datetime(2026, 9, 7)  # последний месяц

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "results" / "task9.db"

# 100.0 * SUM(CASE ...) / COUNT(...) - доля просроченных возвратов в процентах.
OVERDUE_RETURNS = """
    SUM(CASE WHEN l.returned_at IS NOT NULL
              AND l.returned_at > l.due_at
             THEN 1 ELSE 0 END)
"""

REPORTS: list[dict[str, object]] = [
    {
        "title": "Отчёт 1. Топ-10 книг по числу выдач за последний месяц",
        "question": (
            "Какие книги выдавались чаще всего за последний месяц, сколько "
            "разных читателей их брало и какой средний штраф сопровождает "
            "выдачу?"
        ),
        "sql": """
SELECT
    b.title,
    b.author,
    b.genre,
    COUNT(l.id)                  AS issues_count,
    COUNT(DISTINCT l.reader_id)  AS readers_count,
    ROUND(CAST(AVG(l.fine) AS NUMERIC), 2) AS avg_fine
FROM loans l
JOIN books b ON b.id = l.book_id
WHERE l.issued_at >= :since
GROUP BY b.id, b.title, b.author, b.genre
ORDER BY issues_count DESC, b.title
LIMIT 10
""",
        "params": {"since": SINCE},
        "explanation": (
            "JOIN соединяет каждую выдачу с её книгой: без этого в отчёте "
            "были бы только идентификаторы.\n"
            "WHERE отсекает выдачи старше месяца, поэтому в подсчёт попадают "
            "только актуальные.\n"
            "COUNT(l.id) даёт число выдач, COUNT(DISTINCT l.reader_id) - "
            "число разных читателей. Это разные вещи: если книгу пять раз "
            "взял один человек, выдач пять, а читателей один.\n"
            "GROUP BY собирает строки по книге.\n"
            "ORDER BY сортирует по убыванию выдач, при равенстве - по "
            "названию, чтобы результат был воспроизводимым.\n"
            "LIMIT 10 отрезает хвост."
        ),
    },
    {
        "title": "Отчёт 2. Читатели с максимальной суммой штрафов",
        "question": (
            "Кто из читателей больше всего должен библиотеке и у скольких "
            "книг находятся сейчас?"
        ),
        "sql": """
SELECT
    r.full_name,
    r.email,
    COUNT(l.id)                                           AS loans_total,
    SUM(CASE WHEN l.returned_at IS NULL THEN 1 ELSE 0 END) AS active_loans,
    ROUND(CAST(SUM(l.fine) AS NUMERIC), 2)                  AS total_fine,
    ROUND(CAST(AVG(l.fine) AS NUMERIC), 2)                  AS avg_fine
FROM readers r
JOIN loans l ON l.reader_id = r.id
GROUP BY r.id, r.full_name, r.email
HAVING SUM(l.fine) > 0
ORDER BY total_fine DESC
LIMIT 10
""",
        "params": {},
        "explanation": (
            "CASE превращает проверку «книга сейчас выдана» в 1 или 0, чтобы "
            "посчитать такие выдачи через SUM.\n"
            "HAVING отсекает читателей с нулевым долгом. Фильтр стоит "
            "именно здесь, а не в WHERE: WHERE отсёк бы строки до "
            "группировки и сломал бы суммы - остались бы читатели без "
            "выдач вовсе.\n"
            "Сумма и среднее считаются раздельно: максимальный долг и "
            "типичный долг - разные показатели."
        ),
    },
    {
        "title": "Отчёт 3. Книги, которые чаще всего возвращают с просрочкой",
        "question": (
            "Какие книги чаще остаются у читателей дольше срока и какой "
            "процент возвратов это составляет?"
        ),
        "sql": f"""
SELECT
    b.title,
    b.author,
    COUNT(l.id)      AS returns_total,
    {OVERDUE_RETURNS} AS overdue_returns,
    ROUND(100.0 * {OVERDUE_RETURNS} / COUNT(l.id), 1) AS overdue_rate
FROM loans l
JOIN books b ON b.id = l.book_id
WHERE l.returned_at IS NOT NULL
GROUP BY b.id, b.title, b.author
HAVING COUNT(l.id) >= 2
ORDER BY overdue_rate DESC, returns_total DESC
LIMIT 10
""",
        "params": {},
        "explanation": (
            "WHERE отсекает невозвращённые книги: для них просрочка ещё "
            "растёт, и процент по незавершённым выдачам считать бессмысленно.\n"
            "CASE с двумя условиями определяет именно просроченный возврат: "
            "возврат состоялся и случился позже срока.\n"
            "100.0 перед делением превращает долю в проценты. Без "
            "умножения на 100.0 в SQLite и PostgreSQL выполнялось бы "
            "целочисленное деление и получились бы нули.\n"
            "HAVING COUNT(l.id) >= 2 убирает книги с единственным "
            "возвратом: процент по одной записи недостоверен.\n"
            "Выражение SUM(CASE...) повторяется дважды: SQL не умеет "
            "переиспользовать его без подзапроса, поэтому вынесено в "
            "переменную Python при генерации текста запроса."
        ),
    },
    {
        "title": "Отчёт 4. Популярность жанров и средняя нагрузка на книгу",
        "question": (
            "Какие жанры читают чаще и сколько выдач приходится на одну книгу в жанре?"
        ),
        "sql": """
SELECT
    b.genre,
    COUNT(l.id)          AS issues_count,
    COUNT(DISTINCT b.id) AS titles_count,
    ROUND(1.0 * COUNT(l.id) / COUNT(DISTINCT b.id), 2) AS issues_per_title
FROM loans l
JOIN books b ON b.id = l.book_id
GROUP BY b.genre
HAVING COUNT(l.id) > 0
ORDER BY issues_count DESC, b.genre
""",
        "params": {},
        "explanation": (
            "Сравниваются не только абсолютные числа, но и удельные: жанр "
            "с 50 выдачами из одной книги и жанр с 50 выдачами из десяти - "
            "это разные явления.\n"
            "COUNT(DISTINCT b.id) убирает повторы: иначе книга, выданная "
            "пять раз, учитывалась бы как пять разных книг и среднее "
            "на одну книгу завышалось бы.\n"
            "1.0 в делении снова защищает от целочисленного результата."
        ),
    },
]


def seed(session: Session) -> None:
    """Наполняет базу правдоподобными данными."""
    books = [
        Book(
            isbn="978-5-17-115205-5",
            title="Мастер и Маргарита",
            author="Булгаков М.А.",
            year=1967,
            genre="Художественная литература",
            total_copies=5,
            available_copies=2,
        ),
        Book(
            isbn="978-0-13-235088-4",
            title="Clean Code",
            author="Мартин Р.",
            year=2008,
            genre="Программирование",
            total_copies=4,
            available_copies=1,
        ),
        Book(
            isbn="978-5-01-000001-1",
            title="Дюна",
            author="Герберт Ф.",
            year=1965,
            genre="Фантастика",
            total_copies=6,
            available_copies=6,
        ),
        Book(
            isbn="978-0-19-283866-7",
            title="English Grammar in Use",
            author="Свободный Т.",
            year=2000,
            genre="Учебники",
            total_copies=10,
            available_copies=8,
        ),
        Book(
            isbn="978-5-17-090717-5",
            title="Анна Каренина",
            author="Толстой Л.Н.",
            year=1877,
            genre="Художественная литература",
            total_copies=7,
            available_copies=5,
        ),
    ]
    readers = [
        Reader(
            full_name="Иванов Иван",
            email="ivanov@example.com",
            phone="+7 900 000-00-01",
        ),
        Reader(
            full_name="Петрова Анна",
            email="petrova@example.com",
            phone="+7 900 000-00-02",
        ),
        Reader(full_name="Сидоров Пётр", email="sidorov@example.com", phone=None),
        Reader(
            full_name="Кузнецова Мария",
            email="kuznetsova@example.com",
            phone="+7 900 000-00-04",
        ),
    ]
    session.add_all(books)
    session.add_all(readers)
    session.flush()

    def issued(days_ago: int) -> datetime:
        return datetime(2026, 10, 7, 9, 0) - timedelta(days=days_ago)

    loans = [
        # Выдачи за последний месяц
        Loan(
            book_id=1,
            reader_id=1,
            issued_at=issued(3),
            due_at=issued(-11),
            returned_at=None,
            fine=18.0,
        ),
        Loan(
            book_id=1,
            reader_id=2,
            issued_at=issued(9),
            due_at=issued(-5),
            returned_at=issued(4),
            fine=9.0,
        ),
        Loan(
            book_id=1,
            reader_id=3,
            issued_at=issued(14),
            due_at=issued(0),
            returned_at=issued(1),
            fine=3.0,
        ),
        Loan(
            book_id=2,
            reader_id=2,
            issued_at=issued(5),
            due_at=issued(-9),
            returned_at=None,
            fine=10.5,
        ),
        Loan(
            book_id=2,
            reader_id=4,
            issued_at=issued(12),
            due_at=issued(-2),
            returned_at=issued(6),
            fine=21.0,
        ),
        Loan(
            book_id=3,
            reader_id=3,
            issued_at=issued(6),
            due_at=issued(-8),
            returned_at=None,
            fine=12.0,
        ),
        Loan(
            book_id=3,
            reader_id=1,
            issued_at=issued(20),
            due_at=issued(6),
            returned_at=issued(8),
            fine=0.0,
        ),
        Loan(
            book_id=3,
            reader_id=4,
            issued_at=issued(25),
            due_at=issued(11),
            returned_at=issued(15),
            fine=0.0,
        ),
        Loan(
            book_id=4,
            reader_id=1,
            issued_at=issued(2),
            due_at=issued(-12),
            returned_at=None,
            fine=6.0,
        ),
        Loan(
            book_id=4,
            reader_id=2,
            issued_at=issued(7),
            due_at=issued(-7),
            returned_at=issued(2),
            fine=7.5,
        ),
        Loan(
            book_id=4,
            reader_id=3,
            issued_at=issued(11),
            due_at=issued(-3),
            returned_at=issued(5),
            fine=13.5,
        ),
        Loan(
            book_id=5,
            reader_id=4,
            issued_at=issued(18),
            due_at=issued(4),
            returned_at=issued(10),
            fine=0.0,
        ),
        # Выдачи старше месяца: в отчёты за период попадать не должны
        Loan(
            book_id=1,
            reader_id=3,
            issued_at=issued(45),
            due_at=issued(31),
            returned_at=issued(33),
            fine=0.0,
        ),
        Loan(
            book_id=5,
            reader_id=2,
            issued_at=issued(60),
            due_at=issued(46),
            returned_at=issued(40),
            fine=15.0,
        ),
    ]
    session.add_all(loans)
    session.commit()


def print_table(columns: list[str], rows: list[tuple]) -> None:
    """Печатает результат запроса в читаемом виде."""
    widths = [
        max([len(str(column))] + [len(str(row[index])) for row in rows])
        for index, column in enumerate(columns)
    ]

    def render(values: list[str]) -> str:
        return " | ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        )

    print(render([str(column) for column in columns]))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(render([str(value) for value in row]))
    print()
    print(f"строк: {len(rows)}")
    print()


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()

    engine = create_engine(f"sqlite+pysqlite:///{DB_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed(session)

    print("=" * 78)
    print("Задание 9. Аналитические отчёты по системе управления библиотекой")
    print("=" * 78)
    print("Данные: 5 книг, 4 читателя, 14 выдач")
    print(f"Отчётный период: с {SINCE.date()} по {TODAY}")
    print()

    failures = 0
    with engine.connect() as connection:
        for report in REPORTS:
            print("-" * 78)
            print(report["title"])
            print("-" * 78)
            print(f"Вопрос: {report['question']}")
            print()
            print("SQL:")
            print(str(report["sql"]).strip())
            print()

            result = connection.execute(
                text(str(report["sql"])), dict(report["params"])
            )
            rows = [tuple(row) for row in result]
            columns = list(result.keys())
            if not rows:
                failures += 1
                print("ЗАПРОС НЕ ВЕРНУЛ СТРОК")
            print_table(columns, rows)
            print("Логика запроса:")
            print(report["explanation"])
            print()

    print("=" * 78)
    print(f"Отчётов выполнено: {len(REPORTS)}, без результата: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
