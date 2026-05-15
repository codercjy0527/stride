from datetime import date

from sqlalchemy import String, Integer, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user = relationship("User", back_populates="checkins")
