"""
COROS 数据同步 —— 优先使用新 coros-training-mcp 原生 Python API
若未配置凭据，回退到旧的 npm CLI subprocess 方式
"""
import os, logging
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from db.user import User
from db.metrics import FitnessMetrics
from db.activity import ActivityRecord


def _get_coros_client(user_id: int = None, db: Session = None):
    """Get authenticated COROS API client with token caching.

    Token is cached in the OS keyring by coros_api itself (24h TTL).
    We additionally track expiry in the DB to avoid re-login within the
    same token window, which prevents COROS security notifications on
    the user's phone.

    Resolution order:
    1. Cached token in keyring/encrypted file (from coros_api._save_auth)
    2. DB-stored credentials → check expiry → cached token or fresh login
    3. Env vars (COROS_EMAIL + COROS_PASSWORD)
    4. None (caller should fall back to old CLI)
    """
    try:
        import coros_api
    except ImportError:
        return None

    # 1. Try cached auth from keyring/encrypted file
    #    coros_api.login() stores the token via _save_auth() automatically.
    #    If it's still valid, return it — no login needed.
    auth = coros_api.get_stored_auth()
    if auth is not None:
        return auth

    # 2. Try DB credentials (with expiry check to avoid spamming login)
    if user_id and db:
        try:
            from db.coros_token import CorosToken
            from services.license import _simple_decrypt
            token_row = db.query(CorosToken).filter(CorosToken.user_id == user_id).first()
            if token_row and token_row.coros_email and token_row.coros_password_enc:
                # If DB says token is still fresh, try keyring once more
                # (coros_api TTL is 24h; we use 23h to add buffer)
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                if token_row.expires_at and token_row.expires_at > now_utc:
                    auth = coros_api.get_stored_auth()
                    if auth is not None:
                        return auth

                # Token expired or never cached — do a fresh login
                email = token_row.coros_email
                password = _simple_decrypt(token_row.coros_password_enc)
                region = token_row.coros_region or "cn"
                auth = asyncio_run(coros_api.login(email, password, region))
                if auth:
                    # Remember expiry so we don't re-login for the next 23 hours
                    token_row.expires_at = now_utc + timedelta(hours=23)
                    token_row.updated_at = now_utc
                    db.commit()
                    return auth
        except Exception:
            pass

    # 3. Try env vars (with keyring caching)
    auth = coros_api.get_stored_auth()
    if auth:
        return auth

    # 4. Try env-based auto-login (COROS_EMAIL + COROS_PASSWORD from .env)
    try:
        auth = asyncio_run(coros_api.try_auto_login())
        if auth:
            return auth
    except Exception:
        pass

    return None


def _fallback_cli_call(tool_name: str, args: dict = None) -> str:
    """Fallback: call old npm coros-mcp CLI via subprocess."""
    import subprocess, json
    cmd = ["coros-mcp", "call-tool", "--tool", tool_name]
    if args:
        cmd.extend(["--arguments-json", json.dumps(args, ensure_ascii=False)])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            return ""
        data = json.loads(result.stdout)
        if data.get("isError"):
            return ""
        for item in data.get("content", []):
            if item.get("type") == "text":
                text = item["text"]
                if text.startswith('"') and text.endswith('"'):
                    try:
                        text = json.loads(text)
                    except Exception:
                        pass
                return text
        return ""
    except Exception:
        return ""


