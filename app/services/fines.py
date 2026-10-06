"""Штрафы за просрочку - рабочая версия.

Расчёт разбит на небольшие функции с одной ответственностью, все числа
вынесены в именованные настройки, а ошибки обрабатываются явно.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

MONEY_QUANTUM = Decimal("0.01")

# Исходная версия округляла итог режимом Decimal по умолчанию, то есть
# ROUND_HALF_EVEN («половина к чётному», или банковское округление).
# Рефакторинг не должен менять behaviour, поэтому режим сохранён.
# ROUND_HALF_UP дал бы другой результат: 104.625 округлился бы в 104.63,
# а здесь и в исходной версии получается 104.62.
MONEY_ROUNDING = ROUND_HALF_EVEN


class FineCalculationError(Exception):
    """Некорректные данные для расчёта штрафа."""


class UnknownCategoryError(FineCalculationError):
    """Категория читателя не известна системе."""


@dataclass(frozen=True)
class FineRules:
    """Правила расчёта штрафа.

    Раньше эти значения были зашиты в код как магические числа, и непонятно
    было, что означает 1.5 и почему штраф ограничен 500.
    """

    daily_rate: Decimal = Decimal("1.50")
    grace_days: int = 30
    long_overdue_multiplier: Decimal = Decimal("1.5")
    max_fine: Decimal = Decimal("500")
    discount_threshold: int = 5
    discount_percent: Decimal = Decimal("0.9")

    def category_multiplier(self, category: str) -> Decimal:
        """Коэффициент ставки в зависимости от категории читателя.

        Raises:
            UnknownCategoryError: если категория не поддерживается.
        """
        multipliers = {
            "student": Decimal("1.0"),
            "regular": Decimal("1.5"),
            "staff": Decimal("0.5"),
        }
        if category not in multipliers:
            raise UnknownCategoryError(f"Неизвестная категория читателя: {category!r}")
        return multipliers[category]


DEFAULT_RULES = FineRules()


@dataclass(frozen=True)
class LoanFine:
    """Результат расчёта по одной выдаче."""

    loan_id: int
    overdue_days: int
    amount: Decimal
    was_capped: bool

    @property
    def amount_display(self) -> Decimal:
        """Сумма, округлённая до копеек. Только для показа.

        Само значение amount намеренно остаётся неокруглённым, чтобы
        итог совпадал с исходной версией: округлять каждую выдачу до
        суммирования - это уже изменение поведения.
        """
        return quantize_money(self.amount)


@dataclass(frozen=True)
class FineSummary:
    """Итог по читателю."""

    reader_id: int
    total: Decimal
    loans: tuple[LoanFine, ...]

    def as_dict(self) -> dict[str, object]:
        """Плоское представление для ответа API и отчётов."""
        return {
            "reader_id": self.reader_id,
            "total": str(self.total),
            "loans": [
                {
                    "loan_id": fine.loan_id,
                    "overdue_days": fine.overdue_days,
                    "amount": str(fine.amount_display),
                    "was_capped": fine.was_capped,
                }
                for fine in self.loans
            ],
        }


def _reference_date(loan: dict[str, Any], today: date) -> date:
    """Дата, на которую считается просрочка выдачи.

    Для невозвращённой книги это сегодняшняя дата, для возвращённой - дата
    возврата: после возврата просрочка перестаёт расти.
    """
    returned_at = loan.get("returned_at")
    if returned_at is None:
        return today
    return to_date(returned_at)


def overdue_days(due_at: datetime | date, reference: date) -> int:
    """Число дней просрочки. Неотрицательное."""
    delta = (reference - to_date(due_at)).days
    return delta if delta > 0 else 0


def loan_overdue_days(loan: dict[str, Any], today: date) -> int:
    """Число дней просрочки по одной выдаче.

    Raises:
        FineCalculationError: если в выдаче нет обязательных полей.
    """
    if "due_at" not in loan:
        raise FineCalculationError("В выдаче отсутствует поле due_at")
    return overdue_days(loan["due_at"], _reference_date(loan, today))


def fine_for_loan(
    loan: dict[str, Any],
    reader: dict[str, Any],
    today: date,
    rules: FineRules = DEFAULT_RULES,
) -> LoanFine | None:
    """Штраф по одной выдаче либо None, если просрочки нет."""
    days = loan_overdue_days(loan, today)
    if days == 0:
        return None

    amount = (
        Decimal(days) * rules.daily_rate * rules.category_multiplier(reader["category"])
    )

    if days > rules.grace_days:
        amount *= rules.long_overdue_multiplier

    was_capped = amount > rules.max_fine
    if was_capped:
        amount = rules.max_fine

    return LoanFine(
        loan_id=loan.get("id", 0),
        overdue_days=days,
        amount=amount,
        was_capped=was_capped,
    )


def returned_on_time_count(reader_id: int, loans: list[dict[str, Any]]) -> int:
    """Сколько раз читатель возвращал книги вовремя.

    Нужно для скидки: в исходной версии этот подсчёт был вторым почти
    идентичным проходом по списку выдач.
    """
    return sum(
        1
        for loan in loans
        if loan["reader_id"] == reader_id
        and loan.get("returned_at") is not None
        and to_date(loan["returned_at"]) <= to_date(loan["due_at"])
    )


def discount_multiplier(
    reader_id: int,
    loans: list[dict[str, Any]],
    rules: FineRules = DEFAULT_RULES,
) -> Decimal:
    """Множитель скидки за дисциплинированность."""
    on_time = returned_on_time_count(reader_id, loans)
    if on_time >= rules.discount_threshold:
        return rules.discount_percent
    return Decimal("1.0")


def summarize_reader_fine(
    reader: dict[str, Any],
    loans: list[dict[str, Any]],
    today: date,
    rules: FineRules = DEFAULT_RULES,
) -> FineSummary:
    """Разбор штрафа читателя по выдачам.

    Raises:
        FineCalculationError: если у читателя нет идентификатора.
        UnknownCategoryError: если категория читателя неизвестна.
    """
    reader_id = reader.get("id")
    if reader_id is None:
        raise FineCalculationError("У читателя отсутствует поле id")

    rules.category_multiplier(reader["category"])  # проверка категории заранее

    fines = tuple(
        fine
        for loan in loans
        if loan["reader_id"] == reader_id
        for fine in (fine_for_loan(loan, reader, today, rules),)
        if fine is not None
    )

    subtotal = sum((fine.amount for fine in fines), Decimal("0"))
    total = subtotal * discount_multiplier(reader_id, loans, rules)

    return FineSummary(
        reader_id=reader_id,
        total=quantize_money(total),
        loans=fines,
    )


def calculate_reader_fine(
    reader: dict[str, Any],
    loans: list[dict[str, Any]],
    today: date,
    rules: FineRules = DEFAULT_RULES,
) -> Decimal:
    """Итоговый штраф читателя. Совпадает с исходной версией."""
    return summarize_reader_fine(reader, loans, today, rules).total


def quantize_money(value: Decimal) -> Decimal:
    """Округляет денежную сумму до копеек.

    Режим округления совпадает с исходной версией, см. MONEY_ROUNDING.
    """
    return value.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


def format_fine(amount: Decimal) -> str:
    """Форматирует штраф для вывода клиенту."""
    if amount == 0:
        return "Штраф отсутствует"
    return f"Штраф: {amount} руб."


def to_date(value: datetime | date) -> date:
    """Приводит значение к дате.

    Raises:
        FineCalculationError: если значение не является датой.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise FineCalculationError(f"Ожидалась дата, получено: {type(value).__name__}")
