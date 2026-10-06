"""Тесты валидации ISBN из задания 10.

Покрываются оба слоя: регулярное выражение проверяет форму записи,
контрольная сумма - правильность цифр.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.isbn import (
    ISBN10_REGEX,
    ISBN13_REGEX,
    IsbnError,
    is_valid_format,
    isbn10_checksum,
    isbn10_checksum_value,
    isbn13_checksum,
    make_isbn10,
    make_isbn13,
    normalize,
    validate_isbn,
)

# Корректные номера построены функциями, а не выписаны вручную: ручная
# запись почти всегда даёт неверную контрольную цифру.
ISBN13_VALID = make_isbn13("978517115205")
ISBN10_WITH_X = make_isbn10("080442957")
ISBN10_NUMERIC = make_isbn10("517115205")


# ------------------------------------------------------------------ формат


def test_регулярные_выражения_скомпилированы() -> None:
    """Оба шаблона существуют и отличаются друг от друга."""
    assert ISBN10_REGEX.pattern
    assert ISBN13_REGEX.pattern
    assert ISBN10_REGEX.pattern != ISBN13_REGEX.pattern


@pytest.mark.parametrize(
    "value",
    [
        "978-5-17-115205-5",
        "9785171152055",
        "978 5 17 115205 5",
        "0-8044-2957-X",
        "080442957X",
        "5171152055",
        "979-5-17-115205-5",
    ],
)
def test_форма_корректная(value: str) -> None:
    """Регулярное выражение принимает обе формы: с дефисами и без."""
    assert is_valid_format(value)


@pytest.mark.parametrize(
    "value",
    ["123", "abc-def-ghij", "978517115205", "9775171152055", "08044295X0"],
)
def test_форма_некорректная(value: str) -> None:
    """Явно неверные записи отвергаются на уровне шаблона."""
    assert not is_valid_format(value)


def test_isbn13_обязан_начинаться_с_978_или_979() -> None:
    """Книжные номера не могут начинаться с 977."""
    assert ISBN13_REGEX.fullmatch("9785171152055")
    assert ISBN13_REGEX.fullmatch("9795171152055")
    assert not ISBN13_REGEX.fullmatch("9775171152055")
    assert not ISBN13_REGEX.fullmatch("977517115205")


def test_форма_верна_но_сумма_не_сходится() -> None:
    """Регулярное выражение пропускает опечатку в контрольной цифре."""
    wrong = ISBN13_VALID[:-1] + ("7" if ISBN13_VALID[-1] != "7" else "8")

    assert is_valid_format(wrong)
    with pytest.raises(IsbnError):
        validate_isbn(wrong)


# ------------------------------------------------------- контрольная сумма


def test_сумма_isbn13_вычисляется_верно() -> None:
    """Контрольная цифра ISBN-13 завершает построение номера."""
    assert isbn13_checksum("978517115205") == 5
    assert make_isbn13("978517115205") == "9785171152055"


def test_сумма_isbn10_может_быть_x() -> None:
    """Римская десятка обозначается буквой X и означает 10."""
    assert isbn10_checksum("080442957") == "X"
    assert isbn10_checksum_value("080442957") == 10
    assert ISBN10_WITH_X.endswith("X")


def test_сумма_isbn10_обычная_цифра() -> None:
    """Обычная контрольная цифра возвращается числом."""
    assert isbn10_checksum("517115205") == 5
    assert isbn10_checksum_value("517115205") == 5
    assert ISBN10_NUMERIC.endswith("5")


def test_make_isbn10_отвергает_не_цифры() -> None:
    """Построить ISBN-10 из не-цифр нельзя."""
    with pytest.raises(ValueError, match="только из цифр"):
        make_isbn10("08044295X")


def test_make_isbn_требует_верную_длину() -> None:
    """Префиксы фиксированной длины."""
    with pytest.raises(ValueError, match="12 цифр"):
        make_isbn13("97851711520")
    with pytest.raises(ValueError, match="9 цифр"):
        make_isbn10("08044295")


# ------------------------------------------------------------- полная проверка


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("978-5-17-115205-5", "9785171152055"),
        ("9785171152055", "9785171152055"),
        ("  978 5 17 115205 5  ", "9785171152055"),
        ("0-8044-2957-X", "080442957X"),
        ("080442957X", "080442957X"),
    ],
)
def test_валидные_значения_нормализуются(raw: str, expected: str) -> None:
    """Проверка проходит и возвращает номер без разделителей."""
    assert validate_isbn(raw) == expected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("978-5-17-115205-6", "контрольная цифра ISBN-13"),
        ("0804429571", "контрольная цифра ISBN-10"),
        ("978517115205", "10 или 13 символов"),
        ("123", "10 или 13 символов"),
        ("", "не должен быть пустым"),
        ("   ", "не должен быть пустым"),
    ],
)
def test_невалидные_значения_отвергаются(raw: str, message: str) -> None:
    """Каждая ошибка объяснена понятным сообщением."""
    with pytest.raises(IsbnError, match=message):
        validate_isbn(raw)


def test_каждая_опечатка_ловится() -> None:
    """Замена любой цифры в номере ломает контрольную сумму."""
    base = list(ISBN13_VALID)
    broken = 0
    for index in range(12):
        for replacement in "0123456789":
            if replacement == base[index]:
                continue
            candidate = list(base)
            candidate[index] = replacement
            with pytest.raises(IsbnError):
                validate_isbn("".join(candidate))
            broken += 1
    assert broken == 108


def test_нормализация_убирает_разделители() -> None:
    """Дефисы и пробелы не влияют на результат."""
    assert normalize("978-5-17-115205-5") == "9785171152055"
    assert normalize("978 5 17 115205 5") == "9785171152055"
    assert normalize("  080442957X  ") == "080442957X"


# --------------------------------------------------------------------- API


def test_api_отклоняет_неверный_isbn(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Книга с неверной контрольной цифрой не попадает в базу."""
    response = client.post(
        "/items", json={**book_payload, "isbn": f"{ISBN13_VALID[:-1]}-6"}
    )

    assert response.status_code == 422
    assert "контрольная цифра" in response.text


def test_api_нормализует_isbn(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """В базу сохраняется номер без дефисов."""
    response = client.post("/items", json={**book_payload, "isbn": "978-0-13-235088-4"})

    assert response.status_code == 201
    assert response.json()["isbn"] == "9780132350884"


def test_api_принимает_корректный_isbn(
    client: TestClient, book_payload: dict[str, object]
) -> None:
    """Книга с настоящим ISBN создаётся."""
    response = client.post("/items", json={**book_payload, "isbn": ISBN13_VALID})

    assert response.status_code == 201
