-- Проверка совместимости аналитических запросов задания 9 с PostgreSQL.
-- Файл выполняется через: docker compose exec -T db psql -U library -d library


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

INSERT INTO readers (id, full_name, email, phone) VALUES
(1, 'Иванов Иван', 'ivanov@example.com', '+7 900 000-00-01'), (2, 'Петрова Анна', 'petrova@example.com', '+7 900 000-00-02'), (3, 'Сидоров Пётр', 'sidorov@example.com', NULL), (4, 'Кузнецова Мария', 'kuznetsova@example.com', '+7 900 000-00-04');

INSERT INTO books (id, isbn, title, author, year, genre, total_copies, available_copies) VALUES
(1, '978-5-17-115205-6', 'Мастер и Маргарита', 'Булгаков М.А.', 1967, 'Художественная литература', 5, 2), (2, '978-0-13-235088-4', 'Clean Code', 'Мартин Р.', 2008, 'Программирование', 4, 1), (3, '978-5-01-000001-2', 'Дюна', 'Герберт Ф.', 1965, 'Фантастика', 6, 6), (4, '978-0-19-283866-6', 'English Grammar in Use', 'Свободный Т.', 2000, 'Учебники', 10, 8), (5, '978-5-17-090717-4', 'Анна Каренина', 'Толстой Л.Н.', 1877, 'Художественная литература', 7, 5);

INSERT INTO loans (book_id, reader_id, issued_at, due_at, returned_at, fine) VALUES
(1, 1, '2026-10-04 09:00:00'::timestamp, '2026-10-18 09:00:00'::timestamp, NULL, 18.0), (1, 2, '2026-09-28 09:00:00'::timestamp, '2026-10-12 09:00:00'::timestamp, '2026-10-03 09:00:00'::timestamp, 9.0), (1, 3, '2026-09-23 09:00:00'::timestamp, '2026-10-07 09:00:00'::timestamp, '2026-10-06 09:00:00'::timestamp, 3.0), (2, 2, '2026-10-02 09:00:00'::timestamp, '2026-10-16 09:00:00'::timestamp, NULL, 10.5), (2, 4, '2026-09-25 09:00:00'::timestamp, '2026-10-09 09:00:00'::timestamp, '2026-10-01 09:00:00'::timestamp, 21.0), (3, 3, '2026-10-01 09:00:00'::timestamp, '2026-10-15 09:00:00'::timestamp, NULL, 12.0), (3, 1, '2026-09-17 09:00:00'::timestamp, '2026-10-01 09:00:00'::timestamp, '2026-09-29 09:00:00'::timestamp, 0.0), (3, 4, '2026-09-12 09:00:00'::timestamp, '2026-09-26 09:00:00'::timestamp, '2026-09-22 09:00:00'::timestamp, 0.0), (4, 1, '2026-10-05 09:00:00'::timestamp, '2026-10-19 09:00:00'::timestamp, NULL, 6.0), (4, 2, '2026-09-30 09:00:00'::timestamp, '2026-10-14 09:00:00'::timestamp, '2026-10-05 09:00:00'::timestamp, 7.5), (4, 3, '2026-09-26 09:00:00'::timestamp, '2026-10-10 09:00:00'::timestamp, '2026-10-02 09:00:00'::timestamp, 13.5), (5, 4, '2026-09-19 09:00:00'::timestamp, '2026-10-03 09:00:00'::timestamp, '2026-09-27 09:00:00'::timestamp, 0.0), (1, 3, '2026-08-23 09:00:00'::timestamp, '2026-09-06 09:00:00'::timestamp, '2026-09-04 09:00:00'::timestamp, 0.0), (5, 2, '2026-08-08 09:00:00'::timestamp, '2026-08-22 09:00:00'::timestamp, '2026-08-28 09:00:00'::timestamp, 15.0);

\echo '=== Отчёт 1. Топ-10 книг по числу выдач за последний месяц ==='
SELECT
    b.title,
    b.author,
    b.genre,
    COUNT(l.id)                  AS issues_count,
    COUNT(DISTINCT l.reader_id)  AS readers_count,
    ROUND(CAST(AVG(l.fine) AS NUMERIC), 2) AS avg_fine
FROM loans l
JOIN books b ON b.id = l.book_id
WHERE l.issued_at >= '2026-09-07 00:00:00'::timestamp
GROUP BY b.id, b.title, b.author, b.genre
ORDER BY issues_count DESC, b.title
LIMIT 10;

\echo '=== Отчёт 2. Читатели с максимальной суммой штрафов ==='
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
LIMIT 10;

\echo '=== Отчёт 3. Книги, которые чаще всего возвращают с просрочкой ==='
SELECT
    b.title,
    b.author,
    COUNT(l.id)      AS returns_total,
    
    SUM(CASE WHEN l.returned_at IS NOT NULL
              AND l.returned_at > l.due_at
             THEN 1 ELSE 0 END)
 AS overdue_returns,
    ROUND(100.0 * 
    SUM(CASE WHEN l.returned_at IS NOT NULL
              AND l.returned_at > l.due_at
             THEN 1 ELSE 0 END)
 / COUNT(l.id), 1) AS overdue_rate
FROM loans l
JOIN books b ON b.id = l.book_id
WHERE l.returned_at IS NOT NULL
GROUP BY b.id, b.title, b.author
HAVING COUNT(l.id) >= 2
ORDER BY overdue_rate DESC, returns_total DESC
LIMIT 10;

\echo '=== Отчёт 4. Популярность жанров и средняя нагрузка на книгу ==='
SELECT
    b.genre,
    COUNT(l.id)          AS issues_count,
    COUNT(DISTINCT b.id) AS titles_count,
    ROUND(1.0 * COUNT(l.id) / COUNT(DISTINCT b.id), 2) AS issues_per_title
FROM loans l
JOIN books b ON b.id = l.book_id
GROUP BY b.genre
HAVING COUNT(l.id) > 0
ORDER BY issues_count DESC, b.genre;
