"""
通过 Cookie 模拟 COROS Web 请求，自动拉取数据。

使用方式：
A. 自动登录（推荐）：输入 COROS 邮箱密码 → 后端代请求 → 自动获取 Cookie
B. 手动粘贴 Cookie：浏览器打开 https://t.coros.com 登录 → F12 → Cookies → 粘贴

COROS 内部 API（逆向自网页版）：
- 登录: /account/login → teamcnapi.coros.com
- 用户信息: /api/v1/user/info → t.coros.com
- 活动列表: /api/v1/activity/list → t.coros.com
- 每日健康: /api/v1/fitness/daily → t.coros.com
- 睡眠详情: /api/v1/sleep/detail → t.coros.com
- 训练计划: /api/v1/plan/list → t.coros.com
"""

import json
import re
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import httpx

from db.user import User
from db.coros_token import CorosToken
from db.metrics import FitnessMetrics
from db.training import TrainingPlan, TrainingSession, SessionType, Intensity

COROS_WEB_BASE = "https://t.coros.com"
COROS_LOGIN_API_CN = "https://teamcnapi.coros.com"
COROS_LOGIN_API_GLOBAL = "https://teamapi.coros.com"
COROS_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# ── Auto-login ──

def _get_csrf_token(region: str = "cn") -> tuple[str, str]:
    """Get CSRF token from COROS webpage. Returns (token, raw_cookie_header)."""
    base = "https://t.coros.com" if region == "cn" else "https://training.coros.com"
    resp = httpx.get(
        base,
        headers={"User-Agent": COROS_USER_AGENT, "Accept": "text/html"},
        timeout=15,
        follow_redirects=True,
    )
    # Extract csrfToken from Set-Cookie
    cookie_header = resp.headers.get("set-cookie", "")
    match = re.search(r"csrfToken=([^;]+)", cookie_header)
    csrf = match.group(1) if match else ""
    # Also try reading from the cookie jar-like response
    if not csrf:
        for h in resp.headers.multi_items():
            if h[0].lower() == "set-cookie":
                m = re.search(r"csrfToken=([^;]+)", h[1])
                if m:
                    csrf = m.group(1)
                    break
    return csrf, cookie_header


def login_via_web(email: str, password: str, region: str = "cn") -> dict:
    """Login to COROS web and return session cookie string.

    Returns {"ok": True, "cookie": "...", "name": "..."} on success,
    or {"ok": False, "message": "...", "need_captcha": bool} on failure.
    """
    login_api = COROS_LOGIN_API_CN if region == "cn" else COROS_LOGIN_API_GLOBAL
    web_host = "t.coros.com" if region == "cn" else "training.coros.com"

    # 1. Get CSRF token
    try:
        csrf, _ = _get_csrf_token(region)
    except Exception as e:
        return {"ok": False, "message": f"无法获取 CSRF token: {e}"}

    if not csrf:
        return {"ok": False, "message": "无法获取 CSRF token，请检查网络连接"}

    # Determine account type: phone vs email
    if re.match(r'^\+?\d{8,15}$', email.strip()):
        account_type = "phone"
    elif "@" in email:
        account_type = "email"
    else:
        account_type = "phone"  # default to phone for numeric-looking inputs

    # 2. Login
    try:
        resp = httpx.post(
            f"{login_api}/account/login",
            json={"account": email, "password": password, "type": account_type},
            headers={
                "User-Agent": COROS_USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": f"https://{web_host}",
                "Referer": f"https://{web_host}/login",
                "x-csrf-token": csrf,
                "Cookie": f"csrfToken={csrf}",
            },
            timeout=15,
        )
    except Exception as e:
        return {"ok": False, "message": f"登录请求失败: {e}"}

    if resp.status_code != 200:
        return {"ok": False, "message": f"服务器返回 {resp.status_code}"}

    data = resp.json()
    result_code = data.get("result", "")

    # CAPTCHA required
    if result_code in ("3003", "3004") or "captcha" in str(data).lower():
        return {"ok": False, "need_captcha": True, "message": "需要完成验证码，请在浏览器中登录后手动粘贴 Cookie"}

    # Wrong credentials
    if result_code != "0000":
        msg = data.get("message", "登录失败")
        return {"ok": False, "message": msg}

    # 3. Extract session cookies from response
    cookie_parts = []
    for item in resp.headers.multi_items():
        if item[0].lower() == "set-cookie":
            cookie_parts.append(item[1].split(";")[0])

    cookie_str = "; ".join(cookie_parts)

    # 4. Get user name
    name = ""
    try:
        user_resp = httpx.get(
            f"https://{web_host}/api/v1/user/info",
            headers={
                "User-Agent": COROS_USER_AGENT,
                "Accept": "application/json",
                "Origin": f"https://{web_host}",
                "Referer": f"https://{web_host}/",
                "Cookie": cookie_str,
            },
            timeout=15,
        )
        if user_resp.status_code == 200:
            user_data = user_resp.json()
            name = user_data.get("data", {}).get("nickname") or user_data.get("data", {}).get("name") or ""
    except Exception:
        pass

    return {"ok": True, "cookie": cookie_str, "name": name, "message": f"登录成功{f' ({name})' if name else ''}"}


