"""Добавление заметок к выдачам и индекса для поиска просрочек

Revision ID: 0002_add_loan_notes
Revises: 0001_initial_schema
Create Date: 2026-10-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_loan_notes"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "loans",
        sa.Column("notes", sa.Text(), nullable=True, server_default=None),
    )
    op.create_index("ix_loans_returned_at", "loans", ["returned_at"])


def downgrade() -> None:
    op.drop_index("ix_loans_returned_at", table_name="loans")
    op.drop_column("loans", "notes")