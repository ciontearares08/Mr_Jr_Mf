import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class FieldRole(str, enum.Enum):
    owner = "owner"
    viewer = "viewer"


class FieldMember(Base):
    __tablename__ = "field_members"

    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[FieldRole] = mapped_column(
        Enum(FieldRole, name="field_role"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
