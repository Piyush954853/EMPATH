"""Add event create permission

Revision ID: 5ed863845115
Revises: f1f8f792cc69
Create Date: 2026-09-24 19:59:46.507284

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5ed863845115"
down_revision: Union[str, Sequence[str], None] = "f1f8f792cc69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
    )

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    op.bulk_insert(
        permissions_table,
        [
            {
                "id": 23,
                "name": "events.create",
                "description": "Create monitoring events",
                "is_active": True,
            }
        ],
    )

    op.bulk_insert(
        role_permissions_table,
        [
            {
                "role_id": 1,
                "permission_id": 23,
            },
            {
                "role_id": 2,
                "permission_id": 23,
            },
        ],
    )


def downgrade() -> None:
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
    )

    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.permission_id == 23
        )
    )

    op.execute(
        permissions_table.delete().where(
            permissions_table.c.id == 23
        )
    )