def _get_cookie(user_id: int, db: Session) -> str | None:
    token = db.query(CorosToken).filter(CorosToken.user_id == user_id).first()
    if not token or not token.cookie:
        return None
    return token.cookie


def _parse_cookie_to_dict(cookie_str: str) -> dict:
    """Parse cookie string like 'key1=val1; key2=val2' to dict."""
    cookies = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, val = item.split("=", 1)
            cookies[key.strip()] = val.strip()
    return cookies


def _make_headers(cookie_str: str) -> dict:
    return {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://t.coros.com/",
        "Origin": "https://t.coros.com",
    }


async def test_cookie(user_id: int, db: Session) -> dict:
    """Test if the cookie is valid."""
    cookie = _get_cookie(user_id, db)
    if not cookie:
        return {"valid": False, "message": "未设置 Cookie"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{COROS_WEB_BASE}/api/v1/user/info",
                headers=_make_headers(cookie),
            )
            if r.status_code == 200:
                data = r.json()
                name = data.get("data", {}).get("nickname") or data.get("data", {}).get("name") or "未知"
                return {"valid": True, "message": f"Cookie 有效，已识别账号: {name}"}
            return {"valid": False, "message": f"Cookie 无效 (HTTP {r.status_code})"}
    except Exception as e:
        return {"valid": False, "message": f"连接失败: {str(e)[:100]}"}


async def fetch_daily_fitness(user_id: int, db: Session, days: int = 14) -> list[dict]:
    """Fetch daily fitness data (HRV, resting HR, recovery, sleep, etc.)."""
    cookie = _get_cookie(user_id, db)
    if not cookie:
        return []

    today = date.today()
    start = today - timedelta(days=days)

    async with httpx.AsyncClient(timeout=30) as client:
        # Try fitness daily endpoint
        try:
            r = await client.get(
                f"{COROS_WEB_BASE}/api/v1/fitness/daily",
                headers=_make_headers(cookie),
                params={"startDate": start.isoformat(), "endDate": today.isoformat()},
            )
            if r.status_code == 200:
                data = r.json()
                records = data.get("data", {}).get("list") or data.get("data", [])
                return records if isinstance(records, list) else []
        except Exception:
            pass

        # Fallback: try sleep endpoint + other health endpoints
        results = []
        for ep in ["/api/v1/sleep/list", "/api/v1/health/daily"]:
            try:
                r = await client.get(
                    f"{COROS_WEB_BASE}{ep}",
                    headers=_make_headers(cookie),
                    params={"startDate": start.isoformat(), "endDate": today.isoformat()},
                )
                if r.status_code == 200:
                    data = r.json()
                    records = data.get("data", {}).get("list") or data.get("data", [])
                    if isinstance(records, list):
                        results.extend(records)
            except Exception:
                continue

        return results


async def fetch_activities(user_id: int, db: Session, days: int = 30) -> list[dict]:
    """Fetch running activities."""
    cookie = _get_cookie(user_id, db)
    if not cookie:
        return []

    today = date.today()
    start = today - timedelta(days=days)

    async with httpx.AsyncClient(timeout=30) as client:
        all_activities = []
        page = 1
        while True:
            try:
                r = await client.get(
                    f"{COROS_WEB_BASE}/api/v1/activity/list",
                    headers=_make_headers(cookie),
                    params={
                        "startDate": start.isoformat(),
                        "endDate": today.isoformat(),
                        "page": page,
                        "size": 50,
                        "sportType": "1",
                    },
                )
                if r.status_code != 200:
                    break
                data = r.json()
                records = data.get("data", {}).get("list") or data.get("data", [])
                if not records:
                    break
                all_activities.extend(records)
                if len(records) < 50:
                    break
                page += 1
            except Exception:
                break
        return all_activities


