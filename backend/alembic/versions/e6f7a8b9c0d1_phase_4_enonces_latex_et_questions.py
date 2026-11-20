"""Phase 4 : énoncés et corrigés réécrits en LaTeX, questions séparées et réponses par question.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-11-20 08:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "rewrite_status IN ('none', 'ok', 'doubtful', 'failed')"


def upgrade() -> None:
    with op.batch_alter_table('exercises') as batch:
        batch.add_column(sa.Column('statement_latex', sa.Text(), nullable=True))
        batch.add_column(sa.Column('rewrite_status', sa.String(length=12), server_default='none', nullable=False))
        batch.add_column(sa.Column('rewrite_model', sa.String(length=80), nullable=True))
        batch.add_column(sa.Column('rewritten_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint('ck_exercises_rewrite_status', STATUSES)
    with op.batch_alter_table('corrections') as batch:
        batch.add_column(sa.Column('text_latex', sa.Text(), nullable=True))
        batch.add_column(sa.Column('rewrite_status', sa.String(length=12), server_default='none', nullable=False))

    op.create_table(
        'exercise_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(length=10), server_default='result', nullable=False),
        sa.Column('expected_answer', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.CheckConstraint("kind IN ('result', 'proof')", name='ck_exercise_questions_kind'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exercise_questions_exercise_id', 'exercise_questions', ['exercise_id'])
    op.create_table(
        'question_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer_latex', sa.Text(), nullable=True),
        sa.Column('result', sa.String(length=12), nullable=False),
        sa.Column('after_correction', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("result IN ('correct', 'incorrect', 'submitted', 'self_ok', 'self_review')",
                           name='ck_question_attempts_result'),
        sa.ForeignKeyConstraint(['question_id'], ['exercise_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_question_attempts_user_question', 'question_attempts', ['user_id', 'question_id'])


def downgrade() -> None:
    op.drop_index('ix_question_attempts_user_question', table_name='question_attempts')
    op.drop_table('question_attempts')
    op.drop_index('ix_exercise_questions_exercise_id', table_name='exercise_questions')
    op.drop_table('exercise_questions')
    with op.batch_alter_table('corrections') as batch:
        batch.drop_column('rewrite_status')
        batch.drop_column('text_latex')
    with op.batch_alter_table('exercises') as batch:
        batch.drop_constraint('ck_exercises_rewrite_status', type_='check')
        batch.drop_column('rewritten_at')
        batch.drop_column('rewrite_model')
        batch.drop_column('rewrite_status')
        batch.drop_column('statement_latex')
