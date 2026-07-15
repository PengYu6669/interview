"""extend coaching attempts

Revision ID: 20260715_0025
Revises: 20260715_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0025"
down_revision: str | None = "20260715_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coaching_turns",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "coaching_turns",
        sa.Column("elapsed_seconds", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_coaching_turns_attempt_number",
        "coaching_turns",
        "attempt_number BETWEEN 1 AND 3",
    )
    op.create_check_constraint(
        "ck_coaching_turns_elapsed_seconds",
        "coaching_turns",
        "elapsed_seconds IS NULL OR elapsed_seconds BETWEEN 0 AND 3600",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_coaching_turns_elapsed_seconds", "coaching_turns", type_="check"
    )
    op.drop_constraint(
        "ck_coaching_turns_attempt_number", "coaching_turns", type_="check"
    )
    op.drop_column("coaching_turns", "elapsed_seconds")
    op.drop_column("coaching_turns", "attempt_number")
