"""expand career schedule

Revision ID: 20260716_0027
Revises: 20260716_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0027"
down_revision: str | None = "20260716_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_profiles",
        sa.Column(
            "available_weekdays",
            postgresql.JSONB(),
            nullable=False,
            server_default="[0, 2, 4, 5]",
        ),
    )
    op.add_column(
        "career_profiles",
        sa.Column(
            "preferred_time_slot",
            sa.String(20),
            nullable=False,
            server_default="evening",
        ),
    )
    op.add_column(
        "weekly_plans",
        sa.Column("basis", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column("weekly_plans", sa.Column("model", sa.String(100), nullable=True))
    op.add_column(
        "weekly_plans", sa.Column("prompt_version", sa.String(80), nullable=True)
    )
    op.add_column(
        "weekly_plans", sa.Column("skill_version", sa.String(30), nullable=True)
    )
    op.add_column(
        "weekly_plans",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE weekly_plans SET confirmed_at = created_at")
    op.alter_column("weekly_plans", "confirmed_at", nullable=False)

    op.create_table(
        "weekly_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("time_slot", sa.String(20), nullable=False),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("completion_criteria", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coaching_mode", sa.String(40), nullable=True),
        sa.Column("exercise_type", sa.String(40), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["weekly_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weekly_plan_items_plan_id", "weekly_plan_items", ["plan_id"])
    op.create_index(
        "ix_weekly_plan_items_scheduled_date", "weekly_plan_items", ["scheduled_date"]
    )
    op.create_index("ix_weekly_plan_items_task_type", "weekly_plan_items", ["task_type"])
    op.create_index("ix_weekly_plan_items_status", "weekly_plan_items", ["status"])
    op.create_index(
        "ix_weekly_plan_items_question_id", "weekly_plan_items", ["question_id"]
    )
    op.create_table(
        "career_plan_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_plan_drafts_user_id", "career_plan_drafts", ["user_id"])
    op.create_index("ix_career_plan_drafts_expires_at", "career_plan_drafts", ["expires_at"])
    op.execute(
        """
        INSERT INTO weekly_plan_items (
            id, plan_id, scheduled_date, time_slot, estimated_minutes, task_type,
            title, reason, completion_criteria, status, origin, position,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(), plan.id, plan.week_start, 'flexible', 20,
            CASE item.value->>'category'
                WHEN 'interview' THEN 'mock_interview'
                WHEN 'resume' THEN 'resume'
                WHEN 'application' THEN 'application'
                ELSE 'question_review'
            END,
            item.value->>'title', '从原周计划迁移',
            '按计划完成一次',
            CASE
                WHEN COALESCE((item.value->>'completed_count')::int, 0)
                    >= COALESCE((item.value->>'target_count')::int, 1)
                THEN 'completed' ELSE 'pending'
            END,
            'migrated', (item.ordinality - 1)::int, plan.created_at, plan.updated_at
        FROM weekly_plans AS plan,
        LATERAL jsonb_array_elements(plan.items) WITH ORDINALITY AS item(value, ordinality)
        """
    )
    op.add_column(
        "coaching_sessions",
        sa.Column("career_plan_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_coaching_sessions_career_plan_item_id",
        "coaching_sessions",
        "weekly_plan_items",
        ["career_plan_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_coaching_sessions_career_plan_item_id",
        "coaching_sessions",
        ["career_plan_item_id"],
    )
    op.drop_column("weekly_plans", "items")


def downgrade() -> None:
    op.drop_index(
        "ix_coaching_sessions_career_plan_item_id", table_name="coaching_sessions"
    )
    op.drop_constraint(
        "fk_coaching_sessions_career_plan_item_id",
        "coaching_sessions",
        type_="foreignkey",
    )
    op.drop_column("coaching_sessions", "career_plan_item_id")
    op.drop_table("career_plan_drafts")
    op.add_column(
        "weekly_plans",
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.execute(
        """
        UPDATE weekly_plans AS plan
        SET items = source.items
        FROM (
            SELECT plan_id, jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'category', CASE task_type
                        WHEN 'mock_interview' THEN 'interview'
                        WHEN 'resume' THEN 'resume'
                        WHEN 'application' THEN 'application'
                        ELSE 'learning'
                    END,
                    'title', title,
                    'target_count', 1,
                    'completed_count', CASE WHEN status = 'completed' THEN 1 ELSE 0 END
                ) ORDER BY position
            ) AS items
            FROM weekly_plan_items GROUP BY plan_id
        ) AS source
        WHERE source.plan_id = plan.id
        """
    )
    op.drop_table("weekly_plan_items")
    op.drop_column("weekly_plans", "confirmed_at")
    op.drop_column("weekly_plans", "skill_version")
    op.drop_column("weekly_plans", "prompt_version")
    op.drop_column("weekly_plans", "model")
    op.drop_column("weekly_plans", "basis")
    op.drop_column("career_profiles", "preferred_time_slot")
    op.drop_column("career_profiles", "available_weekdays")
