from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # Event that triggered this alert.
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    # Alert priority: high, medium, low, etc.
    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Alert lifecycle: active, acknowledged, resolved, dismissed.
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )

    # Short alert heading.
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Original alert message from the event/AI workflow.
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # AI-generated incident summary.
    # Nullable so existing alerts continue to work.
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Nurse currently responsible for this alert.
    # Nullable to support unassigned and existing alerts.
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # Acknowledgement tracking.
    acknowledged_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Resolution tracking.
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Dismissal audit tracking.
    # Nullable to preserve existing alerts.
    dismissed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Alert creation timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )