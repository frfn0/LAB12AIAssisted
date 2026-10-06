"""Начальная схема: книги, читатели, выдачи

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-06 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("isbn", sa.String(length=17), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("genre", sa.String(length=64), nullable=False),
        sa.Column("total_copies", sa.Integer(), nullable=False),
        sa.Column("available_copies", sa.Integer(), nullable=False),
        sa.UniqueConstraint("isbn", name="uq_books_isbn"),
        sa.CheckConstraint("total_copies >= 0", name="ck_books_total_copies_non_negative"),
        sa.CheckConstraint(
            "available_copies >= 0 AND available_copies <= total_copies",
            name="ck_books_available_within_total",
        ),
    )
    op.create_index("ix_books_title", "books", ["title"])
    op.create_index("ix_books_author", "books", ["author"])

    op.create_table(
        "readers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_readers_email"),
    )
    op.create_index("ix_readers_full_name", "readers", ["full_name"])

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("reader_id", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fine", sa.Float(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reader_id"], ["readers.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_loans_issued_at", "loans", ["issued_at"])
    op.create_index("ix_loans_book_id_reader_id", "loans", ["book_id", "reader_id"])


def downgrade() -> None:
    op.drop_index("ix_loans_book_id_reader_id", table_name="loans")
    op.drop_index("ix_loans_issued_at", table_name="loans")
    op.drop_table("loans")

    op.drop_index("ix_readers_full_name", table_name="readers")
    op.drop_table("readers")

    op.drop_index("ix_books_author", table_name="books")
    op.drop_index("ix_books_title", table_name="books")
    op.drop_table("books")