"""Add updated_at to return_payments.

Revision ID: 0026_return_payment_timestamps
Revises: 0025_permission_timestamps
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_return_payment_timestamps"
down_revision = "0025_permission_timestamps"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "return_payments",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE return_payments
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        )
    )

    op.alter_column(
        "return_payments",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.drop_column("return_payments", "updated_at")
