"""Тесты расчёта штрафа: рабочая версия и её соответствие исходной.

Ключевая идея набора - рефакторинг не должен менять поведение, поэтому
почти каждый тест считает сумму обеими версиями и требует равенства.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.services import fines, fines_before

TODAY = date(2026, 10, 6)


def _dt(days: int) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=days)


def _loan(
    loan_id: int = 1,
    reader_id: int = 1,
    due_days: int = 0,
    returned_days: int | None = None,
) -> dict[str, object]:
    return {
        "id": loan_id,
        "reader_id": reader_id,
        "due_at": _dt(due_days),
        "returned_at": None if returned_days is None else _dt(returned_days),
    }


READER: dict[str, object] = {"id": 1, "category": "student"}
REGULAR: dict[str, object] = {"id": 1, "category": "regular"}


# ---------------------------------------------------------------- базовые случаи


def test_просрочки_нет_штраф_нулевой() -> None:
    loans = [_loan(due_days=0, returned_days=0)]
    assert fines.calculate_reader_fine(READER, loans, TODAY) == Decimal("0.00")


def test_нет_выдач_штраф_нулевой() -> None:
    assert fines.calculate_reader_fine(READER, [], TODAY) == Decimal("0.00")


def test_выдача_другого_читателя_не_учитывается() -> None:
    loans = [_loan(reader_id=99)]
    assert fines.calculate_reader_fine(READER, loans, TODAY) == Decimal("0.00")


def test_просрочка_считается_до_момента_возврата() -> None:
    """После возврата просрочка перестаёт расти."""
    loans = [_loan(due_days=0, returned_days=5)]

    summary = fines.summarize_reader_fine(READER, loans, TODAY)

    assert summary.loans[0].overdue_days == 5


def test_невозвращённая_книга_считается_на_сегодня() -> None:
    loans = [_loan(due_days=0)]

    summary = fines.summarize_reader_fine(READER, loans, TODAY)

    assert summary.loans[0].overdue_days == (TODAY - _dt(0).date()).days


# -------------------------------------------------------------------- правила


def test_ставка_для_студента() -> None:
    """Ставка 1.50 в день без дополнительных множителей."""
    loans = [_loan(due_days=0, returned_days=4)]

    assert fines.calculate_reader_fine(READER, loans, TODAY) == Decimal("6.00")


def test_категория_влияет_на_ставку() -> None:
    """Обычный читатель платит в полтора раза больше студента."""
    loans = [_loan(due_days=0, returned_days=4)]

    assert fines.calculate_reader_fine(REGULAR, loans, TODAY) == Decimal("9.00")


def test_льготный_период_не_штрафуется() -> None:
    """Ровно grace_days просрочки ещё не умножается на коэффициент."""
    loans = [_loan(due_days=0, returned_days=30)]

    assert fines.calculate_reader_fine(READER, loans, TODAY) == Decimal("45.00")


def test_свыше_льготного_периода_включается_множитель() -> None:
    """Просрочка длиннее grace_days умножается на 1.5."""
    loans = [_loan(due_days=0, returned_days=31)]

    assert fines.calculate_reader_fine(READER, loans, TODAY) == Decimal("69.75")


def test_штраф_по_одной_выдаче_ограничен() -> None:
    """Бесконечная просрочка не даёт штраф больше max_fine."""
    loans = [_loan(due_days=0)]

    summary = fines.summarize_reader_fine(READER, loans, TODAY)

    assert summary.loans[0].amount_display == fines.DEFAULT_RULES.max_fine
    assert summary.loans[0].was_capped is True


def test_скидка_за_пять_возвратов_вовремя() -> None:
    """Пять возвратов вовремя дают коэффициент 0.9."""
    loans = [_loan(loan_id=0, due_days=0, returned_days=0)]
    loans += [
        _loan(loan_id=index, due_days=100, returned_days=100) for index in range(1, 5)
    ]
    loans.append(_loan(loan_id=99, due_days=0, returned_days=10))

    assert fines.discount_multiplier(1, loans) == Decimal("0.9")


def test_без_скидки_при_четырёх_возвратах() -> None:
    """Четырёх возвратов вовремя недостаточно для скидки."""
    loans = [
        _loan(loan_id=index, due_days=100, returned_days=100) for index in range(4)
    ]

    assert fines.discount_multiplier(1, loans) == Decimal("1.0")


def_loan_fine = fines.fine_for_loan


def test_скидка_применяется_к_итогу() -> None:
    """Итог уменьшается на 10% при достаточном числе возвратов вовремя."""
    loans = [
        _loan(loan_id=0, due_days=0, returned_days=0),
        _loan(loan_id=1, due_days=100, returned_days=100),
        _loan(loan_id=2, due_days=100, returned_days=100),
        _loan(loan_id=3, due_days=100, returned_days=100),
        _loan(loan_id=4, due_days=100, returned_days=100),
        _loan(loan_id=9, due_days=0, returned_days=10),
    ]

    subtotal = Decimal("15.00")
    total = fines.calculate_reader_fine(READER, loans, TODAY)

    assert total == (subtotal * Decimal("0.9")).quantize(Decimal("0.01"))


# ------------------------------------------------------------------ обработка


def test_неизвестная_категория_даёт_понятную_ошибку() -> None:
    """Вместо KeyError выбрасывается именованное исключение с текстом."""
    with pytest.raises(fines.UnknownCategoryError, match="vip"):
        fines.calculate_reader_fine({"id": 1, "category": "vip"}, [], TODAY)


def test_отсутствие_id_читателя_даёт_ошибку() -> None:
    """Читатель без идентификатора отвергается."""
    with pytest.raises(fines.FineCalculationError, match="id"):
        fines.calculate_reader_fine({"category": "student"}, [], TODAY)


def test_отсутствие_due_at_даёт_ошибку() -> None:
    """Выдача без срока выдачи отвергается."""
    with pytest.raises(fines.FineCalculationError, match="due_at"):
        fines.loan_overdue_days({"id": 1, "returned_at": None}, TODAY)


def test_to_date_отвергает_строку() -> None:
    """Вместо AttributeError выбрасывается понятная ошибка."""
    with pytest.raises(fines.FineCalculationError, match="Ожидалась дата"):
        fines.to_date("2026-01-01")  # type: ignore[arg-type]


def test_исходная_версия_падает_на_неизвестной_категории() -> None:
    """Зафиксировано поведение плохой версии: необработанный KeyError."""
    with pytest.raises(KeyError):
        fines_before.calculate_reader_fine({"id": 1, "category": "vip"}, [], TODAY)


# ------------------------------------------------- соответствие исходной версии


@pytest.mark.parametrize("category", ["student", "regular", "staff"])
@pytest.mark.parametrize("days", [0, 1, 29, 30, 31, 45, 60, 120, 365])
def test_совпадает_с_исходной_версией(category: str, days: int) -> None:
    """Одиночная выдача: обе версии дают одну и ту же сумму."""
    reader = {"id": 1, "category": category}
    loans = [_loan(due_days=0, returned_days=days)]

    assert fines.calculate_reader_fine(reader, loans, TODAY) == (
        fines_before.calculate_reader_fine(reader, loans, TODAY)
    )


@pytest.mark.parametrize("case", range(50))
def test_совпадает_на_сгенерированных_наборах(case: int) -> None:
    """Случайные наборы выдач: расхождений быть не должно."""
    reader = {"id": 1, "category": ["student", "regular", "staff"][case % 3]}
    loans = [
        _loan(
            loan_id=index,
            reader_id=1 if index % 5 else 2,
            due_days=index * 3,
            returned_days=None if index % 3 == 0 else index * 3 + (case % 11),
        )
        for index in range(6)
    ]

    assert fines.calculate_reader_fine(reader, loans, TODAY) == (
        fines_before.calculate_reader_fine(reader, loans, TODAY)
    )


def test_итог_совпадает_на_большом_наборе() -> None:
    """Полный сценарий демонстрации: суммы идентичны."""
    loans = [
        _loan(loan_id=10, due_days=0),
        _loan(loan_id=11, due_days=10, returned_days=12),
        _loan(loan_id=12, due_days=20, returned_days=50),
        _loan(loan_id=13, due_days=30, returned_days=32),
        _loan(loan_id=14, due_days=40, returned_days=44),
        _loan(loan_id=15, due_days=50, returned_days=54),
        _loan(loan_id=20, reader_id=2, due_days=0),
    ]

    assert fines.calculate_reader_fine(READER, loans, TODAY) == (
        fines_before.calculate_reader_fine(READER, loans, TODAY)
    )


# -------------------------------------------------------- вспомогательные функции


def test_возвращённая_вовремя_книга_не_увеличивает_счётчик() -> None:
    """Просроченный возврат не засчитывается как возврат вовремя."""
    loans = [_loan(due_days=0, returned_days=10)]

    assert fines.returned_on_time_count(1, loans) == 0


def test_сводка_содержит_разбор_по_выдачам() -> None:
    """Итог содержит детализацию, которой в исходной версии не было."""
    loans = [_loan(loan_id=7, due_days=0, returned_days=3)]

    summary = fines.summarize_reader_fine(READER, loans, TODAY).as_dict()

    assert summary["reader_id"] == 1
    assert summary["total"] == "4.50"
    assert summary["loans"] == [
        {
            "loan_id": 7,
            "overdue_days": 3,
            "amount": "4.50",
            "was_capped": False,
        }
    ]


def test_форматирование_нулевого_штрафа() -> None:
    """Форматирование совпадает с исходной версией."""
    assert fines.format_fine(Decimal("0.00")) == fines_before.format_fine(
        Decimal("0.00")
    )


def test_форматирование_ненулевого_штрафа() -> None:
    """Форматирование совпадает с исходной версией."""
    assert fines.format_fine(Decimal("12.50")) == fines_before.format_fine(
        Decimal("12.50")
    )


def test_режим_округления_совпадает_с_исходным() -> None:
    """Банковское округление исходной версии сохранено."""
    from decimal import ROUND_HALF_EVEN

    assert fines.MONEY_ROUNDING == ROUND_HALF_EVEN
    assert fines.quantize_money(Decimal("104.625")) == Decimal("104.62")


def test_правила_можно_переопределить() -> None:
    """Правила вынесены в объект, поэтому ставку можно изменить без кода."""
    custom = fines.FineRules(daily_rate=Decimal("3.00"))

    result = fines.calculate_reader_fine(
        READER, [_loan(returned_days=4)], TODAY, custom
    )

    assert result == Decimal("12.00")


def test_размер_исходной_функции_превышает_30_строк() -> None:
    """Исходная функция действительно длиннее 30 строк, как требует задание."""
    import inspect

    source = inspect.getsource(fines_before.calculate_reader_fine)

    assert len(source.splitlines()) > 30


def test_в_исходной_версии_есть_магические_числа() -> None:
    """Фиксируем наличие магических чисел в плохой версии."""
    import inspect

    source = inspect.getsource(fines_before.calculate_reader_fine)

    for magic in (
        'Decimal("1.50")',
        "> 30",
        'Decimal("500")',
        ">= 5",
        'Decimal("0.9")',
    ):
        assert magic in source, magic
