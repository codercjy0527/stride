from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional
import secrets, logging

from database import get_db
from db.user import User
from db.coros_token import CorosToken
from db.metrics import FitnessMetrics
from db.activity import ActivityRecord
from routers.auth import get_current_user
from services.coros_sync import get_daily_adjustment
from services.coros_api import (
    generate_pkce_pair, get_authorization_url, exchange_code,
    sync_health_to_metrics, fetch_activities, fetch_training_plans,
    import_coros_plan, fetch_athlete_profile,
)
from services.coros_web import test_cookie, sync_all_to_metrics, login_via_web
from services.coros_mcp_cli import sync_all as mcp_sync_all
from config import COROS_CLIENT_ID, COROS_REDIRECT_URI

router = APIRouter()

# In-memory PKCE store (key: state, value: code_verifier)
_pkce_store: dict[str, tuple[str, str]] = {}


class MetricsInput(BaseModel):
    date: Optional[date] = None
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    resting_hr: Optional[int] = Field(default=None, ge=30, le=100)
    hrv: Optional[int] = Field(default=None, ge=10, le=200)
    fatigue_score: Optional[float] = Field(default=None, ge=0, le=100)
    recovery_score: Optional[float] = Field(default=None, ge=0, le=100)


class MetricsResponse(BaseModel):
    id: int
    date: date
    sleep_hours: float | None
    sleep_quality: int | None
    resting_hr: int | None
    hrv: int | None
    fatigue_score: float | None
    recovery_score: float | None

    model_config = {"from_attributes": True, "json_encoders": {date: lambda d: d.isoformat()}}


# ── OAuth 授权流程 ──

@router.get("/auth/url")
def get_coros_auth_url(
    user: User = Depends(get_current_user),
    redirect_uri: str = Query(default=""),
):
    """获取 COROS OAuth 授权 URL。用户浏览器跳转到此 URL 完成授权。"""
    if not COROS_CLIENT_ID:
        raise HTTPException(status_code=400, detail="未配置 COROS_CLIENT_ID，请在环境变量中设置")

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    _pkce_store[state] = (code_verifier, str(user.id))

    auth_url = get_authorization_url(state, code_challenge, redirect_uri or COROS_REDIRECT_URI)
    return {"url": auth_url, "state": state}


@router.post("/auth/callback")
def coros_auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """COROS OAuth 回调：用 code 换取 token 并保存"""
    if state not in _pkce_store:
        raise HTTPException(status_code=400, detail="Invalid state")

    code_verifier, stored_user_id = _pkce_store.pop(state)

    try:
        token_data = exchange_code(code, code_verifier, redirect_uri or COROS_REDIRECT_URI)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    expires_in = token_data.get("expires_in", 7200)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(seconds=expires_in)

    existing = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data["refresh_token"]
        existing.openid = token_data.get("openid")
        existing.expires_at = expires_at
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        t = CorosToken(
            user_id=user.id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            openid=token_data.get("openid"),
            expires_at=expires_at,
        )
        db.add(t)

    db.commit()
    return {"ok": True, "message": "COROS 授权成功"}


@router.get("/auth/status")
def coros_auth_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """检查 COROS 授权状态"""
    token = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if not token:
        return {"connected": False}
    return {
        "connected": True,
        "openid": token.openid,
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
    }


