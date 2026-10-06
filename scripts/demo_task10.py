"""Задание 10. Регулярное выражение для ISBN и скрипт его проверки.

Показывает, почему одного регулярного выражения мало: формат записи
проверяется шаблоном, а правильность цифр - контрольной суммой.

Корректные номера в примерах не выписаны вручную, а построены функциями
make_isbn10 и make_isbn13 - иначе很容易 ошибиться в контрольной цифре,
что и случилось при первой попытке.

Запуск:
    python scripts/demo_task10.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.isbn import (  # noqa: E402
    ISBN10_PATTERN,
    ISBN13_PATTERN,
    IsbnError,
    is_valid_format,
    make_isbn10,
    make_isbn13,
    normalize,
    validate_isbn,
)

# Корректные номера строятся функциями, а не выписываются вручную
_ISBN13 = make_isbn13("978517115205")
_ISBN13_SHORT = make_isbn13("978517090717")
_ISBN10 = make_isbn10("080442957")
_ISBN10_NUMERIC = make_isbn10("517115205")

VALID_EXAMPLES = [
    (f"978-5-17-115205-{_ISBN13[-1]}", "ISBN-13 с дефисами"),
    (_ISBN13, "ISBN-13 без дефисов"),
    (f"978 5 17 115205 {_ISBN13[-1]}", "ISBN-13 с пробелами вместо дефисов"),
    ("978-0-13-235088-4", "Clean Code"),
    (_ISBN10, f"десятизначный номер, контрольная цифра {_ISBN10[-1]}"),
    ("0-8044-2957-X", "тот же номер с дефисами"),
    (_ISBN10_NUMERIC, "десятизначный ISBN без префикса 978"),
    (_ISBN13_SHORT, "ещё один ISBN-13"),
]

INVALID_EXAMPLES = [
    (
        f"978-5-17-115205-{'6' if _ISBN13[-1] != '6' else '7'}",
        "верная форма, неверная контрольная цифра",
    ),
    (
        _ISBN10[:9] + ("1" if _ISBN10[-1] != "1" else "2"),
        "неверная контрольная цифра ISBN-10",
    ),
    (_ISBN13[:-1], "только двенадцать цифр"),
    ("123", "слишком короткий"),
    (_ISBN13 + "5", "лишняя цифра"),
    ("977" + _ISBN13[3:], "ISBN-13 не может начинаться с 977"),
    ("08044295X0", "X стоит не на последнем месте"),
    ("978-5-17-115205-X", "X недопустим в ISBN-13"),
    ("abc-def-ghij", "буквы вместо цифр"),
    ("", "пустая строка"),
]


def check(value: str) -> tuple[str, str]:
    """Возвращает результаты проверки формата и полной проверки."""
    try:
        fmt = "да" if is_valid_format(value) else "нет"
    except IsbnError:
        fmt = "ошибка"
    try:
        validate_isbn(value)
        full = "да"
    except IsbnError:
        full = "нет"
    return fmt, full


def print_table(title: str, rows: list[tuple[str, str]]) -> None:
    """Печатает таблицу результатов."""
    print(title)
    print("-" * 88)
    print(f"{'значение':22} {'регулярное':13} {'полная':10} примечание")
    print("-" * 88)
    for value, note in rows:
        shown = value if value else "(пусто)"
        fmt, full = check(value)
        print(f"{shown:22} {fmt:13} {full:10} {note}")
    print()


def main() -> int:
    print("=" * 88)
    print("Задание 10. Валидация ISBN: регулярное выражение и контрольная сумма")
    print("=" * 88)
    print()
    print("Регулярное выражение проверяет форму записи:")
    print(f"  ISBN-10  {ISBN10_PATTERN}")
    print(f"  ISBN-13  {ISBN13_PATTERN}")
    print()
    print("Регулярное выражение не способно проверить правильность цифр.")
    print("Пример: форма записи верная, а контрольная сумма нет -")
    print(f"  {_ISBN13[:-1]}-6  форма подходит, сумма не сходится")
    print()

    print_table("Валидные примеры:", VALID_EXAMPLES)
    print_table("Невалидные примеры:", INVALID_EXAMPLES)

    print("Разбор невалидных случаев")
    print("-" * 88)
    for value, _ in INVALID_EXAMPLES:
        try:
            validate_isbn(value)
            print(f"  {(value or '(пусто)'):22} неожиданно прошёл проверку")
        except IsbnError as exc:
            print(f"  {(value or '(пусто)'):22} {exc}")
    print()

    print("Проверка через API")
    print("-" * 88)
    wrong = f"978-5-17-115205-{_ISBN13[-1] if _ISBN13[-1] != '6' else '7'}"
    try:
        validate_isbn(wrong)
        print(f"  isbn={wrong} прошёл бы проверку")
    except IsbnError as exc:
        print(f"  POST /items с isbn={wrong} -> 422")
        print(f"  {exc}")
    print()

    print("Как получить корректный ISBN")
    print("-" * 88)
    for prefix in ("978517115205", "978517090717", "978501000001", "978019283866"):
        print(f"  {prefix} -> {make_isbn13(prefix)}")
    print(f"  080442957 -> {make_isbn10('080442957')}")
    print()
    print("  Контрольная цифра не выбирается произвольно, а вычисляется,")
    print("  поэтому номера в тестах и демонстрации строятся функциями.")
    print()

    print("Нормализация")
    print("-" * 88)
    for raw in (
        f"978-5-17-115205-{_ISBN13[-1]}",
        f"  978 5 17 115205 {_ISBN13[-1]}  ",
        _ISBN13,
    ):
        print(f"  {raw!r:26} -> {normalize(raw)!r}")
    print()

    errors = 0
    for value, _ in VALID_EXAMPLES:
        try:
            validate_isbn(value)
        except IsbnError:
            errors += 1
    for value, _ in INVALID_EXAMPLES:
        try:
            validate_isbn(value)
            errors += 1
        except IsbnError:
            pass

    print("=" * 88)
    print(f"Примеров: {len(VALID_EXAMPLES) + len(INVALID_EXAMPLES)}, ошибок: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
