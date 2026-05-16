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
from services.philosophies import list_philosophies, get_philosophy

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
    philosophy: str = Field(default="polarised_80_20")


class QuestionnaireInput(BaseModel):
    """护栏约束模式 - 体能评估 + 计划参数"""
    # 体能评估
    fitness_level: str = Field(..., description="beginner / intermediate / advanced")
    training_days_per_week: int = Field(default=4, ge=3, le=7)
    recent_race_result: str | None = Field(default=None, description="近期成绩, 如 5K 22:30")
    injury_notes: str | None = Field(default=None, description="伤病备注")
    # 计划参数
    name: str = "我的训练计划"
    weeks: int = Field(default=12, ge=4, le=24)
    weekly_mileage_cap: float = Field(default=0.10, ge=0.0, le=0.20)
    philosophy: str = Field(default="polarised_80_20")
    target_race: str = "半马"
    target_date: date | None = None
    base_weekly_km: float = Field(default=30.0, ge=10.0, le=150.0)


class PlanUpdate(BaseModel):
    name: str | None = None
    weekly_mileage_cap: float | None = None
    high_intensity_max: int | None = None
    low_intensity_max: int | None = None
    target_race: str | None = None
    target_date: date | None = None
    philosophy: str | None = None


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
    philosophy: str | None = None
    fitness_level: str | None = None
    recent_race_result: str | None = None
    injury_notes: str | None = None
    training_days_per_week: int | None = None
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
    is_checkpoint: bool
    is_blind_run: bool
    checkpoint_result_sec: int | None = None
    checkpoint_notes: str | None = None

    model_config = {"from_attributes": True}


class CheckpointSubmit(BaseModel):
    result_seconds: int = Field(..., description="测试成绩(秒)")
    notes: str | None = None


class CheckpointAnalysis(BaseModel):
    week: int
    current_result_sec: int | None
    previous_result_sec: int | None
    delta_pct: float | None
    previous_week: int | None
    trend: str  # baseline / improving / declining / plateauing
    available_variables: list[str]


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
        philosophy=getattr(plan, 'philosophy', None),
        fitness_level=getattr(plan, 'fitness_level', None),
        recent_race_result=getattr(plan, 'recent_race_result', None),
        injury_notes=getattr(plan, 'injury_notes', None),
        training_days_per_week=getattr(plan, 'training_days_per_week', None),
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


# ─── 护栏约束模式新增端点 ────────────────────────────────────────────


@router.get("/philosophies")
def get_philosophies():
    """列出所有可用训练哲学"""
    return list_philosophies()


