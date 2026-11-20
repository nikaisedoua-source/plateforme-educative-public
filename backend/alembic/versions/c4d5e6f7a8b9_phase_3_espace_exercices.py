"""Phase 3 : espace d'exercices (tentatives, consultations de corrigés, réglages).

Revision ID: c4d5e6f7a8b9
Revises: b7c1d2e3f4a5
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b7c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "exercise_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_ids", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("after_correction", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("result IN ('correct', 'incorrect', 'partial', 'submitted')", name="ck_attempts_result"),
    )
    op.create_index("ix_attempts_user_exercise", "exercise_attempts", ["user_id", "exercise_id"])
    op.create_table(
        "correction_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("views", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "exercise_id", name="uq_correction_views_user_exercise"),
    )
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("correction_access", sa.String(30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("correction_access")
    op.drop_table("correction_views")
    op.drop_index("ix_attempts_user_exercise", table_name="exercise_attempts")
    op.drop_table("exercise_attempts")
    op.drop_table("app_settings")
