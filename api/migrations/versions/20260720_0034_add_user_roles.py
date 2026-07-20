"""add user roles

Revision ID: 20260720_0034
Revises: 20260718_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0034"
down_revision: str | None = "20260718_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), server_default="user", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('user', 'admin')",
    )
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
