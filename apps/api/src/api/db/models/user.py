import datetime
import uuid

from pydantic import validate_email
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())