"""Persist immutable target progress history when target periods complete."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_target_progress_snapshots"
down_revision = "0020_warranty_rule_snapshot"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "target_progress_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("targets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("achieved_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(18, 4), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("target_id", "target_version", name="uq_target_progress_snapshot_version"),
    )
    op.create_index("ix_target_snapshots_branch_period", "target_progress_snapshots", ["branch_id", "period_start", "period_end"])

def downgrade() -> None:
    op.drop_index("ix_target_snapshots_branch_period", table_name="target_progress_snapshots")
    op.drop_table("target_progress_snapshots")
