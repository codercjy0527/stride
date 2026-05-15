from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    training_plans = relationship("TrainingPlan", back_populates="user", cascade="all, delete-orphan")
    checkins = relationship("DailyCheckin", back_populates="user", cascade="all, delete-orphan")
    fitness_metrics = relationship("FitnessMetrics", back_populates="user", cascade="all, delete-orphan")
