"""add analysis jobs

Revision ID: 20260325_0003
Revises: 20260323_0002
Create Date: 2026-03-25 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260325_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = sa.Enum("pending", "processing", "success", "failed", "dead", name="analysisjobstatus")
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("current_stage", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("stage_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name=op.f("fk_analysis_jobs_session_id_interview_sessions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_jobs")),
        sa.UniqueConstraint("session_id", "version", name="uq_analysis_jobs_session_id_version"),
    )
    op.create_index(op.f("ix_analysis_jobs_session_id"), "analysis_jobs", ["session_id"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_status"), "analysis_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_next_retry_at"), "analysis_jobs", ["next_retry_at"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_fingerprint"), "analysis_jobs", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_analysis_jobs_idempotency_key"), "analysis_jobs", ["idempotency_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_jobs_idempotency_key"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_fingerprint"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_next_retry_at"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_status"), table_name="analysis_jobs")
    op.drop_index(op.f("ix_analysis_jobs_session_id"), table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    status_enum = sa.Enum("pending", "processing", "success", "failed", "dead", name="analysisjobstatus")
    status_enum.drop(op.get_bind(), checkfirst=True)
