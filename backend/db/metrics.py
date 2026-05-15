from datetime import date

from sqlalchemy import Integer, Float, Date, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class FitnessMetrics(Base):
    __tablename__ = "fitness_metrics"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_metrics_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Basic health
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fatigue_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Advanced metrics
    vo2max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lthr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ltsp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stamina_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    stamina_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_load_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Sleep phases
    deep_sleep_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_sleep_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_sleep_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_avg_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_min_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Stress / Recovery
    tired_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ati: Mapped[float | None] = mapped_column(Float, nullable=True)
    cti: Mapped[float | None] = mapped_column(Float, nullable=True)

    user = relationship("User", back_populates="fitness_metrics")
