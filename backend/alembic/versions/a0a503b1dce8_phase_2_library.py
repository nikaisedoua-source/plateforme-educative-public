"""Phase 2 : bibliothèque documentaire (documents, pages, exercices, options, captures, corrigés, journal).

Revision ID: a0a503b1dce8
Revises: 0002_phase1_tracks
"""
from alembic import op
import sqlalchemy as sa

revision = "a0a503b1dce8"
down_revision = "0002_phase1_tracks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('mime_type', sa.String(length=120), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=20), server_default='autre', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='imported', nullable=False),
    sa.Column('page_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('pages_done', sa.Integer(), server_default='0', nullable=False),
    sa.Column('extraction_error', sa.Text(), nullable=True),
    sa.Column('grade_id', sa.Integer(), nullable=True),
    sa.Column('track_id', sa.Integer(), nullable=True),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('chapter_id', sa.Integer(), nullable=True),
    sa.Column('imported_by', sa.Integer(), nullable=True),
    sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('manuel', 'fiche', 'exercices', 'devoir', 'examen', 'corrige', 'revision', 'methode', 'autre')", name='ck_documents_kind'),
    sa.CheckConstraint("status IN ('imported', 'processing', 'extracted', 'failed', 'archived')", name='ck_documents_status'),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['imported_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sha256')
    )
    op.create_table('document_pages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), server_default='', nullable=False),
    sa.Column('method', sa.String(length=10), server_default='text', nullable=False),
    sa.CheckConstraint("method IN ('text', 'ocr', 'empty')", name='ck_document_pages_method'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'page_number', name='uq_document_pages_doc_page')
    )
    op.create_table('exercises',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('page_start', sa.Integer(), nullable=False),
    sa.Column('page_end', sa.Integer(), nullable=False),
    sa.Column('source_number', sa.String(length=50), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('original_text', sa.Text(), nullable=False),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('exercise_type', sa.String(length=20), server_default='libre', nullable=False),
    sa.Column('difficulty', sa.Integer(), server_default='2', nullable=False),
    sa.Column('expected_answer', sa.Text(), nullable=True),
    sa.Column('numeric_tolerance', sa.Float(), nullable=True),
    sa.Column('points', sa.Integer(), server_default='1', nullable=False),
    sa.Column('grade_id', sa.Integer(), nullable=True),
    sa.Column('track_id', sa.Integer(), nullable=True),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('chapter_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='extracted', nullable=False),
    sa.Column('is_published', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_archived', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('validated_by', sa.Integer(), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("exercise_type IN ('libre', 'qcm', 'vrai_faux', 'a_completer', 'numerique', 'probleme', 'etude_de_cas')", name='ck_exercises_type'),
    sa.CheckConstraint("status IN ('extracted', 'transformed', 'pending_validation', 'validated', 'rejected')", name='ck_exercises_status'),
    sa.CheckConstraint('difficulty BETWEEN 1 AND 3', name='ck_exercises_difficulty'),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['validated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exercises_chapter_published', 'exercises', ['chapter_id', 'is_published'], unique=False)
    op.create_table('corrections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('exercise_id', sa.Integer(), nullable=False),
    sa.Column('original_text', sa.Text(), server_default='', nullable=False),
    sa.Column('final_answer', sa.Text(), nullable=True),
    sa.Column('steps', sa.Text(), nullable=True),
    sa.Column('rubric', sa.Text(), nullable=True),
    sa.Column('source_document_id', sa.Integer(), nullable=False),
    sa.Column('source_page', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='extracted', nullable=False),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('extracted', 'transformed', 'pending_validation', 'validated', 'rejected')", name='ck_corrections_status'),
    sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('exercise_id')
    )
    op.create_table('exercise_assets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('exercise_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('storage_key', sa.String(length=500), nullable=True),
    sa.Column('caption', sa.String(length=200), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("kind IN ('page', 'image')", name='ck_exercise_assets_kind'),
    sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('exercise_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('exercise_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=10), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('exercise_options')
    op.drop_table('exercise_assets')
    op.drop_table('corrections')
    op.drop_index('ix_exercises_chapter_published', table_name='exercises')
    op.drop_table('exercises')
    op.drop_table('document_pages')
    op.drop_table('documents')
    op.drop_index('ix_audit_logs_entity', table_name='audit_logs')
    op.drop_table('audit_logs')