@router.delete("/auth/disconnect")
def coros_disconnect(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """断开 COROS 账号连接"""
    token = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if token:
        db.delete(token)
        db.commit()
    return {"ok": True}


# ── COROS 账号凭据 (用户自行绑定) ──

class CredentialInput(BaseModel):
    email: str
    password: str
    region: str = "cn"


@router.post("/credentials")
def save_credentials(
    data: CredentialInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存 COROS 账号密码（本地加密存储）"""
    from services.license import _simple_encrypt
    t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    enc_pw = _simple_encrypt(data.password)
    if t:
        t.coros_email = data.email
        t.coros_password_enc = enc_pw
        t.coros_region = data.region
        t.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        t = CorosToken(
            user_id=user.id,
            coros_email=data.email,
            coros_password_enc=enc_pw,
            coros_region=data.region,
            access_token="",
            refresh_token="",
        )
        db.add(t)
    db.commit()
    return {"ok": True, "message": "COROS 账号已保存"}


@router.get("/credentials")
def get_credential_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查看是否已配置 COROS 账号"""
    t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if t and t.coros_email and t.coros_password_enc:
        return {"configured": True, "email": t.coros_email, "region": t.coros_region or "cn"}
    return {"configured": False, "email": "", "region": "cn"}


# ── Cookie 方案 ──

class CookieInput(BaseModel):
    cookie: str


@router.post("/save-cookie")
def save_cookie(
    data: CookieInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存 COROS 网页版 Cookie 实现自动同步"""
    t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if t:
        t.cookie = data.cookie
        t.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        t = CorosToken(user_id=user.id, cookie=data.cookie, access_token="", refresh_token="")
        db.add(t)
    db.commit()
    return {"ok": True, "message": "Cookie 已保存"}


class LoginInput(BaseModel):
    email: str
    password: str
    region: str = "cn"


@router.post("/auto-login")
async def auto_login(
    data: LoginInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """登录 COROS：保存凭证，并行尝试原生 API + Web Cookie 登录（最多 12 秒）。"""
    import asyncio as aio
    from services.license import _simple_encrypt

    # 1. Detect account change — clear old data if email changed
    t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    old_email = t.coros_email if t else None
    if old_email and old_email != data.email:
        # Coros account switched → clear all old data to avoid mixing accounts
        db.query(FitnessMetrics).filter(FitnessMetrics.user_id == user.id).delete()
        db.query(ActivityRecord).filter(ActivityRecord.user_id == user.id).delete()
        db.commit()

    enc_pw = _simple_encrypt(data.password)
    if t:
        t.coros_email = data.email
        t.coros_password_enc = enc_pw
        t.coros_region = data.region
        t.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        t = CorosToken(
            user_id=user.id,
            coros_email=data.email,
            coros_password_enc=enc_pw,
            coros_region=data.region,
            access_token="",
            refresh_token="",
        )
        db.add(t)
    db.commit()

    # 2. Try both login methods in parallel (12s total timeout)
    native_ok = False
    native_msg = ""
    cookie_ok = False
    cookie_msg = ""

    async def try_native():
        nonlocal native_ok, native_msg
        try:
            import coros_api
            auth = await aio.wait_for(coros_api.login(data.email, data.password, data.region), timeout=10)
            if auth:
                native_ok = True
                native_msg = "原生 API 认证成功"
                try:
                    profile = await aio.wait_for(coros_api.fetch_athlete_profile(auth), timeout=5)
                    if profile:
                        native_msg += f" ({profile.get('nickname') or profile.get('name', '')})"
                except Exception:
                    pass
        except ImportError:
            native_msg = "coros-training-mcp 未安装，已保存凭证"
        except aio.TimeoutError:
            native_msg = "原生 API 连接超时，请检查网络"
        except Exception as e:
            native_msg = f"原生 API 登录失败: {str(e)[:80]}"

    async def try_web():
        nonlocal cookie_ok, cookie_msg
        try:
            web_result = await aio.to_thread(login_via_web, data.email, data.password, data.region)
            if web_result.get("ok"):
                # Re-query token since we're in a different async context
                t2 = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
                if t2:
                    t2.cookie = web_result["cookie"]
                    db.commit()
                cookie_ok = True
                cookie_msg = "Cookie 已保存"
            else:
                cookie_msg = web_result.get("message", "Cookie 获取失败")[:80]
        except Exception as e:
            cookie_msg = f"Cookie 登录失败: {str(e)[:80]}"

    try:
        await aio.wait_for(aio.gather(try_native(), try_web()), timeout=12)
    except aio.TimeoutError:
        if not native_msg:
            native_msg = "登录超时"
        if not cookie_msg:
            cookie_msg = "登录超时"

    return {
        "ok": native_ok or cookie_ok,
        "native_ok": native_ok,
        "native_msg": native_msg,
        "cookie_ok": cookie_ok,
        "cookie_msg": cookie_msg,
        "message": native_msg if native_ok else (cookie_msg if cookie_ok else "登录失败"),
    }


@router.post("/test-cookie")
async def test_cookie_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """测试 Cookie 是否有效"""
    result = await test_cookie(user.id, db)
    return result


# ── 数据同步 ──

@router.post("/sync")
async def sync_coros_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """同步 COROS 数据（优先 MCP CLI，其次 Cookie，最后 OAuth）"""
    # 1. Try coros-mcp CLI (installed globally)
    try:
        result = mcp_sync_all(user, db)
        if result.get("imported") or result.get("recovery"):
            return {"ok": True, **result}
    except Exception as e:
        logging.getLogger("stride").warning(f"MCP sync unavailable: {e}")

    # 2. Try cookie-based web sync
    t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    if t and t.cookie:
        try:
            result = await sync_all_to_metrics(user.id, db)
            if "error" not in result:
                return result
        except Exception as e:
            logging.getLogger("stride").warning(f"Cookie sync failed: {e}")

    # 3. Fallback to OAuth
    try:
        count = sync_health_to_metrics(user, db)
        return {"ok": True, "synced": count, "message": f"成功从 COROS 同步 {count} 条数据"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/activities")
def get_coros_activities(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取 COROS 跑步活动列表"""
    activities = fetch_activities(user.id, db, days=days)
    return {"activities": activities, "count": len(activities)}


# ── 训练计划导入 ──

@router.get("/plans")
def list_coros_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取 COROS 训练计划列表"""
    plans = fetch_training_plans(user.id, db)
    return {"plans": plans, "count": len(plans)}


@router.post("/plans/import")
def import_plan(
    plan_index: int = Query(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导入 COROS 训练计划到本地"""
    plans = fetch_training_plans(user.id, db)
    if plan_index >= len(plans):
        raise HTTPException(status_code=400, detail="Invalid plan index")
    plan_data = plans[plan_index]
    local_plan = import_coros_plan(user, plan_data, db)
    from db.training import TrainingSession
    sessions = db.query(TrainingSession).filter(TrainingSession.plan_id == local_plan.id).count() if local_plan else 0
    return {
        "ok": True,
        "plan": {
            "id": local_plan.id if local_plan else None,
            "name": local_plan.name if local_plan else "",
            "weeks": local_plan.weeks if local_plan else 0,
            "sessions": sessions,
        },
    }


# ── 手动录入 (保留) ──

@router.post("/manual", response_model=MetricsResponse)
def manual_entry(data: MetricsInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry_date = data.date or date.today()
    existing = db.query(FitnessMetrics).filter(
        FitnessMetrics.user_id == user.id,
        FitnessMetrics.date == entry_date,
    ).first()
    if existing:
        for key, value in data.model_dump(exclude_unset=True, exclude={"date"}).items():
            if value is not None:
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        metric = FitnessMetrics(
            user_id=user.id, date=entry_date,
            **data.model_dump(exclude_unset=True, exclude={"date"}),
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        return metric


# ── CSV 导入 ──

@router.post("/import/activities")
def import_activities_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导入活动 CSV（多平台自动识别：Garmin/Apple/华为/小米/Keep/悦跑圈）"""
    from services.csv_importer import CsvImporter

    content = file.file.read().decode("utf-8-sig")
    imp = CsvImporter(content)
    imp.detect_and_parse()

    imported = 0
    skipped = 0

    import hashlib
    for act in imp.activities:
        try:
            d = act.get("date")
            if not d:
                skipped += 1
                continue
            # Generate unique label_id for dedup
            row_key = f"csv_{d}_{act.get('distance_km', 0)}_{act.get('duration_sec', 0)}"
            label_id = "csv_" + hashlib.md5(row_key.encode()).hexdigest()[:16]
            # Skip if already imported
            if db.query(ActivityRecord).filter(ActivityRecord.label_id == label_id).first():
                skipped += 1
                continue
            db.add(ActivityRecord(
                user_id=user.id,
                label_id=label_id,
                activity_date=date.fromisoformat(d) if isinstance(d, str) else d,
                sport_type=act.get("sport_type", 100),
                location=act.get("location"),
                duration_sec=act.get("duration_sec"),
                distance_km=act.get("distance_km"),
                avg_pace=act.get("avg_pace"),
                avg_hr=act.get("avg_hr"),
                calories=act.get("calories"),
            ))
            imported += 1
        except Exception:
            skipped += 1

    db.commit()
    return {
        "ok": True,
        "format": imp.format,
        "imported": imported,
        "skipped": skipped,
        "errors": imp.errors[:5],
        "message": f"识别为 {imp.format} 格式，导入 {imported} 条活动记录",
    }


@router.post("/import/health")
def import_health_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导入健康数据 CSV"""
    from services.csv_importer import CsvImporter

    content = file.file.read().decode("utf-8-sig")
    imp = CsvImporter(content)
    imp.detect_and_parse()

    imported = 0
    for rec in imp.health_records:
        try:
            d = rec.get("date")
            if not d:
                continue
            d_obj = date.fromisoformat(d) if isinstance(d, str) else d
            existing = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user.id, FitnessMetrics.date == d_obj,
            ).first()
            fields = {k: v for k, v in rec.items() if k != "date" and v is not None}
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                db.add(FitnessMetrics(user_id=user.id, date=d_obj, **fields))
            imported += 1
        except Exception:
            pass

    db.commit()
    return {
        "ok": True,
        "format": imp.format,
        "imported": imported,
        "errors": imp.errors[:5],
        "message": f"导入 {imported} 条健康数据",
    }


# ── 旧 CSV 导入 (保留兼容) ──

@router.post("/import-csv")
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import csv, io
    content = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    for row in reader:
        try:
            row_date = _parse_csv_date(row)
            if not row_date:
                continue
            existing = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user.id, FitnessMetrics.date == row_date,
            ).first()
            metrics_data = {
                "sleep_hours": _parse_float(row, ["sleep_hours", "睡眠时长", "sleep"]),
                "sleep_quality": _parse_int(row, ["sleep_quality", "睡眠质量"]),
                "resting_hr": _parse_int(row, ["resting_hr", "静息心率", "Resting HR"]),
                "hrv": _parse_int(row, ["hrv", "HRV"]),
                "fatigue_score": _parse_float(row, ["fatigue_score", "疲劳度"]),
                "recovery_score": _parse_float(row, ["recovery_score", "恢复度"]),
            }
            metrics_data = {k: v for k, v in metrics_data.items() if v is not None}
            if existing:
                for k, v in metrics_data.items():
                    setattr(existing, k, v)
            else:
                db.add(FitnessMetrics(user_id=user.id, date=row_date, **metrics_data))
            imported += 1
        except Exception:
            continue
    db.commit()
    return {"ok": True, "imported": imported, "message": f"成功导入 {imported} 条数据"}


# ── Fitness Assessment ──

@router.get("/fitness-assessment")
async def get_fitness_assessment(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get COROS fitness assessment: VO2max, running level, threshold pace, race predictions."""
    # Try native API first
    try:
        from services.coros_mcp_cli import _get_coros_client
        auth = _get_coros_client(user_id=user.id, db=db)
        if auth:
            import coros_api
            from services.coros_mcp_cli import asyncio_run
            profile = asyncio_run(coros_api.fetch_athlete_profile(auth))
            if profile:
                return {
                    "vo2max": profile.get("vo2max"),
                    "running_level": profile.get("runningLevel") or profile.get("running_level"),
                    "threshold_pace": profile.get("thresholdPace") or profile.get("threshold_pace"),
                    "race_predictions": {
                        "5k": profile.get("predict5k") or profile.get("predict_5k"),
                        "10k": profile.get("predict10k") or profile.get("predict_10k"),
                        "half_marathon": profile.get("predictHalf") or profile.get("predict_half"),
                        "marathon": profile.get("predictMarathon") or profile.get("predict_marathon"),
                    },
                }
    except Exception:
        pass

    # Fallback: legacy CLI
    try:
        from services.coros_mcp_cli import _fallback_cli_call
        text = _fallback_cli_call("queryFitnessAssessmentOverview")
        if text:
            import re, json
            result = {
                "vo2max": None, "running_level": None,
                "threshold_pace": None, "race_predictions": {},
            }
            m = re.search(r'VO2[ _]?Max[:\s]*(\d+\.?\d*)', text, re.I)
            if m:
                result["vo2max"] = float(m.group(1))
            m = re.search(r'(?:Running\s*)?Level[:\s]*([^\n]+)', text, re.I)
            if m:
                result["running_level"] = m.group(1).strip()
            m = re.search(r'(?:Threshold\s*)?Pace[:\s]*([\d:]+)', text, re.I)
            if m:
                result["threshold_pace"] = m.group(1).strip()
            for dist in ["5K", "10K", "Half[ -]?Marathon", "Marathon"]:
                key_map = {"Half[ -]?Marathon": "half_marathon"}
                key = key_map.get(dist) or dist.lower().replace(" ", "_")
                m = re.search(rf'{dist}[:\s]*([\d:]+)', text, re.I)
                if m:
                    result["race_predictions"][key] = m.group(1).strip()
            return result
    except Exception:
        pass

    # Fallback: derive from DB
    from datetime import timedelta
    recent = (
        db.query(FitnessMetrics)
        .filter(FitnessMetrics.user_id == user.id)
        .order_by(FitnessMetrics.date.desc())
        .limit(30).all()
    )
    vo2max_vals = [r.vo2max for r in recent if r.vo2max]
    return {
        "vo2max": vo2max_vals[0] if vo2max_vals else None,
        "running_level": None,
        "threshold_pace": None,
        "race_predictions": {},
        "source": "local_db",
    }


# ── Dashboard ──

@router.get("/activities/synced")
def get_synced_activities(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取已同步的活动记录"""
    since = date.today() - timedelta(days=days)
    activities = (
        db.query(ActivityRecord)
        .filter(ActivityRecord.user_id == user.id, ActivityRecord.activity_date >= since)
        .order_by(ActivityRecord.activity_date.desc(), ActivityRecord.id.desc())
        .limit(100)
        .all()
    )
    import json
    result = []
    for a in activities:
        item = {
            "id": a.id,
            "date": str(a.activity_date),
            "sport_type": a.sport_type,
            "sport_name": a.sport_name,
            "location": a.location,
            "duration_min": round(a.duration_sec / 60, 1) if a.duration_sec else None,
            "distance_km": a.distance_km,
            "avg_pace": a.avg_pace,
            "avg_hr": a.avg_hr,
            "max_hr": a.max_hr,
            "calories": a.calories,
            "training_load": a.training_load,
            "avg_power": a.avg_power,
            "elevation_gain": a.elevation_gain,
            "hr_zones": json.loads(a.hr_zones) if a.hr_zones else None,
            "pace_zones": json.loads(a.pace_zones) if a.pace_zones else None,
            "laps": json.loads(a.laps) if a.laps else None,
        }
        result.append(item)
    return {"activities": result, "total": len(result)}


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    today_metric = db.query(FitnessMetrics).filter(
        FitnessMetrics.user_id == user.id, FitnessMetrics.date == today,
    ).first()

    # Auto-sync if no data yet today (non-blocking)
    synced = False
    if not today_metric:
        # 1. Try MCP/CLI native sync
        try:
            result = mcp_sync_all(user, db)
            if result.get("imported") or result.get("recovery"):
                synced = True
        except Exception:
            pass

        # 2. Fallback: Cookie-based web sync
        if not synced:
            t = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
            if t and t.cookie:
                try:
                    result = await sync_all_to_metrics(user.id, db)
                    if result.get("ok"):
                        synced = True
                except Exception:
                    pass

        # Refresh today_metric after sync
        if synced:
            db.expire_all()
            today_metric = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user.id, FitnessMetrics.date == today,
            ).first()
    recent = (
        db.query(FitnessMetrics)
        .filter(FitnessMetrics.user_id == user.id)
        .order_by(FitnessMetrics.date.desc())
        .limit(14).all()
    )
    # Recent activities (last 7 days)
    since = today - timedelta(days=7)
    recent_activities = (
        db.query(ActivityRecord)
        .filter(ActivityRecord.user_id == user.id, ActivityRecord.activity_date >= since)
        .order_by(ActivityRecord.activity_date.desc())
        .limit(10)
        .all()
    )
    # Weekly stats
    weekly_km = sum((a.distance_km or 0) for a in recent_activities)
    weekly_runs = len(recent_activities)

    token = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
    coros_connected = False
    if token:
        # OAuth connected, credentials configured, or cookie set
        coros_connected = bool(
            token.access_token or
            (token.coros_email and token.coros_password_enc) or
            token.cookie
        )
    # Also check native API / MCP availability
    if not coros_connected:
        try:
            from services.coros_mcp_cli import _get_coros_client
            coros_connected = _get_coros_client(user_id=user.id, db=db) is not None
        except Exception:
            pass
    # Best recent metrics (latest with data)
    best_vo2max = None
    best_stamina = None
    best_lthr = None
    best_ltsp = None
    for r in recent:
        if best_vo2max is None and r.vo2max:
            best_vo2max = r.vo2max
        if best_stamina is None and r.stamina_level:
            best_stamina = r.stamina_level
        if best_lthr is None and r.lthr:
            best_lthr = r.lthr
        if best_ltsp is None and r.ltsp:
            best_ltsp = r.ltsp

    # Weekly totals
    weekly_duration_min = sum((a.duration_sec or 0) / 60 for a in recent_activities)
    weekly_elevation = sum(a.elevation_gain or 0 for a in recent_activities)
    weekly_load = sum(a.training_load or 0 for a in recent_activities)

    adjustment = get_daily_adjustment(user, db) if recent else {"message": "暂无数据", "adjustment": "none"}
    return {
        "today": today_metric,
        "recent": recent,
        "daily_adjustment": adjustment,
        "coros_connected": coros_connected,
        "auto_synced": synced,
        # Weekly stats
        "weekly_km": round(weekly_km, 1),
        "weekly_runs": weekly_runs,
        "weekly_duration_min": round(weekly_duration_min, 1),
        "weekly_elevation": weekly_elevation,
        "weekly_load": weekly_load,
        # Advanced metrics
        "vo2max": best_vo2max,
        "stamina": best_stamina,
        "lthr": best_lthr,
        "ltsp": best_ltsp,
        "recent_activities": [
            {
                "id": a.id,
                "date": str(a.activity_date),
                "distance_km": a.distance_km,
                "avg_pace": a.avg_pace,
                "duration_min": round(a.duration_sec / 60, 1) if a.duration_sec else None,
                "avg_hr": a.avg_hr,
                "max_hr": a.max_hr,
                "elevation_gain": a.elevation_gain,
                "training_load": a.training_load,
                "sport_name": a.sport_name,
            }
            for a in recent_activities[:5]
        ],
    }


# ── CSV helpers ──

def _parse_csv_date(row: dict) -> date | None:
    for key in ["date", "日期", "Date"]:
        if key in row:
            val = row[key].strip()
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
    return None


def _parse_float(row: dict, keys: list[str]) -> float | None:
    for key in keys:
        if key in row and row[key].strip():
            try:
                return float(row[key].strip())
            except ValueError:
                pass
    return None


def _parse_int(row: dict, keys: list[str]) -> int | None:
    for key in keys:
        if key in row and row[key].strip():
            try:
                return int(float(row[key].strip()))
            except ValueError:
                pass
    return None
