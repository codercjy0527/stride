"""
COROS Open API 对接服务
实现 OAuth 2.0 授权、运动数据同步、训练计划拉取

COROS API docs: https://developer.coros.com
"""

import hashlib
import base64
import secrets
import time
from datetime import date, datetime, timedelta, timezone as tz
from typing import Optional
from sqlalchemy.orm import Session
import httpx

from config import (
    COROS_CLIENT_ID, COROS_CLIENT_SECRET, COROS_REDIRECT_URI,
    COROS_AUTH_URL, COROS_TOKEN_URL, COROS_API_BASE,
)
from db.user import User
from db.coros_token import CorosToken
from db.metrics import FitnessMetrics
from db.training import TrainingPlan, TrainingSession, SessionType, Intensity


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge for OAuth."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return code_verifier, code_challenge


def get_authorization_url(state: str, code_challenge: str, redirect_uri: str = "") -> str:
    """Build COROS OAuth authorization URL."""
    uri = redirect_uri or COROS_REDIRECT_URI
    params = {
        "client_id": COROS_CLIENT_ID,
        "redirect_uri": uri,
        "response_type": "code",
        "scope": "activity:read health:read sleep:read profile:read",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{COROS_AUTH_URL}?{qs}"


def exchange_code(code: str, code_verifier: str, redirect_uri: str = "") -> dict:
    """Exchange OAuth authorization code for tokens."""
    uri = redirect_uri or COROS_REDIRECT_URI
    resp = httpx.post(
        COROS_TOKEN_URL,
        data={
            "client_id": COROS_CLIENT_ID,
            "client_secret": COROS_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": uri,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise Exception(f"Token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()


def refresh_access_token(token: CorosToken) -> dict:
    """Refresh expired access token."""
    resp = httpx.post(
        COROS_TOKEN_URL,
        data={
            "client_id": COROS_CLIENT_ID,
            "client_secret": COROS_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise Exception(f"Token refresh failed: {resp.status_code} {resp.text}")
    return resp.json()


def _get_valid_token(user_id: int, db: Session) -> str | None:
    """Get a valid access token, refreshing if needed."""
    token = db.query(CorosToken).filter(CorosToken.user_id == user_id).first()
    if not token:
        return None

    # Check if expired
    if token.expires_at and token.expires_at <= datetime.now(tz):
        try:
            new_tokens = refresh_access_token(token)
            token.access_token = new_tokens["access_token"]
            token.refresh_token = new_tokens.get("refresh_token", token.refresh_token)
            expires_in = new_tokens.get("expires_in", 7200)
            token.expires_at = datetime.now(tz) + timedelta(seconds=expires_in)
            db.commit()
        except Exception:
            return None

    return token.access_token


def fetch_athlete_profile(user_id: int, db: Session) -> dict:
    """Fetch COROS athlete profile."""
    access_token = _get_valid_token(user_id, db)
    if not access_token:
        return {}

    resp = httpx.get(
        f"{COROS_API_BASE}/v2/athlete",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return {}


def fetch_activities(user_id: int, db: Session, days: int = 30) -> list[dict]:
    """Fetch recent running activities from COROS."""
    access_token = _get_valid_token(user_id, db)
    if not access_token:
        return []

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    resp = httpx.get(
        f"{COROS_API_BASE}/v2/activity/list",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "sportType": "1",  # 1 = running
            "size": "100",
        },
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("data", {}).get("records", [])
    return []


def fetch_health_data(user_id: int, db: Session, days: int = 14) -> list[dict]:
    """Fetch sleep, HRV, and daily health data from COROS."""
    access_token = _get_valid_token(user_id, db)
    if not access_token:
        return []

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    results = []

    # Try multiple health endpoints
    endpoints = [
        "/v2/health/daily",
        "/v2/health/sleep",
        "/v2/health/summary",
    ]

    for ep in endpoints:
        try:
            resp = httpx.get(
                f"{COROS_API_BASE}{ep}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                records = data.get("records") or data.get("items") or []
                if isinstance(records, list):
                    results.extend(records)
                elif isinstance(data, dict):
                    results.append(data)
        except Exception:
            continue

    return results


def sync_health_to_metrics(user: User, db: Session) -> int:
    """Sync COROS health data to local FitnessMetrics table."""
    access_token = _get_valid_token(user.id, db)
    if not access_token:
        return 0

    health_data = fetch_health_data(user.id, db, days=14)
    activities = fetch_activities(user.id, db, days=30)

    imported = 0

    # Process daily health data
    for item in health_data:
        try:
            item_date = _parse_date(item)
            if not item_date:
                continue

            existing = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user.id,
                FitnessMetrics.date == item_date,
            ).first()

            metrics_data = {
                "sleep_hours": _nested_get(item, ["sleepDuration", "sleep_duration", "totalSleep"]) or _nested_get(item, ["sleep", "duration"]),
                "sleep_quality": _nested_get(item, ["sleepQuality", "sleep_quality", "sleepScore"]),
                "resting_hr": _nested_get(item, ["restingHr", "resting_hr", "restHr", "avgHr"]),
                "hrv": _nested_get(item, ["hrv", "rmssd"]),
                "fatigue_score": _nested_get(item, ["fatigue", "trainingLoad", "fatigueScore"]),
                "recovery_score": _nested_get(item, ["recovery", "recoveryScore", "readiness"]),
            }

            # Convert sleep from minutes to hours
            if metrics_data["sleep_hours"] and metrics_data["sleep_hours"] > 24:
                metrics_data["sleep_hours"] = round(metrics_data["sleep_hours"] / 60, 1)

            # Clean None values
            metrics_data = {k: v for k, v in metrics_data.items() if v is not None}

            if not metrics_data:
                continue

            if existing:
                for k, v in metrics_data.items():
                    setattr(existing, k, v)
            else:
                m = FitnessMetrics(user_id=user.id, date=item_date, **metrics_data)
                db.add(m)
                db.flush()

            imported += 1
        except Exception:
            continue

    db.commit()
    return imported


def fetch_training_plans(user_id: int, db: Session) -> list[dict]:
    """Fetch COROS training plans."""
    access_token = _get_valid_token(user_id, db)
    if not access_token:
        return []

    resp = httpx.get(
        f"{COROS_API_BASE}/v2/training/plan",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("data", {}).get("plans") or resp.json().get("data", [])
    return []


def import_coros_plan(user: User, plan_data: dict, db: Session) -> TrainingPlan | None:
    """Import a COROS training plan into the local app."""
    if not plan_data:
        return None

    plan = TrainingPlan(
        user_id=user.id,
        name=plan_data.get("planName") or plan_data.get("name") or "COROS 导入计划",
        weeks=plan_data.get("totalWeeks") or plan_data.get("weeks") or 12,
        weekly_mileage_cap=0.10,
        high_intensity_max=2,
        low_intensity_max=4,
        target_race=_map_race_type(plan_data.get("targetRace") or plan_data.get("goal")),
        target_date=_parse_date_str(plan_data.get("targetDate") or plan_data.get("raceDate")),
    )
    db.add(plan)
    db.flush()

    # Add sessions from plan
    workouts = plan_data.get("workouts") or plan_data.get("sessions") or []
    for w in workouts:
        session_type = _map_session_type(w.get("type") or w.get("trainingType") or "easy")
        intensity = Intensity.high if session_type in (SessionType.tempo, SessionType.interval) else Intensity.low

        db.add(TrainingSession(
            plan_id=plan.id,
            week=w.get("week") or 1,
            day_of_week=w.get("dayOfWeek") or w.get("day") or 0,
            session_type=session_type,
            intensity=intensity,
            duration_min=w.get("duration") or w.get("plannedDuration") or 30,
            distance_km=float(w.get("distance") or w.get("plannedDistance") or 0),
            description=w.get("description") or w.get("name") or "",
        ))

    db.commit()
    return plan


def _parse_date(item: dict) -> date | None:
    for key in ("date", "recordDate", "day", "sleepDate"):
        val = item.get(key)
        if val:
            return _parse_date_str(val)
    return None


def _parse_date_str(val) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(val[:10], fmt).date()
            except ValueError:
                continue
    return None


def _nested_get(d: dict, keys: list[str]):
    for key in keys:
        val = d.get(key)
        if val is not None:
            if isinstance(val, (int, float)):
                return float(val) if val > 0 else None
            return val
    return None


def _map_session_type(t: str) -> SessionType:
    t = t.lower()
    mapping = {
        "easy": SessionType.easy, "jog": SessionType.easy, "recovery": SessionType.easy,
        "tempo": SessionType.tempo, "threshold": SessionType.tempo, "pace": SessionType.tempo,
        "interval": SessionType.interval, "speed": SessionType.interval, "hill": SessionType.interval,
        "long_run": SessionType.long_run, "long": SessionType.long_run, "endurance": SessionType.long_run,
        "rest": SessionType.rest, "off": SessionType.rest,
    }
    return mapping.get(t, SessionType.easy)


def _map_race_type(goal: str) -> str:
    if not goal:
        return "半马"
    goal = goal.lower()
    if "marathon" in goal or "全马" in goal or "42" in goal:
        return "全马"
    if "half" in goal or "半马" in goal or "21" in goal:
        return "半马"
    if "10k" in goal or "10公里" in goal:
        return "10K"
    if "5k" in goal or "5公里" in goal:
        return "5K"
    return "半马"
