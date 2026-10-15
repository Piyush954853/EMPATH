
"""Add alert handoff assignment and history.

Revision ID: 9dd758618280
Revises: 5ed863845115
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "9dd758618280"
down_revision: Union[str, Sequence[str], None] = "5ed863845115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add alert assignment and permanent handoff history."""

    # SQLite requires batch table recreation to safely add a foreign key.
    # This preserves existing alert records and their existing columns.
    with op.batch_alter_table(
        "alerts",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "assigned_to_user_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_foreign_key(
            "fk_alerts_assigned_to_user_id_users",
            "users",
            ["assigned_to_user_id"],
            ["id"],
        )

        batch_op.create_index(
            "ix_alerts_assigned_to_user_id",
            ["assigned_to_user_id"],
            unique=False,
        )

    # Create history after the alerts table has been updated, so that
    # its foreign key references the final alerts table.
    op.create_table(
        "alert_handoff_history",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=True),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "transferred_by_user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transferred_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_alert_handoff_history_alert_id",
        "alert_handoff_history",
        ["alert_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove handoff history and assignment column."""

    # Drop the referencing table first.
    op.drop_index(
        "ix_alert_handoff_history_alert_id",
        table_name="alert_handoff_history",
    )
    op.drop_table("alert_handoff_history")

    # SQLite batch mode handles dropping the foreign key and column.
    with op.batch_alter_table(
        "alerts",
        recreate="always",
    ) as batch_op:
        batch_op.drop_index("ix_alerts_assigned_to_user_id")
        batch_op.drop_constraint(
            "fk_alerts_assigned_to_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("assigned_to_user_id")
