"""Сравнение версий расчёта штрафа: до рефакторинга и после.

Скрипт прогоняет обе версии на одних и тех же данных и показывает,
что итоговые суммы совпадают, при этом новая версия дополнительно
разбирает результат по выдачам и сообщает о плохих данных вместо
необработанного исключения.

Запуск:
    python scripts/demo_task3.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import fines, fines_before  # noqa: E402

TODAY = date(2026, 10, 6)


def _datetime(days: int) -> datetime:
    return datetime(2026, 1, 1) + timedelta(days=days)


READER: dict[str, Any] = {"id": 1, "category": "student"}


def build_loans() -> list[dict[str, Any]]:
    """Набор выдач: просрочка, вовремя, часть выдано."""
    return [
        {
            "id": 10,
            "reader_id": 1,
            "due_at": _datetime(0),
            "returned_at": None,
        },
        {
            "id": 11,
            "reader_id": 1,
            "due_at": _datetime(10),
            "returned_at": _datetime(12),
        },
        {
            "id": 12,
            "reader_id": 1,
            "due_at": _datetime(20),
            "returned_at": _datetime(50),
        },
        {
            "id": 13,
            "reader_id": 1,
            "due_at": _datetime(30),
            "returned_at": _datetime(32),
        },
        {
            "id": 14,
            "reader_id": 1,
            "due_at": _datetime(40),
            "returned_at": _datetime(44),
        },
        {
            "id": 15,
            "reader_id": 1,
            "due_at": _datetime(50),
            "returned_at": _datetime(54),
        },
        {
            "id": 20,
            "reader_id": 2,
            "due_at": _datetime(0),
            "returned_at": None,
        },
    ]


def main() -> int:
    loans = build_loans()

    print(f"Дата расчёта: {TODAY}")
    print(f"Читатель: {READER}")
    print(f"Выдач всего: {len(loans)}, из них читателя №1: {len(loans) - 1}")
    print()

    old_total = fines_before.calculate_reader_fine(READER, loans, TODAY)
    new_total = fines.calculate_reader_fine(READER, loans, TODAY)
    summary = fines.summarize_reader_fine(READER, loans, TODAY)

    print("1. Итог до рефакторинга")
    print(f"   {fines_before.format_fine(old_total)}")
    print()
    print("2. Итог после рефакторинга")
    print(f"   {fines.format_fine(new_total)}")
    print(f"   Совпадает с исходной версией: {old_total == new_total}")
    print()

    print("3. Разбор по выдачам - в исходной версии этого не было")
    for fine in summary.loans:
        print(
            f"   выдача {fine.loan_id}: просрочка {fine.overdue_days} дн., "
            f"штраф {fine.amount_display}, ограничен: {fine.was_capped}"
        )
    print()

    print("4. Проверка правил расчёта")
    rules = fines.DEFAULT_RULES
    print(f"   ставка в день: {rules.daily_rate}")
    print(f"   льготный период: {rules.grace_days} дн.")
    print(f"   множитель за долгую просрочку: {rules.long_overdue_multiplier}")
    print(f"   максимальный штраф за выдачу: {rules.max_fine}")
    print(f"   порог скидки: {rules.discount_threshold} возвратов вовремя")
    print(f"   коэффициент скидки: {rules.discount_percent}")
    print(f"   ставка для категории student: {rules.category_multiplier('student')}")
    print(f"   ставка для категории regular: {rules.category_multiplier('regular')}")
    print(f"   ставка для категории staff:   {rules.category_multiplier('staff')}")
    print()

    print("5. Размер функции")
    import inspect

    old_lines = len(inspect.getsource(fines_before.calculate_reader_fine).splitlines())
    new_lines = len(inspect.getsource(fines.calculate_reader_fine).splitlines())
    print(f"   было: {old_lines} строк в одной функции")
    print(
        f"   стало: {new_lines} строк, логика разнесена по {len(inspect.getsource(fines).splitlines())} строкам модуля"
    )
    print()

    print("6. Обработка ошибок")
    bad_reader: dict[str, Any] = {"id": 1, "category": "vip"}

    try:
        fines_before.calculate_reader_fine(bad_reader, loans, TODAY)
    except Exception as exc:
        print(f"   было:  {type(exc).__name__}: {exc}")

    try:
        fines.calculate_reader_fine(bad_reader, loans, TODAY)
    except fines.UnknownCategoryError as exc:
        print(f"   стало: UnknownCategoryError: {exc}")

    try:
        fines.calculate_reader_fine({}, loans, TODAY)
    except fines.FineCalculationError as exc:
        print(f"   стало: FineCalculationError: {exc}")

    try:
        fines.to_date("2026-01-01")  # type: ignore[arg-type]
    except fines.FineCalculationError as exc:
        print(f"   стало: FineCalculationError: {exc}")
    print()

    print("7. Граничные случаи")
    for label, case_reader, case_loans in [
        ("нет выдач", READER, []),
        (
            "просрочки нет",
            READER,
            [
                {
                    "id": 1,
                    "reader_id": 1,
                    "due_at": _datetime(0),
                    "returned_at": _datetime(0),
                }
            ],
        ),
        (
            "чужая выдача",
            READER,
            [{"id": 2, "reader_id": 99, "due_at": _datetime(0), "returned_at": None}],
        ),
    ]:
        old = fines_before.calculate_reader_fine(case_reader, case_loans, TODAY)
        new = fines.calculate_reader_fine(case_reader, case_loans, TODAY)
        print(f"   {label}: было {old}, стало {new}, совпадает: {old == new}")
    print()

    print("8. Проверка совпадения на 200 сгенерированных наборах")
    mismatches = 0
    first_mismatch = ""
    for case in range(200):
        days = case % 90
        reader = {"id": 1, "category": ["student", "regular", "staff"][case % 3]}
        payload = [
            {
                "id": 1000 + case,
                "reader_id": 1,
                "due_at": _datetime(0),
                "returned_at": None if case % 4 == 0 else _datetime(days),
            }
        ]
        old = fines_before.calculate_reader_fine(reader, payload, TODAY)
        new = fines.calculate_reader_fine(reader, payload, TODAY)
        if old != new:
            mismatches += 1
            if not first_mismatch:
                first_mismatch = f"набор №{case}: было {old}, стало {new}"
    print(f"   расхождений: {mismatches} из 200")
    if first_mismatch:
        print(f"   первое расхождение: {first_mismatch}")
    print()

    print("9. Про режим округления")
    print(f"   округление в исходной версии и в новой: {fines.MONEY_ROUNDING}")
    print("   104.625 -> " + str(fines.quantize_money(Decimal("104.625"))))
    print("   (ROUND_HALF_UP дал бы 104.63, поэтому режим сохранён исходный)")
    print()

    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
