from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List
from datetime import date, timedelta

from database import get_db
from db.user import User
from db.checkin import DailyCheckin
from routers.auth import get_current_user

router = APIRouter()


class CheckinCreate(BaseModel):
    mood: int | None = Field(default=None, ge=1, le=5)
    weight: float | None = None
    notes: str | None = None


class CheckinResponse(BaseModel):
    id: int
    date: date
    mood: int | None
    weight: float | None
    notes: str | None

    model_config = {"from_attributes": True}


class CheckinStats(BaseModel):
    total_days: int
    streak_days: int
    current_month_days: int
    today_checked: bool


@router.get("/checkins", response_model=List[CheckinResponse])
def list_checkins(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(DailyCheckin).filter(DailyCheckin.user_id == user.id).order_by(DailyCheckin.date.desc()).limit(90).all()


@router.post("/checkins", response_model=CheckinResponse)
def create_checkin(data: CheckinCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    existing = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == user.id,
        DailyCheckin.date == today,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already checked in today")
    checkin = DailyCheckin(user_id=user.id, date=today, **data.model_dump(exclude_unset=True))
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("/checkins/stats", response_model=CheckinStats)
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    checkins = (
        db.query(DailyCheckin)
        .filter(DailyCheckin.user_id == user.id)
        .order_by(DailyCheckin.date.desc())
        .all()
    )
    dates = {c.date for c in checkins}

    total = len(dates)
    current_month = sum(1 for d in dates if d.year == today.year and d.month == today.month)
    today_checked = today in dates

    # Calculate streak
    streak = 0
    d = today if today_checked else today - timedelta(days=1)
    while d in dates:
        streak += 1
        d -= timedelta(days=1)

    return CheckinStats(
        total_days=total,
        streak_days=streak,
        current_month_days=current_month,
        today_checked=today_checked,
    )
