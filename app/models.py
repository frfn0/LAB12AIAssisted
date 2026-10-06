"""Модели предметной области: книги, читатели и выдачи."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    """Текущее время в UTC без локального смещения."""
    return datetime.now(timezone.utc)


class Book(Base):
    """Книга в фонде библиотеки.

    `available_copies` не может превышать `total_copies` и не может быть
    отрицательным - это проверяется ограничением на уровне таблицы.
    """

    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "total_copies >= 0",
            name="ck_books_total_copies_non_negative",
        ),
        CheckConstraint(
            "available_copies >= 0 AND available_copies <= total_copies",
            name="ck_books_available_within_total",
        ),
        Index("ix_books_title", "title"),
        Index("ix_books_author", "author"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(17), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    genre: Mapped[str] = mapped_column(String(64), nullable=False)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False)

    loans: Mapped[list["Loan"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )


class Reader(Base):
    """Читатель библиотеки."""

    __tablename__ = "readers"
    __table_args__ = (Index("ix_readers_full_name", "full_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    loans: Mapped[list["Loan"]] = relationship(
        back_populates="reader",
        cascade="all, delete-orphan",
    )


class Loan(Base):
    """Выдача книги читателю.

    Связь many-to-one с книгой и читателем. Индексы добавлены под запросы
    задания 9: выдачи за период и книги с наибольшим числом выдач.
    """

    __tablename__ = "loans"
    __table_args__ = (
        Index("ix_loans_issued_at", "issued_at"),
        Index("ix_loans_book_id_reader_id", "book_id", "reader_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
    )
    reader_id: Mapped[int] = mapped_column(
        ForeignKey("readers.id", ondelete="CASCADE"),
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fine: Mapped[float] = mapped_column(nullable=False, default=0.0)

    book: Mapped[Book] = relationship(back_populates="loans")
    reader: Mapped[Reader] = relationship(back_populates="loans")

    @property
    def is_returned(self) -> bool:
        """Книга возвращена, если заполнено поле `returned_at`."""
        return self.returned_at is not None

    @property
    def overdue_days(self) -> int:
        """Количество дней просрочки на сегодняшний день."""
        reference = self.returned_at or _utc_now()
        return max((reference.date() - self.due_at.date()).days, 0)

    def as_dict(self) -> dict[str, object]:
        """Плоское представление для отчётов и аналитических запросов."""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "reader_id": self.reader_id,
            "issued_at": self.issued_at,
            "due_at": self.due_at,
            "returned_at": self.returned_at,
            "fine": self.fine,
            "overdue_days": self.overdue_days,
        }


def today() -> date:
    """Текущая дата в UTC."""
    return _utc_now().date()
