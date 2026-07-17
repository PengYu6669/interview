"""link mock interview drafts to weekly plan items

Revision ID: 20260717_0030
Revises: 20260716_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0030"
down_revision: str | None = "20260716_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_drafts",
        sa.Column(
            "career_plan_item_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_training_drafts_career_plan_item_id",
        "training_drafts",
        "weekly_plan_items",
        ["career_plan_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_training_drafts_career_plan_item_id",
        "training_drafts",
        ["career_plan_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_drafts_career_plan_item_id", table_name="training_drafts"
    )
    op.drop_constraint(
        "fk_training_drafts_career_plan_item_id",
        "training_drafts",
        type_="foreignkey",
    )
    op.drop_column("training_drafts", "career_plan_item_id")
