"""rework interview style to difficulty

Revision ID: 20260405_0005
Revises: 20260405_0004
Create Date: 2026-04-05 00:55:00
"""

from alembic import op


revision = "20260405_0005"
down_revision = "20260405_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE interview_sessions SET style = 'medium' WHERE style = 'regular'")
    op.execute("UPDATE interview_sessions SET style = 'hard' WHERE style = 'pressure'")
    op.execute("UPDATE interview_sessions SET style = 'simple' WHERE style = 'guided'")

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            """
            ALTER TABLE interview_sessions
            MODIFY COLUMN style ENUM('simple', 'medium', 'hard') NOT NULL
            """
        )


def downgrade() -> None:
    op.execute("UPDATE interview_sessions SET style = 'regular' WHERE style IN ('simple', 'medium')")
    op.execute("UPDATE interview_sessions SET style = 'pressure' WHERE style = 'hard'")

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            """
            ALTER TABLE interview_sessions
            MODIFY COLUMN style ENUM('regular', 'pressure', 'guided') NOT NULL
            """
        )
