
"""add alert dismissal audit fields

Revision ID: 90a1de6d2714
Revises: 473239139363
Create Date: 2026-10-14 13:30:18.345524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90a1de6d2714"
down_revision: Union[str, Sequence[str], None] = "473239139363"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable audit fields for alert dismissal."""

    # Batch mode supports SQLite's foreign-key constraint changes.
    # Existing alert records are retained; both new fields are nullable.
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "dismissed_by",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "dismissed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

        batch_op.create_foreign_key(
            "fk_alerts_dismissed_by_users",
            "users",
            ["dismissed_by"],
            ["id"],
        )


def downgrade() -> None:
    """Remove the dismissal audit fields."""

    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_alerts_dismissed_by_users",
            type_="foreignkey",
        )
        batch_op.drop_column("dismissed_at")
        batch_op.drop_column("dismissed_by")
