"""Lock manual warranty reference uniqueness per branch."""
from alembic import op

revision = "0015_manual_warranty_reference"
down_revision = "0014_audit_immutability"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_unique_constraint("uq_manual_warranty_branch_reference", "manual_warranty_documents", ["branch_id", "reference_no"])

def downgrade() -> None:
    op.drop_constraint("uq_manual_warranty_branch_reference", "manual_warranty_documents", type_="unique")
