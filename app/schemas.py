"""Схемы Pydantic для валидации входных и выходных данных."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Book, Reader


class ItemBase(BaseModel):
    """Общие поля книги.

    `Item` - основная сущность предметной области: книга в фонде библиотеки.
    """

    # Запрещаем поля, которых нет в модели: без этого лишние поля молча
    # игнорировались бы, и клиент не получил бы ответа о неверном запросе.
    model_config = ConfigDict(extra="forbid")

    isbn: str = Field(
        min_length=10,
        max_length=17,
        description="ISBN-10 или ISBN-13",
        examples=["978-5-17-115205-6"],
    )
    title: str = Field(min_length=1, max_length=255, examples=["Мастер и Маргарита"])
    author: str = Field(min_length=1, max_length=255, examples=["Булгаков М.А."])
    year: int = Field(ge=1450, le=2100, examples=[1967])
    genre: str = Field(
        min_length=1, max_length=64, examples=["Художественная литература"]
    )
    total_copies: int = Field(ge=0, le=1000, examples=[3])

    @field_validator("title", "author", "genre")
    @classmethod
    def _strip_whitespace(cls, value: str) -> str:
        """Убирает лишние пробелы, чтобы поиск по названию работал предсказуемо."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("значение не должно состоять только из пробелов")
        return cleaned


class ItemCreate(ItemBase):
    """Данные для создания книги."""

    available_copies: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Свободных экземпляров. Если не задано - равен total_copies.",
    )

    def resolved_available_copies(self) -> int:
        """Возвращает число свободных экземпляров с учётом значения по умолчанию."""
        if self.available_copies is None:
            return self.total_copies
        return min(self.available_copies, self.total_copies)


class ItemUpdate(BaseModel):
    """Частичное обновление книги: переданные только поля изменяются."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    year: int | None = Field(default=None, ge=1450, le=2100)
    genre: str | None = Field(default=None, min_length=1, max_length=64)
    total_copies: int | None = Field(default=None, ge=0, le=1000)


class ItemRead(ItemBase):
    """Книга, возвращаемая клиенту."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    available_copies: int


class ReaderBase(BaseModel):
    """Общие поля читателя."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=255, examples=["Иванов Иван"])
    email: EmailStr = Field(examples=["ivanov@example.com"])
    phone: str | None = Field(
        default=None, max_length=32, examples=["+7 900 000-00-00"]
    )


class ReaderCreate(ReaderBase):
    """Данные для регистрации читателя."""


class ReaderRead(ReaderBase):
    """Читатель, возвращаемый клиенту."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    registered_at: datetime


class LoanRead(BaseModel):
    """Выдача книги, возвращаемая клиенту."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    reader_id: int
    issued_at: datetime
    due_at: datetime
    returned_at: datetime | None
    fine: float


class HealthResponse(BaseModel):
    """Ответ сервиса проверки состояния."""

    status: str
    app_name: str
    version: str
    today: date


def book_to_read_schema(book: Book) -> ItemRead:
    """Преобразует модель SQLAlchemy в схему ответа."""
    return ItemRead.model_validate(book)


def reader_to_read_schema(reader: Reader) -> ReaderRead:
    """Преобразует модель SQLAlchemy в схему ответа."""
    return ReaderRead.model_validate(reader)
