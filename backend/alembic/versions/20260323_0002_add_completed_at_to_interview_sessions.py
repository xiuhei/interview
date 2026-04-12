"""add completed_at to interview sessions

Revision ID: 20260323_0002
Revises: 20260322_0001
Create Date: 2026-03-23 14:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260323_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    interview_sessions = sa.table(
        "interview_sessions",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String(length=50)),
        sa.column("completed_at", sa.DateTime(timezone=True)),
    )
    interview_reports = sa.table(
        "interview_reports",
        sa.column("session_id", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    completed_at_subquery = (
        sa.select(interview_reports.c.created_at)
        .where(interview_reports.c.session_id == interview_sessions.c.id)
        .scalar_subquery()
    )

    op.execute(
        sa.update(interview_sessions)
        .where(interview_sessions.c.status == "completed")
        .where(interview_sessions.c.completed_at.is_(None))
        .values(completed_at=completed_at_subquery)
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "completed_at")