async def fetch_sleep_detail(user_id: int, db: Session, target_date: date) -> dict | None:
    """Fetch detailed sleep data for a specific date."""
    cookie = _get_cookie(user_id, db)
    if not cookie:
        return None

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"{COROS_WEB_BASE}/api/v1/sleep/detail",
                headers=_make_headers(cookie),
                params={"date": target_date.isoformat()},
            )
            if r.status_code == 200:
                return r.json().get("data", {})
        except Exception:
            pass
    return None


async def sync_all_to_metrics(user_id: int, db: Session) -> dict:
    """Sync all COROS data to local FitnessMetrics. Returns summary."""
    cookie = _get_cookie(user_id, db)
    if not cookie:
        return {"error": "未配置 Cookie，请先在设置页粘贴 Cookie"}

    # Test cookie first
    test = await test_cookie(user_id, db)
    if not test["valid"]:
        return {"error": test["message"]}

    user = db.query(User).filter(User.id == user_id).first()
    imported_fitness = 0
    imported_activities = 0

    # Sync daily fitness
    fitness_data = await fetch_daily_fitness(user_id, db, days=14)
    for item in fitness_data:
        try:
            item_date = _extract_date(item)
            if not item_date:
                continue

            existing = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user_id,
                FitnessMetrics.date == item_date,
            ).first()

            sleep_hours = _nested_num(item, ["sleepDuration", "totalSleep", "sleepTime"])
            if sleep_hours and sleep_hours > 24:
                sleep_hours = round(sleep_hours / 60, 1)

            metrics_data = {
                "sleep_hours": sleep_hours,
                "sleep_quality": _nested_int(item, ["sleepQuality", "sleepScore", "sleepLevel"]),
                "resting_hr": _nested_int(item, ["restHr", "restingHr", "avgHr", "restingHeartRate"]),
                "hrv": _nested_int(item, ["hrv", "rmssd", "sdnn"]),
                "fatigue_score": _nested_num(item, ["fatigue", "trainingLoad", "load"]),
                "recovery_score": _nested_num(item, ["recovery", "readiness", "recoveryScore"]),
                # Sleep phases from fitness daily
                "deep_sleep_min": _nested_int(item, ["deepSleep", "deepMinutes", "deepSleepTime", "deepDuration"]),
                "light_sleep_min": _nested_int(item, ["lightSleep", "lightMinutes", "lightSleepTime", "lightDuration"]),
                "rem_sleep_min": _nested_int(item, ["remSleep", "remMinutes", "remSleepTime", "remDuration"]),
                "sleep_avg_hr": _nested_int(item, ["avgSleepHr", "sleepAvgHr", "avgHr"]),
                "sleep_min_hr": _nested_int(item, ["minSleepHr", "sleepMinHr", "minHr"]),
                "sleep_max_hr": _nested_int(item, ["maxSleepHr", "sleepMaxHr", "maxHr"]),
            }
            # Also try nested sleep object
            sleep_obj = item.get("sleep") or item.get("sleepData") or {}
            if isinstance(sleep_obj, dict):
                for k in ("deep_sleep_min", "light_sleep_min", "rem_sleep_min", "sleep_avg_hr", "sleep_min_hr", "sleep_max_hr"):
                    if metrics_data.get(k) is None:
                        pass  # Will be filled below if available
                if metrics_data.get("deep_sleep_min") is None:
                    metrics_data["deep_sleep_min"] = _nested_int(sleep_obj, ["deep", "deepMinutes", "deepDuration"])
                if metrics_data.get("light_sleep_min") is None:
                    metrics_data["light_sleep_min"] = _nested_int(sleep_obj, ["light", "lightMinutes", "lightDuration"])
                if metrics_data.get("rem_sleep_min") is None:
                    metrics_data["rem_sleep_min"] = _nested_int(sleep_obj, ["rem", "remMinutes", "remDuration"])
            metrics_data = {k: v for k, v in metrics_data.items() if v is not None}

            if not metrics_data:
                continue

            if existing:
                for k, v in metrics_data.items():
                    setattr(existing, k, v)
            else:
                db.add(FitnessMetrics(user_id=user_id, date=item_date, **metrics_data))
                db.flush()

            imported_fitness += 1
        except Exception:
            continue

    # Also sync today's sleep detail for richer data (phases, sleep HR, etc.)
    try:
        sleep_detail = await fetch_sleep_detail(user_id, db, date.today())
        if sleep_detail:
            today = date.today()
            existing = db.query(FitnessMetrics).filter(
                FitnessMetrics.user_id == user_id,
                FitnessMetrics.date == today,
            ).first()
            sleep_h = _nested_num(sleep_detail, ["totalSleep", "duration", "sleepTime"])
            if sleep_h and sleep_h > 24:
                sleep_h = round(sleep_h / 60, 1)
            avg_hr = _nested_int(sleep_detail, ["avgHr", "avgHeartRate"])
            hrv_val = _nested_int(sleep_detail, ["avgHrv", "hrv"])
            # Sleep phases
            deep_min = _nested_int(sleep_detail, ["deepSleep", "deepMinutes", "deepSleepTime", "deepDuration", "deep"])
            light_min = _nested_int(sleep_detail, ["lightSleep", "lightMinutes", "lightSleepTime", "lightDuration", "light"])
            rem_min = _nested_int(sleep_detail, ["remSleep", "remMinutes", "remSleepTime", "remDuration", "rem"])
            min_hr = _nested_int(sleep_detail, ["minHr", "minHeartRate", "sleepMinHr"])
            max_hr = _nested_int(sleep_detail, ["maxHr", "maxHeartRate", "sleepMaxHr"])
            quality = _nested_int(sleep_detail, ["sleepQuality", "sleepScore", "quality", "score"])
            # Also try nested sleep object from detail
            nested_sleep = sleep_detail.get("sleep") or sleep_detail.get("sleepData") or {}
            if isinstance(nested_sleep, dict):
                if deep_min is None:
                    deep_min = _nested_int(nested_sleep, ["deep", "deepMinutes", "deepDuration"])
                if light_min is None:
                    light_min = _nested_int(nested_sleep, ["light", "lightMinutes", "lightDuration"])
                if rem_min is None:
                    rem_min = _nested_int(nested_sleep, ["rem", "remMinutes", "remDuration"])

            if existing:
                if sleep_h: existing.sleep_hours = sleep_h
                if avg_hr: existing.sleep_avg_hr = avg_hr
                if hrv_val: existing.hrv = hrv_val
                if deep_min: existing.deep_sleep_min = deep_min
                if light_min: existing.light_sleep_min = light_min
                if rem_min: existing.rem_sleep_min = rem_min
                if min_hr: existing.sleep_min_hr = min_hr
                if max_hr: existing.sleep_max_hr = max_hr
                if quality: existing.sleep_quality = quality
            elif sleep_h or avg_hr or deep_min:
                db.add(FitnessMetrics(user_id=user_id, date=today,
                    sleep_hours=sleep_h,
                    sleep_avg_hr=avg_hr,
                    hrv=hrv_val,
                    deep_sleep_min=deep_min,
                    light_sleep_min=light_min,
                    rem_sleep_min=rem_min,
                    sleep_min_hr=min_hr,
                    sleep_max_hr=max_hr,
                    sleep_quality=quality,
                ))
            imported_fitness += 1
    except Exception:
        pass

    db.commit()

    return {
        "ok": True,
        "fitness_synced": imported_fitness,
        "activities_found": len(await fetch_activities(user_id, db)),
        "cookie_valid": test["valid"],
        "message": f"同步完成：健康数据 {imported_fitness} 条",
    }


def _extract_date(item: dict) -> date | None:
    for key in ("date", "recordDate", "day", "sleepDate", "fitnessDate"):
        val = item.get(key)
        if val:
            if isinstance(val, date):
                return val
            if isinstance(val, str):
                for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(val[:10], fmt).date()
                    except ValueError:
                        continue
    return None


def _nested_num(d: dict, keys: list[str]) -> float | None:
    for key in keys:
        val = d.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None


def _nested_int(d: dict, keys: list[str]) -> int | None:
    for key in keys:
        val = d.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                pass
    return None
