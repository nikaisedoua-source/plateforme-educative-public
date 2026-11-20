"""Phase 2 : séries multiples par document et par exercice (2nde A/C, 1ère A/C/D/E, Tle A/C/D/E…).

Revision ID: b7c1d2e3f4a5
Revises: 3969043719cd
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c1d2e3f4a5"
down_revision = "3969043719cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_tracks",
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "exercise_tracks",
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_exercise_tracks_track", "exercise_tracks", ["track_id"])
    # Reprise des séries uniques déjà saisies.
    op.execute("INSERT INTO document_tracks (document_id, track_id) SELECT id, track_id FROM documents WHERE track_id IS NOT NULL")
    op.execute("INSERT INTO exercise_tracks (exercise_id, track_id) SELECT id, track_id FROM exercises WHERE track_id IS NOT NULL")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("track_id")
    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("track_id")


def downgrade() -> None:
    for table in ("documents", "exercises"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True))
    # Une seule série conservée par contenu (la plus petite) : retour arrière avec perte assumée.
    op.execute("UPDATE documents SET track_id = (SELECT MIN(track_id) FROM document_tracks WHERE document_id = documents.id)")
    op.execute("UPDATE exercises SET track_id = (SELECT MIN(track_id) FROM exercise_tracks WHERE exercise_id = exercises.id)")
    op.drop_index("ix_exercise_tracks_track", table_name="exercise_tracks")
    op.drop_table("exercise_tracks")
    op.drop_table("document_tracks")
