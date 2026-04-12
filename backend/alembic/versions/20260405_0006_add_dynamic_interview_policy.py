"""add dynamic interview policy fields

Revision ID: 20260405_0006
Revises: 20260405_0005
Create Date: 2026-04-05 16:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0006"
down_revision = "20260405_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("min_questions", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("early_reject_score_threshold", sa.Float(), nullable=False, server_default="30"),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("early_accept_score_threshold", sa.Float(), nullable=False, server_default="75"),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("end_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("end_decided_by", sa.String(length=32), nullable=True),
    )

    op.execute("UPDATE interview_sessions SET min_questions = 3 WHERE min_questions IS NULL OR min_questions < 3")
    op.execute("UPDATE interview_sessions SET max_questions = 7 WHERE max_questions IS NULL OR max_questions > 7")
    op.execute("UPDATE interview_sessions SET max_questions = 7 WHERE max_questions < 3")

    op.alter_column("interview_sessions", "min_questions", server_default=None)
    op.alter_column("interview_sessions", "early_reject_score_threshold", server_default=None)
    op.alter_column("interview_sessions", "early_accept_score_threshold", server_default=None)


def downgrade() -> None:
    op.drop_column("interview_sessions", "end_decided_by")
    op.drop_column("interview_sessions", "end_reason")
    op.drop_column("interview_sessions", "early_accept_score_threshold")
    op.drop_column("interview_sessions", "early_reject_score_threshold")
    op.drop_column("interview_sessions", "min_questions")
