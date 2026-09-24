"""Link user to role

Revision ID: 26f7c8af5f0e
Revises: 75f687f8c814
Create Date: 2026-09-23 20:48:10.109793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "26f7c8af5f0e"
down_revision: Union[str, Sequence[str], None] = "75f687f8c814"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role_id", sa.Integer(), nullable=False)
        )
        batch_op.create_foreign_key(
            "fk_users_role_id_roles",
            "roles",
            ["role_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_users_role_id_roles",
            type_="foreignkey",
        )
        batch_op.drop_column("role_id")