from datetime import date, datetime, timezone

from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ActivityRecord(Base):
    __tablename__ = "activity_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    label_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    sport_type: Mapped[int] = mapped_column(Integer, default=100)
    sport_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_pace: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_load: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elevation_gain: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_stride_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON data
    hr_zones: Mapped[str | None] = mapped_column(Text, nullable=True)
    pace_zones: Mapped[str | None] = mapped_column(Text, nullable=True)
    laps: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
