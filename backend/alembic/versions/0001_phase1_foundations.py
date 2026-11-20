"""Initial schema: accounts and education reference data.

Revision ID: 0001_phase1
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "educational_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=30), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )
    op.create_table(
        "grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("educational_cycles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=30), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.UniqueConstraint("grade_id", "name", "academic_year", name="uq_classes_grade_name_year"),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("grade_id", "subject_id", "title", name="uq_chapters_grade_subject_title"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="student"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pseudo", sa.String(length=40), nullable=False, unique=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("student_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("chapters")
    op.drop_table("subjects")
    op.drop_table("classes")
    op.drop_table("grades")
    op.drop_table("educational_cycles")
