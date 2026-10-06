"""CRUD-маршруты основной сущности: книги (Item)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ConflictError, NotFoundError
from app.models import Book
from app.schemas import ItemCreate, ItemRead, ItemUpdate

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


def _find_by_isbn(db: Session, isbn: str) -> Book | None:
    """Ищет книгу по ISBN."""
    return db.scalar(select(Book).where(Book.isbn == isbn))


def _get_or_404(db: Session, item_id: int) -> Book:
    """Возвращает книгу по id или выбрасывает 404."""
    book = db.get(Book, item_id)
    if book is None:
        raise NotFoundError(f"Книга с id={item_id} не найдена")
    return book


@router.get("", response_model=list[ItemRead], summary="Список книг")
def list_items(
    db: DbSession,
    search: Annotated[
        str | None, Query(max_length=255, description="Поиск по названию или автору")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Book]:
    """Возвращает страницу книг с необязательным поиском по названию и автору."""
    statement: Select[tuple[Book]] = select(Book)

    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(Book.title.ilike(pattern), Book.author.ilike(pattern))
        )

    statement = statement.order_by(Book.id).offset(skip).limit(limit)
    return list(db.scalars(statement))


@router.get("/{item_id}", response_model=ItemRead, summary="Книга по id")
def get_item(item_id: int, db: DbSession) -> Book:
    """Возвращает одну книгу."""
    return _get_or_404(db, item_id)


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать книгу",
)
def create_item(payload: ItemCreate, db: DbSession) -> Book:
    """Создаёт новую книгу. ISBN должен быть уникальным."""
    isbn = payload.isbn.strip()
    if _find_by_isbn(db, isbn) is not None:
        raise ConflictError(f"Книга с ISBN {isbn} уже существует")

    available = payload.resolved_available_copies()
    book = Book(
        isbn=isbn,
        title=payload.title,
        author=payload.author,
        year=payload.year,
        genre=payload.genre,
        total_copies=payload.total_copies,
        available_copies=available,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@router.put("/{item_id}", response_model=ItemRead, summary="Обновить книгу")
def update_item(item_id: int, payload: ItemUpdate, db: DbSession) -> Book:
    """Частично обновляет книгу: изменяются только переданные поля."""
    book = _get_or_404(db, item_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return book

    if "total_copies" in changes:
        new_total = changes["total_copies"]
        issued = book.total_copies - book.available_copies
        if new_total < issued:
            raise ConflictError(
                f"Нельзя установить total_copies={new_total}: в выдаче {issued} шт."
            )
        changes["available_copies"] = new_total - issued

    for field, value in changes.items():
        setattr(book, field, value)

    db.commit()
    db.refresh(book)
    return book


@router.delete(
    "/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить книгу"
)
def delete_item(item_id: int, db: DbSession) -> None:
    """Удаляет книгу, если ни один её экземпляр не выдан читателю."""
    book = _get_or_404(db, item_id)

    issued_copies = book.total_copies - book.available_copies
    if issued_copies > 0:
        raise ConflictError(f"Книгу нельзя удалить: в выдаче {issued_copies} шт.")

    db.delete(book)
    db.commit()


@router.get("/stats/summary", response_model=dict[str, int], summary="Сводка по фонду")
def items_stats(db: DbSession) -> dict[str, int]:
    """Количество книг и суммарное число экземпляров."""
    total_titles = db.scalar(select(func.count()).select_from(Book)) or 0
    total_copies = db.scalar(select(func.coalesce(func.sum(Book.total_copies), 0))) or 0
    available = (
        db.scalar(select(func.coalesce(func.sum(Book.available_copies), 0))) or 0
    )
    return {
        "titles": total_titles,
        "total_copies": total_copies,
        "available_copies": available,
        "issued_copies": total_copies - available,
    }
