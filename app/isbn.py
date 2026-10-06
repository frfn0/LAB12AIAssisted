"""Валидация ISBN: формат и контрольная сумма.

Регулярное выражение способно проверить только форму записи. Правильность
самой цифры проверяет контрольная сумма, поэтому полноценная проверка
состоит из двух шагов:

1. формат - регулярное выражение, допускает дефисы;
2. контрольная сумма - арифметика по алгоритму модуля 11 (ISBN-10)
   или модуля 10 с чередованием весов (ISBN-13).

Проверка только формата без суммы пропускала бы опечатки в цифрах, поэтому
в схемах используется полная проверка.
"""

from __future__ import annotations

import re

# ISBN-10: девять цифр и контрольная цифра, которая может быть X (римская
# десятка). Принимаются две формы: с дефисами (0-8044-2957-X) и без них
# (080442957X).
ISBN10_PATTERN = r"^(?:\d{1,5}-(?:\d{1,7}-)?(?:\d{1,6}-)?[\dX]|\d{9}[\dX])$"

# ISBN-13: тринадцать цифр, начинается с 978 или 979. Дефисы допустимы
# в любом месте после префикса. Пример: 978-5-17-115205-5
ISBN13_PATTERN = r"^(?:978|979)(?:-?\d){10}$"

ISBN10_REGEX = re.compile(ISBN10_PATTERN)
ISBN13_REGEX = re.compile(ISBN13_PATTERN)

SEPARATORS = re.compile(r"[\s-]+")

# Значение контрольной цифры X в числовом виде: X означает 10.
ISBN10_CHECK_X_VALUE = 10


class IsbnError(ValueError):
    """ISBN не прошёл проверку."""


def normalize(isbn: str) -> str:
    """Убирает дефисы и пробелы, оставляя только цифры и X.

    Raises:
        IsbnError: если после очистки не осталось ничего.
    """
    cleaned = SEPARATORS.sub("", isbn).strip().upper()
    if not cleaned:
        raise IsbnError("ISBN не должен быть пустым")
    return cleaned


def isbn10_checksum(digits: str) -> int | str:
    """Контрольная цифра ISBN-10 по алгоритму модуля 11.

    Сумма цифр с весами от 10 до 2 должна делиться на 11. Если остаток
    равен 1, контрольная цифра - X (римская десятка).

    Returns:
        int или "X": вычисленная контрольная цифра.
    """
    total = sum((10 - index) * int(digit) for index, digit in enumerate(digits))
    remainder = total % 11
    if remainder == 0:
        return 0
    if remainder == 1:
        return "X"
    return 11 - remainder


def isbn10_checksum_value(digits: str) -> int:
    """Контрольная цифра ISBN-10 приведённая к числу: X - это 10."""
    check = isbn10_checksum(digits)
    return ISBN10_CHECK_X_VALUE if check == "X" else int(check)


def isbn13_checksum(digits: str) -> int:
    """Контрольная цифра ISBN-13.

    Сумма первых двенадцати цифр с чередующимися весами 1 и 3, результат
    округляется вверх до ближайшего десятка.
    """
    total = sum(
        int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(digits)
    )
    return (10 - total % 10) % 10


def is_valid_format(isbn: str) -> bool:
    """Проверяет только форму записи, без контрольной суммы.

    Шаблоны применяются и к исходной строке, и к нормализованной: иначе
    номер без дефисов отвергался бы, хотя запись корректна.
    """
    if ISBN10_REGEX.fullmatch(isbn) or ISBN13_REGEX.fullmatch(isbn):
        return True
    try:
        compact = normalize(isbn)
    except IsbnError:
        return False
    return bool(ISBN10_REGEX.fullmatch(compact) or ISBN13_REGEX.fullmatch(compact))


def validate_isbn(isbn: str) -> str:
    """Проверяет ISBN и возвращает его в нормализованном виде.

    Raises:
        IsbnError: если формат неверный или не сходится контрольная сумма.
    """
    candidate = normalize(isbn)

    if len(candidate) == 10:
        if not re.fullmatch(r"\d{9}[\dX]", candidate):
            raise IsbnError(
                f"ISBN-10 должен содержать девять цифр и контрольную цифру: {isbn!r}"
            )
        actual = candidate[9]
        actual_value = ISBN10_CHECK_X_VALUE if actual == "X" else int(actual)
        if actual_value != isbn10_checksum_value(candidate[:9]):
            raise IsbnError(f"неверная контрольная цифра ISBN-10 в {isbn!r}")
        return candidate

    if len(candidate) == 13:
        if not re.fullmatch(r"\d{13}", candidate):
            raise IsbnError(f"ISBN-13 должен содержать тринадцать цифр: {isbn!r}")
        if int(candidate[12]) != isbn13_checksum(candidate[:12]):
            raise IsbnError(f"неверная контрольная цифра ISBN-13 в {isbn!r}")
        return candidate

    raise IsbnError(
        f"ISBN должен содержать 10 или 13 символов, получено {len(candidate)}: {isbn!r}"
    )


def make_isbn13(prefix_digits: str) -> str:
    """Собирает корректный ISBN-13 из первых двенадцати цифр.

    Нужен, чтобы в тестах и демонстрации не выписывать ISBN вручную.

    Raises:
        ValueError: если цифр не двенадцать.
    """
    if len(prefix_digits) != 12:
        raise ValueError("нужно ровно 12 цифр")
    return prefix_digits + str(isbn13_checksum(prefix_digits))


def make_isbn10(prefix_digits: str) -> str:
    """Собирает корректный ISBN-10 из первых девяти цифр.

    Raises:
        ValueError: если цифр не девять или они не десятичные.
    """
    if len(prefix_digits) != 9:
        raise ValueError("нужно ровно 9 цифр")
    if not prefix_digits.isdigit():
        raise ValueError("ISBN-10 строится только из цифр")
    check = isbn10_checksum(prefix_digits)
    return prefix_digits + (check if isinstance(check, str) else str(check))