def asyncio_run(coro):
    """Run an async coroutine synchronously."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    return asyncio.run(coro)


def _legacy_cli_available() -> bool:
    """Check if legacy coros-mcp npm CLI is installed."""
    import shutil
    return shutil.which("coros-mcp") is not None


def sync_all(user: User, db: Session) -> dict:
    """Sync all COROS health & activity data to local DB.

    Returns dict with keys: imported, activities, recovery, message.
    When neither native API nor CLI is available, returns {"available": False}
    so callers can fall back to Cookie or OAuth sync.
    """
    today = date.today()

    # ── Primary: native Python API ──
    auth = _get_coros_client(user_id=user.id, db=db)
    if auth is not None:
        return _sync_via_native_api(auth, user, db, today)

    # ── Fallback: old npm CLI ──
    if _legacy_cli_available():
        return _sync_via_legacy_cli(user, db, today)

    return {"available": False, "message": "MCP 不可用，请使用 Cookie 或 OAuth 同步"}


# ── Native API sync ──

def _sync_via_native_api(auth, user: User, db: Session, today: date) -> dict:
    import coros_api, json

    imported = 0
    activity_count = 0
    detail_count = 0

    # 1. Daily health records (HRV, RHR, VO2max, stamina, training load, etc.) — 30 days
    try:
        start = (today - timedelta(days=30)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        records = asyncio_run(coros_api.fetch_daily_records(auth, start, end))
        for rec in records:
            d = _parse_date_str(rec.date)
            if not d:
                continue
            fields = {
                "resting_hr": rec.rhr,
                "hrv": rec.avg_sleep_hrv,
                "vo2max": rec.vo2max,
                "lthr": rec.lthr,
                "ltsp": rec.ltsp,
                "stamina_level": rec.stamina_level,
                "stamina_7d": rec.stamina_level_7d,
                "training_load_ratio": rec.training_load_ratio,
                "tired_rate": rec.tired_rate,
                "ati": rec.ati,
                "cti": rec.cti,
                "daily_distance_km": round(rec.distance / 1000, 2) if rec.distance else None,
                "daily_duration_min": round(rec.duration / 60, 1) if rec.duration else None,
            }
            _upsert_metric(user, db, d, fields)
            imported += 1
    except Exception:
        pass

    # 2. Detailed sleep — 14 days
    try:
        sleep_start = (today - timedelta(days=14)).strftime("%Y%m%d")
        sleep_end = today.strftime("%Y%m%d")
        sleep_data = asyncio_run(coros_api.fetch_sleep(auth, sleep_start, sleep_end))
        for sl in sleep_data:
            d = _parse_date_str(sl.date)
            if not d:
                continue
            fields = {
                "sleep_hours": round(sl.total_duration_minutes / 60, 1) if sl.total_duration_minutes else None,
                "sleep_quality": sl.quality_score,
                "sleep_avg_hr": sl.avg_hr,
                "sleep_min_hr": sl.min_hr,
                "sleep_max_hr": sl.max_hr,
            }
            if sl.phases:
                fields.update({
                    "deep_sleep_min": sl.phases.deep_minutes,
                    "light_sleep_min": sl.phases.light_minutes,
                    "rem_sleep_min": sl.phases.rem_minutes,
                })
            _upsert_metric(user, db, d, fields)
    except Exception:
        pass

    # 3. Activities — 30 days (with detail for recent runs)
    try:
        start = (today - timedelta(days=30)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        activities = []
        try:
            activities, _ = asyncio_run(coros_api.fetch_activities(auth, start, end))
        except Exception as e:
            # Token might be expired for this endpoint — re-login and retry
            logger.warning(f"fetch_activities failed: {e}, re-authenticating...")
            try:
                from db.coros_token import CorosToken
                from services.license import _simple_decrypt
                token_row = db.query(CorosToken).filter(CorosToken.user_id == user.id).first()
                if token_row and token_row.coros_email and token_row.coros_password_enc:
                    new_auth = asyncio_run(coros_api.login(
                        token_row.coros_email,
                        _simple_decrypt(token_row.coros_password_enc),
                        token_row.coros_region or "cn",
                    ))
                    if new_auth:
                        activities, _ = asyncio_run(coros_api.fetch_activities(new_auth, start, end))
            except Exception:
                pass
        for act in activities:
            parsed = _parse_new_activity(act)
            if parsed:
                existing = db.query(ActivityRecord).filter(
                    ActivityRecord.label_id == parsed["label_id"]
                ).first()
                if not existing:
                    record = ActivityRecord(user_id=user.id, **parsed)
                    db.add(record)
                    db.flush()
                    activity_count += 1
                else:
                    record = existing
                # Fetch detail for runs without detailed data yet
                sport_type = parsed.get("sport_type", 100)
                if sport_type in (100, 101, 102, 103) and not record.hr_zones:
                    try:
                        detail = asyncio_run(coros_api.fetch_activity_detail(auth, parsed["label_id"], sport_type))
                        if detail:
                            _apply_activity_detail(record, detail)
                            detail_count += 1
                    except Exception:
                        pass
    except Exception:
        pass

    # 4. HRV snapshot
    try:
        hrv_data = asyncio_run(coros_api.fetch_hrv(auth))
        if hrv_data:
            latest = hrv_data[-1]
            if latest.avg_sleep_hrv:
                _upsert_metric(user, db, today, {"hrv": latest.avg_sleep_hrv})
    except Exception:
        pass

    db.commit()

    imported = db.query(FitnessMetrics).filter(
        FitnessMetrics.user_id == user.id,
        FitnessMetrics.date >= today - timedelta(days=14),
    ).count()

    return {
        "imported": imported,
        "activities": activity_count,
        "detail_synced": detail_count,
        "message": f"同步完成：健康 {imported} 条 · 运动 {activity_count} 条 · 详情 {detail_count} 条",
    }


def _apply_activity_detail(record: "ActivityRecord", detail: dict):
    """Apply fetched activity detail (HR zones, pace zones, laps) to a record."""
    import json

    # HR zones
    hr_zone_list = detail.get("hrZoneList") or detail.get("hrZones")
    if hr_zone_list:
        record.hr_zones = json.dumps(hr_zone_list, ensure_ascii=False)

    # Pace zones
    pace_zone_list = detail.get("paceZoneList") or detail.get("paceZones")
    if pace_zone_list:
        record.pace_zones = json.dumps(pace_zone_list, ensure_ascii=False)

    # Laps / splits
    lap_list = detail.get("laps") or detail.get("lapList") or detail.get("lapDetails")
    if lap_list:
        record.laps = json.dumps(lap_list, ensure_ascii=False)

    # Elevation
    elevation = detail.get("elevationGain") or detail.get("accumulatedClimb") or detail.get("totalClimb")
    if elevation is not None:
        record.elevation_gain = int(elevation)

    # Max HR
    max_hr = detail.get("maxHr") or detail.get("max_hr")
    if max_hr is not None:
        record.max_hr = int(max_hr)

    # Training load
    tl = detail.get("trainingLoad") or detail.get("tss")
    if tl is not None:
        record.training_load = int(tl)

    # Avg power
    pwr = detail.get("avgPower") or detail.get("avg_power")
    if pwr is not None:
        record.avg_power = int(pwr)

    # Cadence / step frequency
    cadence = detail.get("avgCadence") or detail.get("avgRunCadence") or detail.get("avgStepFrequency") or detail.get("cadence")
    if cadence is not None:
        record.avg_cadence = int(cadence)
    max_cad = detail.get("maxCadence") or detail.get("maxRunCadence") or detail.get("maxStepFrequency")
    if max_cad is not None:
        record.max_cadence = int(max_cad)
    stride = detail.get("avgStrideLength") or detail.get("strideLength") or detail.get("avgStride")
    if stride is not None:
        record.avg_stride_length = float(stride)


def _sync_via_legacy_cli(user: User, db: Session, today: date) -> dict:
    """Fallback sync using old npm coros-mcp CLI subprocess calls."""
    import re

    imported = 0
    activity_count = 0
    recovery_pct = None

    # Recovery status
    text = _fallback_cli_call("queryRecoveryStatus")
    if text:
        m = re.search(r'Recovery:\s*(\d+)%', text)
        if m:
            recovery_pct = int(m.group(1))
            _upsert_metric(user, db, today, {"recovery_score": recovery_pct})

    # Daily health
    text = _fallback_cli_call("queryDailyHealthData", {"days": 14, "timezone": "Asia/Shanghai"})
    _parse_legacy_daily_health(text, user, db)

    # Sleep
    text = _fallback_cli_call("querySleepData", {
        "startDate": (today - timedelta(days=14)).strftime("%Y%m%d"),
        "endDate": today.strftime("%Y%m%d"),
        "days": 14, "timezone": "Asia/Shanghai",
    })
    _parse_legacy_sleep(text, user, db)

    # Resting HR
    text = _fallback_cli_call("queryRestingHeartRate", {"days": 14, "timezone": "Asia/Shanghai"})
    _parse_legacy_resting_hr(text, user, db)

    # HRV
    text = _fallback_cli_call("queryHrvAssessment", {"days": 14, "timezone": "Asia/Shanghai"})
    _parse_legacy_hrv(text, user, db)

    # Sport records
    text = _fallback_cli_call("querySportRecords", {
        "startDate": (today - timedelta(days=30)).strftime("%Y%m%d"),
        "endDate": today.strftime("%Y%m%d"),
        "sportTypeCodes": [100, 101, 102, 103],
        "limit": 100, "timezone": "Asia/Shanghai",
    })
    activity_count = _parse_legacy_activities(text, user, db)

    imported = db.query(FitnessMetrics).filter(
        FitnessMetrics.user_id == user.id,
        FitnessMetrics.date >= today - timedelta(days=14),
    ).count()

    db.commit()
    return {
        "imported": imported,
        "activities": activity_count,
        "message": f"同步完成：健康 {imported} 条 · 运动 {activity_count} 条",
        "recovery": f"{recovery_pct}%" if recovery_pct else None,
    }


# ── Metric helpers ──

def _upsert_metric(user: User, db: Session, d: date, fields: dict):
    """Insert or update a FitnessMetrics row, avoiding duplicates via flush."""
    # Filter out None and COROS sentinel values (-1 means no data)
    fields = {k: v for k, v in fields.items() if v is not None and (not isinstance(v, (int, float)) or v >= 0)}
    if not fields:
        return
    m = db.query(FitnessMetrics).filter(
        FitnessMetrics.user_id == user.id, FitnessMetrics.date == d
    ).first()
    if m:
        for k, v in fields.items():
            setattr(m, k, v)
    else:
        m = FitnessMetrics(user_id=user.id, date=d, **fields)
        db.add(m)
        db.flush()


def _parse_date_str(val) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(val[:10].replace("-", "").replace("/", ""), "%Y%m%d").date()
            except ValueError:
                continue
    return None


# ── New API activity parser ──

def _parse_new_activity(act) -> dict | None:
    """Parse ActivitySummary from new coros_api into local ActivityRecord fields."""
    try:
        label_id = str(act.activity_id)
        # start_time may be int, numeric str (Unix ts), or date str ("2026-05-15...")
        st = act.start_time or ""
        if isinstance(st, (int, float)) and st > 1000000000:
            d = date.fromtimestamp(st)
        elif isinstance(st, str) and st.isdigit() and len(st) >= 10:
            d = date.fromtimestamp(int(st))
        else:
            d = _parse_date_str(str(st)[:8] if st else "")
        if not d:
            return None
        distance_m = act.distance_meters or 0
        duration = act.duration_seconds or 0
        pace = None
        if distance_m > 0 and duration > 0:
            pace_sec = duration / (distance_m / 1000)
            pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"
        return {
            "label_id": label_id,
            "activity_date": d,
            "sport_type": act.sport_type or 100,
            "sport_name": act.sport_name,
            "duration_sec": duration,
            "distance_km": round(distance_m / 1000, 2) if distance_m else None,
            "avg_pace": pace,
            "avg_hr": act.avg_hr,
            "max_hr": act.max_hr,
            "calories": act.calories,
            "training_load": act.training_load,
            "avg_power": act.avg_power,
            "elevation_gain": act.elevation_gain,
        }
    except Exception:
        return None


# ── Legacy CLI parsers (fallback) ──

def _parse_legacy_daily_health(text: str, user: User, db: Session):
    import re
    if not text:
        return
    blocks = re.split(r'--- (\d{8}) ---', text)
    for i in range(1, len(blocks), 2):
        d = _parse_date_str(blocks[i])
        if not d:
            continue
        content = blocks[i + 1] if i + 1 < len(blocks) else ""
        fields = {}
        m = re.search(r'Total:\s*(\d+)h\s*(\d*)min', content)
        if m:
            fields["sleep_hours"] = int(m.group(1)) + (int(m.group(2)) / 60 if m.group(2) else 0)
        m = re.search(r'Score:\s*(\d+)', content)
        if m:
            fields["sleep_quality"] = round(int(m.group(1)) / 20)
        if fields:
            _upsert_metric(user, db, d, fields)


def _parse_legacy_sleep(text: str, user: User, db: Session):
    import re
    if not text:
        return
    blocks = re.split(r'(\d{4}-\d{2}-\d{2})', text)
    for i in range(1, len(blocks), 2):
        d = _parse_date_str(blocks[i])
        if not d:
            continue
        content = blocks[i + 1] if i + 1 < len(blocks) else ""
        m = re.search(r'Main Sleep:\s*(\d+)h\s*(\d*)min', content)
        if m:
            hours = int(m.group(1)) + (int(m.group(2)) / 60 if m.group(2) else 0)
            _upsert_metric(user, db, d, {"sleep_hours": round(hours, 1)})
        m = re.search(r'Sleep Score:\s*(\d+)', content)
        if m:
            _upsert_metric(user, db, d, {"sleep_quality": round(int(m.group(1)) / 20)})


def _parse_legacy_resting_hr(text: str, user: User, db: Session):
    import re
    if not text:
        return
    for line in text.split("\n"):
        m = re.match(r'(\d{4}-\d{2}-\d{2}):\s*(\d+)\s*bpm', line.strip())
        if m:
            d = _parse_date_str(m.group(1))
            hr = int(m.group(2))
            if d and hr > 0:
                _upsert_metric(user, db, d, {"resting_hr": hr})


def _parse_legacy_hrv(text: str, user: User, db: Session):
    import re
    if not text:
        return
    lines = text.split("\n")
    current_date = None
    for line in lines:
        line = line.strip()
        dm = re.match(r'^(\d{4}-\d{2}-\d{2}):$', line)
        if dm:
            current_date = _parse_date_str(dm.group(1))
            continue
        if current_date:
            m = re.match(r'HRV Avg:\s*(\d+)', line)
            if m:
                _upsert_metric(user, db, current_date, {"hrv": int(m.group(1))})
                current_date = None


def _parse_legacy_activities(text: str, user: User, db: Session) -> int:
    import re
    if not text:
        return 0
    count = 0
    records = re.split(r'\n(?=\d+\.\s)', text)
    for rec in records:
        m_lid = re.search(r'LabelId:\s*(\d+)', rec)
        if not m_lid:
            continue
        label_id = m_lid.group(1)
        existing = db.query(ActivityRecord).filter(ActivityRecord.label_id == label_id).first()
        if existing:
            count += 1
            continue
        m_date = re.search(r'(\d{4}-\d{2}-\d{2})', rec)
        if not m_date:
            continue
        d = _parse_date_str(m_date.group(1))
        if not d:
            continue
        sport_type = 100
        m_st = re.search(r'SportType:\s*(\d+)', rec)
        if m_st:
            sport_type = int(m_st.group(1))
        location = None
        m_loc = re.search(r'Location:\s*([^\n]+)', rec)
        if m_loc:
            location = m_loc.group(1).strip()
        distance = None
        m_dist = re.search(r'Distance:\s*([\d.]+)\s*km', rec)
        if m_dist:
            distance = float(m_dist.group(1))
        avg_pace = None
        m_pace = re.search(r'Average Pace:\s*([\d:]+)', rec)
        if m_pace:
            avg_pace = m_pace.group(1)
        avg_hr = None
        m_hr = re.search(r'Avg HR:\s*(\d+)', rec)
        if m_hr:
            avg_hr = int(m_hr.group(1))
        calories = None
        m_cal = re.search(r'Calories:\s*([\d,]+)', rec)
        if m_cal:
            calories = int(m_cal.group(1).replace(",", ""))
        duration_sec = None
        m_dur = re.search(r'Duration:\s*(\d+):(\d+)', rec)
        if m_dur:
            duration_sec = int(m_dur.group(1)) * 60 + int(m_dur.group(2))
        db.add(ActivityRecord(
            user_id=user.id,
            label_id=label_id,
            activity_date=d,
            sport_type=sport_type,
            location=location,
            duration_sec=duration_sec,
            distance_km=distance,
            avg_pace=avg_pace,
            avg_hr=avg_hr,
            calories=calories,
        ))
        count += 1
    return count
