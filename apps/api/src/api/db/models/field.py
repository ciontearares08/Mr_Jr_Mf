from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    area_hectares: Mapped[float] = mapped_column(nullable=False)