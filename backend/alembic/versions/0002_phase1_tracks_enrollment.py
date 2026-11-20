"""Phase 1 : séries/spécialités et validation du parcours élève.

Revision ID: 0002_phase1_tracks
Revises: 0001_phase1
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_phase1_tracks"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("grade_id", "name", name="uq_tracks_grade_name"),
        sa.CheckConstraint("kind IN ('serie', 'specialite', 'option', 'filiere')", name="ck_tracks_kind"),
    )
    op.add_column(
        "student_profiles",
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="SET NULL",
                  name="fk_student_profiles_track_id"), nullable=True),
    )
    op.add_column(
        "student_profiles",
        sa.Column("enrollment_status", sa.String(length=20), nullable=False, server_default="none"),
    )
    op.add_column("student_profiles", sa.Column("enrollment_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("student_profiles", sa.Column("enrollment_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "student_profiles",
        sa.Column("enrollment_reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL",
                  name="fk_student_profiles_reviewed_by"), nullable=True),
    )
    op.create_check_constraint(
        "ck_student_profiles_enrollment_status",
        "student_profiles",
        "enrollment_status IN ('none', 'pending', 'approved', 'rejected')",
    )
    # Les élèves déjà inscrits avec un niveau attendent désormais une validation administrateur.
    op.execute(
        "UPDATE student_profiles SET enrollment_status = 'pending', enrollment_requested_at = now() "
        "WHERE grade_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint("ck_student_profiles_enrollment_status", "student_profiles", type_="check")
    op.drop_column("student_profiles", "enrollment_reviewed_by")
    op.drop_column("student_profiles", "enrollment_reviewed_at")
    op.drop_column("student_profiles", "enrollment_requested_at")
    op.drop_column("student_profiles", "enrollment_status")
    op.drop_column("student_profiles", "track_id")
    op.drop_table("tracks")
