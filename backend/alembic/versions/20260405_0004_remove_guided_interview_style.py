"""remove guided interview style

Revision ID: 20260405_0004
Revises: 20260325_0003_add_analysis_jobs
Create Date: 2026-04-05 00:05:00
"""

from alembic import op


revision = "20260405_0004"
down_revision = "20260325_0003_add_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.execute("UPDATE interview_sessions SET style = 'regular' WHERE style = 'guided'")

    if dialect == "mysql":
        op.execute(
            """
            ALTER TABLE interview_sessions
            MODIFY COLUMN style ENUM('regular', 'pressure') NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            """
            ALTER TABLE interview_sessions
            MODIFY COLUMN style ENUM('regular', 'pressure', 'guided') NOT NULL
            """
        )