@router.post("/training-plans/questionnaire", response_model=PlanResponse)
def create_plan_from_questionnaire(data: QuestionnaireInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """护栏约束模式：体能评估 + 计划创建一步完成"""
    philosophy = get_philosophy(data.philosophy)
    if philosophy is None:
        raise HTTPException(status_code=400, detail=f"未知训练哲学: {data.philosophy}")

    plan = TrainingPlan(
        user_id=user.id,
        name=data.name,
        weeks=data.weeks,
        weekly_mileage_cap=data.weekly_mileage_cap,
        high_intensity_max=philosophy.high_max,
        low_intensity_max=philosophy.low_max,
        target_race=data.target_race,
        target_date=data.target_date,
        philosophy=data.philosophy,
        fitness_level=data.fitness_level,
        recent_race_result=data.recent_race_result,
        injury_notes=data.injury_notes,
        training_days_per_week=data.training_days_per_week,
    )
    db.add(plan)
    db.flush()

    sessions = generate_training_plan(plan, data.base_weekly_km)
    db.add_all(sessions)
    db.commit()
    db.refresh(plan)
    return _plan_to_response(plan)


@router.post("/sessions/{session_id}/checkpoint", response_model=SessionResponse)
def submit_checkpoint(session_id: int, data: CheckpointSubmit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """提交检查点测试成绩"""
    session = db.query(TrainingSession).join(TrainingPlan).filter(
        TrainingSession.id == session_id,
        TrainingPlan.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_checkpoint:
        raise HTTPException(status_code=400, detail="该训练不是检查点")

    session.checkpoint_result_sec = data.result_seconds
    session.checkpoint_notes = data.notes
    session.completed = True
    db.commit()
    db.refresh(session)
    return session


@router.get("/training-plans/{plan_id}/checkpoint/{week}", response_model=CheckpointAnalysis)
def get_checkpoint_analysis(plan_id: int, week: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取检查点分析：本次 vs 上次对比 + 可调整变量"""
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    philosophy = get_philosophy(plan.philosophy or "polarised_80_20")

    # 找当前检查点
    current_sessions = db.query(TrainingSession).filter(
        TrainingSession.plan_id == plan_id,
        TrainingSession.week == week,
        TrainingSession.is_checkpoint == True,
    ).all()

    # 找之前所有检查点（按周逆序）
    prev_sessions = db.query(TrainingSession).filter(
        TrainingSession.plan_id == plan_id,
        TrainingSession.is_checkpoint == True,
        TrainingSession.week < week,
        TrainingSession.checkpoint_result_sec.isnot(None),
    ).order_by(TrainingSession.week.desc()).all()

    current_result = current_sessions[0].checkpoint_result_sec if current_sessions else None
    prev_result = prev_sessions[0].checkpoint_result_sec if prev_sessions else None
    prev_week = prev_sessions[0].week if prev_sessions else None

    delta_pct = None
    trend = "baseline"
    if current_result and prev_result:
        delta_pct = round((prev_result - current_result) / prev_result * 100, 1)
        if delta_pct > 1:
            trend = "improving"
        elif delta_pct < -1:
            trend = "declining"
        else:
            trend = "plateauing"

    available_variables = [
        "weekly_volume",
        "intensity_distribution",
        "long_run_distance",
        "recovery_days",
        "session_pace",
    ]

    return CheckpointAnalysis(
        week=week,
        current_result_sec=current_result,
        previous_result_sec=prev_result,
        delta_pct=delta_pct,
        previous_week=prev_week,
        trend=trend,
        available_variables=available_variables,
    )


class CheckpointAIAnalysisRequest(BaseModel):
    provider: str = "deepseek"
    api_key: str = ""
    model: str = ""


@router.post("/training-plans/{plan_id}/checkpoint/{week}/ai")
async def get_checkpoint_ai_analysis(
    plan_id: int, week: int, data: CheckpointAIAnalysisRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """AI分析检查点结果，给出单变量调整建议"""
    from services.ai_coach import analyze_checkpoint
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id, TrainingPlan.user_id == user.id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    current_sessions = db.query(TrainingSession).filter(
        TrainingSession.plan_id == plan_id,
        TrainingSession.week == week,
        TrainingSession.is_checkpoint == True,
    ).all()

    prev_sessions = db.query(TrainingSession).filter(
        TrainingSession.plan_id == plan_id,
        TrainingSession.is_checkpoint == True,
        TrainingSession.week < week,
        TrainingSession.checkpoint_result_sec.isnot(None),
    ).order_by(TrainingSession.week.desc()).all()

    current_result = current_sessions[0].checkpoint_result_sec if current_sessions else None
    prev_result = prev_sessions[0].checkpoint_result_sec if prev_sessions else None

    delta_pct = None
    trend = "baseline"
    if current_result and prev_result:
        delta_pct = round((prev_result - current_result) / prev_result * 100, 1)
        if delta_pct > 1:
            trend = "improving"
        elif delta_pct < -1:
            trend = "declining"
        else:
            trend = "plateauing"

    if not current_result:
        raise HTTPException(status_code=400, detail="该检查点尚未提交成绩")

    reply = await analyze_checkpoint(
        user=user, plan=plan, checkpoint_week=week,
        current_result_sec=current_result,
        previous_result_sec=prev_result,
        delta_pct=delta_pct, trend=trend,
        db=db, provider=data.provider, api_key=data.api_key, model=data.model,
    )
    return {"reply": reply, "trend": trend, "delta_pct": delta_pct}
