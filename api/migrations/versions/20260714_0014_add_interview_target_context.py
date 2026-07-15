"""增加面试目标上下文。

Revision ID: 20260714_0014
Revises: 20260714_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0014"
down_revision: str | None = "20260714_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEVELS = "'intern', 'campus', 'mid', 'senior'"
ROUNDS = "'first', 'second', 'final', 'manager'"
TYPES = "'comprehensive', 'project', 'technical', 'system_design', 'behavioral', 'weak_area'"


def upgrade() -> None:
    for table in ("training_drafts", "interview_sessions"):
        op.add_column(
            table,
            sa.Column("target_company", sa.String(length=100), nullable=False, server_default=""),
        )
        op.add_column(
            table,
            sa.Column(
                "target_level", sa.String(length=30), nullable=False, server_default="campus"
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "interview_round", sa.String(length=30), nullable=False, server_default="first"
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "interview_type",
                sa.String(length=30),
                nullable=False,
                server_default="comprehensive",
            ),
        )
        op.create_check_constraint(
            f"ck_{table}_target_level",
            table,
            f"target_level IN ({LEVELS})",
        )
        op.create_check_constraint(
            f"ck_{table}_interview_round",
            table,
            f"interview_round IN ({ROUNDS})",
        )
        op.create_check_constraint(
            f"ck_{table}_interview_type",
            table,
            f"interview_type IN ({TYPES})",
        )
        for column in ("target_company", "target_level", "interview_round", "interview_type"):
            op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    for table in ("interview_sessions", "training_drafts"):
        for name in ("interview_type", "interview_round", "target_level"):
            op.drop_constraint(f"ck_{table}_{name}", table, type_="check")
        for column in ("interview_type", "interview_round", "target_level", "target_company"):
            op.drop_column(table, column)
