"""Snapshot warranty duration/custom rule on product warranties."""
from alembic import op
import sqlalchemy as sa

revision = "0020_warranty_rule_snapshot"
down_revision = "0019_manual_warranty_unique"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("product_warranties", sa.Column("duration_value", sa.Integer(), nullable=True))
    op.add_column("product_warranties", sa.Column("custom_rule", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("product_warranties", "custom_rule")
    op.drop_column("product_warranties", "duration_value")
