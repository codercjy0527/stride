from datetime import date, datetime
from enum import Enum

from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class SessionType(str, Enum):
    easy = "easy"
    tempo = "tempo"
    interval = "interval"
    long_run = "long_run"
    rest = "rest"
    checkpoint = "checkpoint"
    fartlek = "fartlek"
    hills = "hills"


class Intensity(str, Enum):
    low = "low"
    high = "high"


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    weeks: Mapped[int] = mapped_column(Integer, default=12)
    weekly_mileage_cap: Mapped[float] = mapped_column(Float, default=0.10)
    high_intensity_max: Mapped[int] = mapped_column(Integer, default=2)
    low_intensity_max: Mapped[int] = mapped_column(Integer, default=4)
    target_race: Mapped[str] = mapped_column(String(20), default="半马")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    philosophy: Mapped[str] = mapped_column(String(30), default="polarised_80_20")
    fitness_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recent_race_result: Mapped[str | None] = mapped_column(String(100), nullable=True)
    injury_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    training_days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="training_plans")
    sessions = relationship("TrainingSession", back_populates="plan", cascade="all, delete-orphan")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 6=Sun
    session_type: Mapped[SessionType] = mapped_column(SAEnum(SessionType), nullable=False)
    intensity: Mapped[Intensity] = mapped_column(SAEnum(Intensity), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(String(500), default="")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_checkpoint: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blind_run: Mapped[bool] = mapped_column(Boolean, default=False)
    checkpoint_result_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkpoint_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    plan = relationship("TrainingPlan", back_populates="sessions")
