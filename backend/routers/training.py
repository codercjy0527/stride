from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List
from datetime import date

from database import get_db
from db.user import User
from db.training import TrainingPlan, TrainingSession, SessionType, Intensity
from routers.auth import get_current_user
from services.plan_generator import generate_training_plan

router = APIRouter()


class PlanCreate(BaseModel):
    name: str
    weeks: int = Field(default=12, ge=4, le=24)
    weekly_mileage_cap: float = Field(default=0.10, ge=0.0, le=0.20)
    high_intensity_max: int = Field(default=2, ge=1, le=3)
    low_intensity_max: int = Field(default=4, ge=2, le=6)
    target_race: str = "半马"
    target_date: date | None = None
    base_weekly_km: float = Field(default=30.0)


class PlanUpdate(BaseModel):
    name: str | None = None
    weekly_mileage_cap: float | None = None
    high_intensity_max: int | None = None
    low_intensity_max: int | None = None
    target_race: str | None = None
    target_date: date | None = None


class PlanResponse(BaseModel):
    id: int
    user_id: int
    name: str
    weeks: int
    weekly_mileage_cap: float
    high_intensity_max: int
    low_intensity_max: int
    target_race: str
    target_date: date | None
    total_sessions: int
    completed_sessions: int

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: int
    plan_id: int
    week: int
    day_of_week: int
    session_type: SessionType
    intensity: Intensity
    duration_min: int
    distance_km: float
    description: str
    completed: bool

    model_config = {"from_attributes": True}


def _plan_to_response(plan: TrainingPlan) -> PlanResponse:
    sessions = plan.sessions or []
    total = len(sessions)
    completed = sum(1 for s in sessions if s.completed)
    return PlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        name=plan.name,
        weeks=plan.weeks,
        weekly_mileage_cap=plan.weekly_mileage_cap,
        high_intensity_max=plan.high_intensity_max,
        low_intensity_max=plan.low_intensity_max,
        target_race=plan.target_race,
        target_date=plan.target_date,
        total_sessions=total,
        completed_sessions=completed,
    )


@router.get("/training-plans", response_model=List[PlanResponse])
def list_plans(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plans = db.query(TrainingPlan).filter(TrainingPlan.user_id == user.id).all()
    return [_plan_to_response(p) for p in plans]


@router.post("/training-plans", response_model=PlanResponse)
def create_plan(data: PlanCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = TrainingPlan(
        user_id=user.id,
        name=data.name,
        weeks=data.weeks,
        weekly_mileage_cap=data.weekly_mileage_cap,
        high_intensity_max=data.high_intensity_max,
        low_intensity_max=data.low_intensity_max,
        target_race=data.target_race,
        target_date=data.target_date,
    )
    db.add(plan)
    db.flush()

    sessions = generate_training_plan(plan, data.base_weekly_km)
    db.add_all(sessions)
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


@router.get("/training-plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(plan)


@router.put("/training-plans/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: int, data: PlanUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


@router.delete("/training-plans/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/training-plans/{plan_id}/generate")
def regenerate_plan(plan_id: int, base_weekly_km: float = 30.0, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    # Delete old sessions
    db.query(TrainingSession).filter(TrainingSession.plan_id == plan.id).delete()
    sessions = generate_training_plan(plan, base_weekly_km)
    db.add_all(sessions)
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


@router.get("/training-plans/{plan_id}/sessions", response_model=List[SessionResponse])
def list_sessions(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan.sessions


@router.put("/sessions/{session_id}/complete", response_model=SessionResponse)
def complete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.query(TrainingSession).join(TrainingPlan).filter(
        TrainingSession.id == session_id,
        TrainingPlan.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.completed = not session.completed
    db.commit()
    db.refresh(session)
    return session
