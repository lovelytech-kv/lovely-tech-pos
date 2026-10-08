"""Add timestamps to permissions.

Revision ID: 0025_permission_timestamps
Revises: 0024_reload_once_per_day
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_permission_timestamps"
down_revision = "0024_reload_once_per_day"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "permissions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "permissions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE permissions
            SET
                created_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
               OR updated_at IS NULL
            """
        )
    )

    op.alter_column(
        "permissions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "permissions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.drop_column("permissions", "updated_at")
    op.drop_column("permissions", "created_at")