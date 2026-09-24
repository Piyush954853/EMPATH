from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserWard(Base):
    __tablename__ = "user_wards"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    ward_id: Mapped[int] = mapped_column(
        ForeignKey("wards.id"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "ward_id",
            name="uq_user_ward",
        ),
    )