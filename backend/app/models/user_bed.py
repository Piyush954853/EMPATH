from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserBed(Base):
    __tablename__ = "user_beds"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    bed_id: Mapped[int] = mapped_column(
        ForeignKey("beds.id"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "bed_id",
            name="uq_user_bed",
        ),
    )