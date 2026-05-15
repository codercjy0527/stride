from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class CorosToken(Base):
    __tablename__ = "coros_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    openid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cookie: Mapped[str | None] = mapped_column(Text, nullable=True)
    coros_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coros_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    coros_region: Mapped[str | None] = mapped_column(String(10), default="cn")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
