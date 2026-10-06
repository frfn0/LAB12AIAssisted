"""ШТРАФЫ ЗА ПРОСРОЧКУ - ВЕРСИЯ ДО РЕФАКТОРИНГА.

Этот модуль оставлен намеренно. Здесь собраны все проблемы, которые
перечислены в задании 3 методички:

1. длина функции больше 30 строк - вся логика в одной функции;
2. магические числа - 1.50, 30, 1.5, 500, 5, 0.9 без объяснения;
3. отсутствие обработки ошибок - неизвестная категория читателя приводит
   к KeyError, отсутствие ключа - к KeyError, пустой список - к TypeError;
4. неинформативные имена переменных - l, d, dd, f, x, r, i;
5. дублирование кода - фильтрация выдач читателя повторяется дважды,
   вычисление просрочки не вынесено в отдельную функцию.

Рабочая версия находится в app/services/fines.py. Поведение обеих версий
совпадает, что проверяется тестами в tests/test_fines.py.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def calculate_reader_fine(
    reader: dict[str, Any],
    loans: list[dict[str, Any]],
    today: date,
) -> Decimal:
    """Считает штраф читателя по всем его просроченным выдачам.

    reader - словарь с ключами id, category;
    loans  - список выдач с ключами reader_id, due_at, returned_at;
    today  - дата, на которую считаем штраф.

    Возвращает итоговый штраф, округлённый до копеек.
    """
    total = Decimal("0")

    # ставка зависит от категории читателя
    if reader["category"] == "student":
        k = Decimal("1.0")
    elif reader["category"] == "regular":
        k = Decimal("1.5")
    else:
        # обработки ошибки нет: неизвестная категория роняет приложение
        k = CATEGORY_RATES[reader["category"]]

    # Имена l, k, d, dd, f, x, i оставлены плохими намеренно: это одна из
    # проблем, которые перечислены в задании. Линтер отключён для этой
    # строки, чтобы плохое имя было видно, но не ломало проверку стиля.
    for l in loans:  # noqa: E741
        if l["reader_id"] != reader["id"]:
            continue

        # повторяющаяся логика вычисления просрочки
        if l["returned_at"] is None:
            r = today
        else:
            r = l["returned_at"].date()

        due = l["due_at"].date()
        if r > due:
            dd = (r - due).days
        else:
            dd = 0

        if dd == 0:
            continue

        f = Decimal(str(dd)) * Decimal("1.50") * k

        if dd > 30:
            f = f * Decimal("1.5")

        if f > Decimal("500"):
            f = Decimal("500")

        total = total + f

    # второй проход по тем же выдачам - дублирование фильтрации
    x = 0
    for i in loans:
        if i["reader_id"] != reader["id"]:
            continue
        if i["returned_at"] is not None:
            if i["returned_at"].date() <= i["due_at"].date():
                x = x + 1

    if x >= 5:
        total = total * Decimal("0.9")

    return total.quantize(Decimal("0.01"))


# Словарь используется только в ветке "else", где категория неизвестна.
CATEGORY_RATES: dict[str, Decimal] = {
    "staff": Decimal("0.5"),
}


def format_fine(amount: Decimal) -> str:
    """Форматирует штраф для вывода клиенту."""
    if amount == 0:
        return "Штраф отсутствует"
    return "Штраф: " + str(amount) + " руб."


def loan_overdue_days(loan: dict[str, Any], today: date) -> int:
    """Считает просрочку по одной выдаче.

    Дублирует логику из calculate_reader_fine - ещё один пример
    дублирования кода в исходной версии.
    """
    if loan["returned_at"] is None:
        d = today
    else:
        d = loan["returned_at"].date()

    if d > loan["due_at"].date():
        return (d - loan["due_at"].date()).days
    return 0


def as_date(value: datetime | date) -> date:
    """Приводит значение к дате."""
    if isinstance(value, datetime):
        return value.date()
    return value
