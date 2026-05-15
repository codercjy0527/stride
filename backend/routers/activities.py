"""
运动数据模块 —— 公开展示 & AI 运动复盘
权限全部开放，无需认证
"""
import re
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta

from database import get_db_public
from db.activity import ActivityRecord
from db.metrics import FitnessMetrics
from services.ai_coach import _call_deepseek, _call_claude, _call_openai, _call_gemini
from config import DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY

router = APIRouter()


import json

def _get_activity_detail(activity_id: int, db: Session) -> dict | None:
    a = db.query(ActivityRecord).filter(ActivityRecord.id == activity_id).first()
    if not a:
        return None
    return {
        "id": a.id,
        "date": str(a.activity_date),
        "sport_type": a.sport_type,
        "sport_name": a.sport_name,
        "location": a.location,
        "duration_sec": a.duration_sec,
        "duration_min": round(a.duration_sec / 60, 1) if a.duration_sec else None,
        "distance_km": a.distance_km,
        "avg_pace": a.avg_pace,
        "avg_hr": a.avg_hr,
        "max_hr": a.max_hr,
        "calories": a.calories,
        "training_load": a.training_load,
        "avg_power": a.avg_power,
        "elevation_gain": a.elevation_gain,
        "avg_cadence": a.avg_cadence,
        "max_cadence": a.max_cadence,
        "avg_stride_length": a.avg_stride_length,
        "hr_zones": json.loads(a.hr_zones) if a.hr_zones else None,
        "pace_zones": json.loads(a.pace_zones) if a.pace_zones else None,
        "laps": json.loads(a.laps) if a.laps else None,
        "label_id": a.label_id,
        "user_id": a.user_id,
    }


@router.get("/activities")
def get_all_activities(
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db_public),
):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(ActivityRecord)
        .filter(ActivityRecord.activity_date >= since)
        .order_by(ActivityRecord.activity_date.desc(), ActivityRecord.id.desc())
        .limit(200)
        .all()
    )
    return {
        "activities": [_get_activity_detail(r.id, db) for r in rows],
        "total": len(rows),
    }


@router.get("/activities/{activity_id}")
def get_activity_detail(activity_id: int, db: Session = Depends(get_db_public)):
    detail = _get_activity_detail(activity_id, db)
    if not detail:
        raise HTTPException(status_code=404, detail="活动记录不存在")
    return detail


@router.post("/activities/{activity_id}/review")
async def review_activity(
    activity_id: int,
    provider: str = Query(default="deepseek"),
    api_key: str = Query(default=""),
    model: str = Query(default=""),
    db: Session = Depends(get_db_public),
):
    detail = _get_activity_detail(activity_id, db)
    if not detail:
        raise HTTPException(status_code=404, detail="活动记录不存在")

    uid = detail["user_id"]
    activity_d = date.fromisoformat(detail["date"])
    recent_activities = (
        db.query(ActivityRecord)
        .filter(ActivityRecord.user_id == uid, ActivityRecord.activity_date < activity_d)
        .order_by(ActivityRecord.activity_date.desc())
        .limit(5)
        .all()
    )
    recent_metrics = (
        db.query(FitnessMetrics)
        .filter(FitnessMetrics.user_id == uid, FitnessMetrics.date <= date.today())
        .order_by(FitnessMetrics.date.desc())
        .limit(7)
        .all()
    )

    # Build comparison data for offline / fallback
    comparison = _build_comparison(detail, recent_activities, recent_metrics)

    # Try AI
    key_map = {
        "deepseek": api_key or DEEPSEEK_API_KEY,
        "claude": api_key or ANTHROPIC_API_KEY,
        "openai": api_key or OPENAI_API_KEY,
        "gemini": api_key or GOOGLE_API_KEY,
    }
    call_map = {
        "deepseek": _call_deepseek,
        "claude": _call_claude,
        "openai": _call_openai,
        "gemini": _call_gemini,
    }
    key = key_map.get(provider, "")
    if key:
        prompt = _build_ai_prompt(detail, recent_activities, recent_metrics)
        try:
            ai_func = call_map.get(provider, _call_deepseek)
            ai_text = await ai_func(REVIEW_SYSTEM_PROMPT, prompt, key, model)
            sections = _parse_ai_response(ai_text)
            return {
                "ok": True,
                "activity": detail,
                "sections": sections,
                "comparison": comparison,
                "offline": False,
            }
        except Exception:
            pass

    return {
        "ok": True,
        "activity": detail,
        "sections": _offline_sections(detail, comparison),
        "comparison": comparison,
        "offline": True,
    }


# ── AI prompt (natural language, no markdown) ──

REVIEW_SYSTEM_PROMPT = """你是一位经验丰富的跑步教练，正在为用户做一次运动复盘。

用自然的口吻、第二人称「你」来写。不要使用任何 Markdown 格式（不要用 #、**、- 等符号）。
用清晰的段落分隔不同主题，段落之间空一行。

按以下顺序写：
第一段：用一两句话概括这次跑步的整体感觉
第二段：评估这次训练的强度类型，是否符合80/20极化训练原则
第三段：和用户近期的训练做对比，判断状态是上升还是下降
第四段：基于心率等数据判断身体负荷是否合理
第五段：给出2条最实用的改进建议
最后一段：建议下一次练什么

每段开头加上标记【概要】【强度】【对比】【负荷】【建议】【下次】"""


def _build_ai_prompt(activity: dict, recent: list, metrics: list) -> str:
    lines = [f"复盘对象：{activity['date']} 的跑步记录"]
    lines.append(f"距离 {activity['distance_km']}km，配速 {activity['avg_pace']}/km，平均心率 {activity['avg_hr']}bpm，最大心率 {activity.get('max_hr') or '?'}bpm，用时 {activity['duration_min']}分钟")
    if activity.get("calories"):
        lines.append(f"消耗 {activity['calories']} kcal，训练负荷 {activity.get('training_load') or '?'}")
    if activity.get("location"):
        lines.append(f"地点 {activity['location']}")
    if activity.get("avg_cadence"):
        cadence_info = f"平均步频 {activity['avg_cadence']} 步/分"
        if activity.get("max_cadence"):
            cadence_info += f"，最大步频 {activity['max_cadence']}"
        if activity.get("avg_stride_length"):
            cadence_info += f"，平均步幅 {activity['avg_stride_length']}m"
        lines.append(cadence_info)

    # Heart rate zones
    hr_zones = activity.get("hr_zones")
    if hr_zones and isinstance(hr_zones, list):
        zone_lines = ["心率区间分布："]
        for z in hr_zones[:6]:
            if isinstance(z, dict):
                zone_lines.append(f"  {z.get('zoneName', z.get('name', '?'))} ({z.get('minBpm', '?')}-{z.get('maxBpm', '?')}bpm): {z.get('timeSec', z.get('duration', 0))}秒")
        if len(zone_lines) > 1:
            lines.append("\n".join(zone_lines))

    # Pace zones
    pace_zones = activity.get("pace_zones")
    if pace_zones and isinstance(pace_zones, list):
        zone_lines = ["配速区间分布："]
        for z in pace_zones[:6]:
            if isinstance(z, dict):
                zone_lines.append(f"  {z.get('zoneName', z.get('name', '?'))}: {z.get('timeSec', z.get('duration', 0))}秒")
        if len(zone_lines) > 1:
            lines.append("\n".join(zone_lines))

    # Laps / splits
    laps = activity.get("laps")
    if laps and isinstance(laps, list):
        laps_data = ["分段数据："]
        for i, lap in enumerate(laps[:20]):
            if isinstance(lap, dict):
                lp_pace = lap.get("pace") or lap.get("avgPace", "?")
                lp_hr = lap.get("avgHr") or lap.get("heartRate", "?")
                lp_dist = lap.get("distance") or lap.get("totalDistance", lap.get("distanceMeter", "?"))
                lp_cadence = lap.get("cadence") or lap.get("avgCadence", "")
                parts = [f"配速{lp_pace}", f"心率{lp_hr}"]
                if lp_cadence:
                    parts.append(f"步频{lp_cadence}")
                laps_data.append(f"  第{i+1}段: {', '.join(parts)}")
        if len(laps_data) > 1:
            lines.append("\n".join(laps_data))

    if recent:
        lines.append("\n近期训练：")
        for r in recent[:5]:
            dur = round(r.duration_sec / 60, 1) if r.duration_sec else "?"
            lines.append(f"{r.activity_date} | {r.distance_km or '?'}km | {r.avg_pace or '?'} | 心率{r.avg_hr or '?'} | {dur}min")

    if metrics:
        lines.append("\n近期健康数据：")
        for m in metrics[:5]:
            parts = []
            if m.sleep_hours: parts.append(f"睡眠{m.sleep_hours}h")
            if m.resting_hr: parts.append(f"静息心率{m.resting_hr}")
            if m.hrv: parts.append(f"HRV {m.hrv}")
            if m.recovery_score: parts.append(f"恢复度{m.recovery_score}%")
            if m.training_load_ratio: parts.append(f"负荷比{m.training_load_ratio:.1f}")
            if parts: lines.append(f"{m.date} | {', '.join(parts)}")

    return "\n".join(lines)


def _parse_ai_response(text: str) -> list[dict]:
    """Parse AI response with 【tags】 into structured sections."""
    tags = ["概要", "强度", "对比", "负荷", "建议", "下次"]
    sections = []
    pattern = "|".join(tags)
    parts = re.split(f"【({pattern})】", text)

    # parts[0] = text before first tag, then alternating tag/content
    for i in range(1, len(parts), 2):
        tag = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        content = content.strip()
        # Strip any residual markdown
        content = re.sub(r'\*{1,3}', '', content)
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        if content:
            sections.append({"title": tag, "content": content})

    if not sections:
        # Fallback: treat entire response as a single section
        clean = re.sub(r'\*{1,3}', '', text)
        clean = re.sub(r'^#+\s*', '', clean, flags=re.MULTILINE)
        sections = [{"title": "复盘", "content": clean.strip()}]

    return sections


# ── Offline / fallback ──

def _build_comparison(activity: dict, recent: list, metrics: list) -> dict:
    """Build structured comparison data for UI rendering."""
    result = {
        "recent_runs": [],
        "trend_distance": None,
        "trend_hr": None,
        "trend_pace": None,
    }

    for r in recent[:5]:
        dur = round(r.duration_sec / 60, 1) if r.duration_sec else None
        result["recent_runs"].append({
            "date": str(r.activity_date),
            "distance_km": r.distance_km,
            "avg_pace": r.avg_pace,
            "avg_hr": r.avg_hr,
            "duration_min": dur,
        })

    # Distance trend
    recent_dists = [r.distance_km for r in recent[:3] if r.distance_km]
    if activity.get("distance_km") and recent_dists:
        avg = sum(recent_dists) / len(recent_dists)
        diff = activity["distance_km"] - avg
        result["trend_distance"] = {
            "current": activity["distance_km"],
            "recent_avg": round(avg, 1),
            "diff": round(diff, 1),
            "direction": "up" if diff > avg * 0.05 else "down" if diff < -avg * 0.05 else "flat",
        }

    # HR trend
    recent_hrs = [r.avg_hr for r in recent[:3] if r.avg_hr]
    if activity.get("avg_hr") and recent_hrs:
        avg_hr = sum(recent_hrs) / len(recent_hrs)
        diff_hr = activity["avg_hr"] - int(avg_hr)
        result["trend_hr"] = {
            "current": activity["avg_hr"],
            "recent_avg": int(avg_hr),
            "diff": diff_hr,
            "direction": "up" if diff_hr > 5 else "down" if diff_hr < -5 else "flat",
        }

    # Pace trend
    current_pace_sec = _pace_to_sec(activity.get("avg_pace"))
    if current_pace_sec and recent:
        recent_paces = []
        for r in recent[:3]:
            ps = _pace_to_sec(r.avg_pace)
            if ps:
                recent_paces.append(ps)
        if recent_paces:
            avg_pace_sec = sum(recent_paces) / len(recent_paces)
            diff_sec = current_pace_sec - avg_pace_sec
            result["trend_pace"] = {
                "current": activity["avg_pace"],
                "recent_avg": _sec_to_pace(int(avg_pace_sec)),
                "diff_sec": int(diff_sec),
                "direction": "up" if diff_sec < -3 else "down" if diff_sec > 3 else "flat",
            }

    return result


def _offline_sections(activity: dict, comp: dict) -> list[dict]:
    """Build structured sections for offline review."""
    sections = []

    # Overview
    dist = activity.get("distance_km", "?")
    pace = activity.get("avg_pace", "?")
    hr = activity.get("avg_hr", "?")
    dur = activity.get("duration_min", "?")
    overview = f"你在 {activity['date']} 完成了一次 {dist}km 的跑步，平均配速 {pace}/km，平均心率 {hr}bpm，用时 {dur} 分钟。"
    sections.append({"title": "概要", "content": overview})

    # Intensity
    intensity = _assess_intensity(activity)
    sections.append({"title": "强度", "content": intensity})

    # Comparison
    comparison_text = _format_comparison_text(comp)
    if comparison_text:
        sections.append({"title": "对比", "content": comparison_text})

    # Load
    load_text = _assess_load(activity, comp)
    if load_text:
        sections.append({"title": "负荷", "content": load_text})

    # Suggestions
    suggestions = _generate_suggestions(activity, comp)
    if suggestions:
        sections.append({"title": "建议", "content": suggestions})

    sections.append({"title": "下次", "content": _next_session_advice(activity)})

    return sections


def _pace_to_sec(pace: str | None) -> int | None:
    if not pace:
        return None
    parts = pace.split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass
    return None


def _sec_to_pace(sec: int) -> str:
    return f"{sec // 60}:{sec % 60:02d}"


def _assess_intensity(a: dict) -> str:
    hr = a.get("avg_hr")
    dist = a.get("distance_km", 0)
    dur = a.get("duration_min", 0)
    hr_zones = a.get("hr_zones") or []

    # Build zone summary from actual data
    zone_summary = ""
    if hr_zones and isinstance(hr_zones, list):
        total_sec = sum(z.get("timeSec", z.get("duration", 0)) or 0 for z in hr_zones if isinstance(z, dict))
        if total_sec > 0:
            high_zone_sec = 0
            mid_zone_sec = 0
            low_zone_sec = 0
            for z in hr_zones:
                if not isinstance(z, dict):
                    continue
                sec = z.get("timeSec", z.get("duration", 0)) or 0
                name = z.get("zoneName", z.get("name", ""))
                if "阈" in name or "无氧" in name or "极限" in name or "5" in name or "6" in name:
                    high_zone_sec += sec
                elif "力量" in name or "乳酸" in name or "4" in name or "3" in name:
                    mid_zone_sec += sec
                else:
                    low_zone_sec += sec
            low_pct = round(low_zone_sec / total_sec * 100)
            mid_pct = round(mid_zone_sec / total_sec * 100)
            high_pct = round(high_zone_sec / total_sec * 100)
            parts = [f"轻松区 {low_pct}%"]
            if mid_pct > 0:
                parts.append(f"力量区 {mid_pct}%")
            if high_pct > 0:
                parts.append(f"高强度区 {high_pct}%")
            zone_summary = f" 心率分区：{'，'.join(parts)}。"

    # Assess based on actual zone data + HR
    if hr:
        if zone_summary:
            if low_pct >= 75:
                return f"平均心率 {hr}bpm。{zone_summary}这次训练以有氧基础为主，完全符合80/20极化训练中「80%轻松跑」的原则。低强度训练是提升有氧能力最安全高效的方式。"
            elif high_pct >= 30:
                return f"平均心率 {hr}bpm。{zone_summary}高强度占比偏高，这类训练对神经肌肉刺激较大，建议每周控制在1-2次，确保充分恢复。"
            elif mid_pct >= 50:
                return f"平均心率 {hr}bpm。{zone_summary}处于中等强度区域。建议将大部分训练（80%）放在更低的心率区间，只在少数关键课次（20%）进入中高强度。"
            else:
                return f"平均心率 {hr}bpm。{zone_summary}强度分布合理，继续保持。"
        else:
            # Fallback to simple HR-based assessment
            if hr < 135:
                return f"这次训练心率保持在 {hr}bpm，属于典型的轻松跑。这种低强度训练能有效提升有氧基础。"
            elif hr < 155:
                return f"心率在 {hr}bpm 区间，处于有氧耐力区。属于中等强度训练。"
            elif hr < 170:
                return f"心率达到 {hr}bpm，已进入高强度区间。这类训练每周控制在1-2次即可。"
            else:
                return f"心率达到 {hr}bpm 的高强度区间。建议之后安排轻松跑或完全休息。"
    return "根据配速和距离判断，这次训练强度适中。"


def _format_comparison_text(comp: dict) -> str:
    parts = []
    if comp.get("trend_distance"):
        td = comp["trend_distance"]
        if td["direction"] == "up":
            parts.append(f"距离比近期均值 {td['recent_avg']}km 多了 {td['diff']}km，跑量在提升")
        elif td["direction"] == "down":
            parts.append(f"距离比近期均值 {td['recent_avg']}km 少了 {abs(td['diff'])}km，跑量有所降低")
        else:
            parts.append(f"距离与近期均值 {td['recent_avg']}km 基本持平")

    if comp.get("trend_pace"):
        tp = comp["trend_pace"]
        if tp["direction"] == "up":
            parts.append(f"配速比近期均值 {tp['recent_avg']} 更快，速度能力在提升")
        elif tp["direction"] == "down":
            parts.append(f"配速比近期均值 {tp['recent_avg']} 偏慢，可能是刻意控制强度或身体疲劳")
        else:
            parts.append(f"配速与近期均值 {tp['recent_avg']} 基本一致，输出稳定")

    if comp.get("trend_hr"):
        th = comp["trend_hr"]
        if th["direction"] == "up":
            parts.append(f"心率比近期均值 {th['recent_avg']}bpm 偏高 {th['diff']}bpm，可能需要更多恢复时间")
        elif th["direction"] == "down":
            parts.append(f"心率比近期均值 {th['recent_avg']}bpm 低 {abs(th['diff'])}bpm，状态不错")
        else:
            parts.append(f"心率与近期基本一致，负荷适应良好")

    return "。".join(parts) + "。" if parts else ""


def _assess_load(a: dict, comp: dict) -> str:
    hr = a.get("avg_hr")
    dur = a.get("duration_min", 0)
    tl = a.get("training_load")
    dist = a.get("distance_km", 0)
    parts = []

    # Use training load if available
    if tl is not None and tl > 0:
        if tl > 150:
            parts.append(f"训练负荷 {tl} 属于高水平，身体需要至少48小时恢复。高强度+高负荷的训练对心肺能力提升显著，但恢复至关重要")
        elif tl > 80:
            parts.append(f"训练负荷 {tl} 处于中等水平，身体负担适中。保持当前节奏，注意训练后营养补充和睡眠")
        else:
            parts.append(f"训练负荷 {tl} 较低，身体负担很小。这是恢复性训练或基础有氧训练的理想负荷范围")
    elif hr and dur:
        # Fallback to HR + duration estimation
        if hr > 155 and dur > 45:
            parts.append("这次训练的累计负荷偏高——高强度配合长时长，身体需要至少48小时恢复")
        elif hr < 140 and dur > 30:
            parts.append("低心率长时长是有氧打基础的优质训练，身体负担可控")
        elif hr > 160 and dur < 30:
            parts.append("短时高强度刺激有利于提升速度能力，今天负荷适中")
        else:
            parts.append("整体训练负荷在合理范围内")

    # Distance-based load
    if dist and dist > 15:
        parts.append(f"{dist}km的长距离对关节和肌肉有较大冲击，确保跑后补充碳水和蛋白质，并安排充足睡眠")

    if comp.get("trend_hr") and comp["trend_hr"]["direction"] == "up":
        parts.append("心率上升趋势值得关注，可能表示身体疲劳累积或恢复不足")

    return "。".join(parts) + "。" if parts else ""


def _generate_suggestions(a: dict, comp: dict) -> str:
    items = []
    hr = a.get("avg_hr")
    pace = a.get("avg_pace")
    pace_sec = _pace_to_sec(pace)
    cadence = a.get("avg_cadence")
    laps = a.get("laps") or []

    # Pace consistency from laps
    if laps and isinstance(laps, list) and len(laps) >= 2:
        lap_paces = []
        for lap in laps:
            if isinstance(lap, dict):
                lp = lap.get("pace") or lap.get("avgPace")
                if lp:
                    ps = _pace_to_sec(lp)
                    if ps:
                        lap_paces.append(ps)
        if len(lap_paces) >= 2:
            max_ps = max(lap_paces)
            min_ps = min(lap_paces)
            spread = max_ps - min_ps
            if spread > 30:
                items.append(f"配速波动较大（最快{_sec_to_pace(min_ps)}/km ~ 最慢{_sec_to_pace(max_ps)}/km，差距{spread}秒），建议训练中控制节奏更均匀，后半程尤其注意不掉速")
            elif spread > 15:
                items.append(f"配速有轻度波动（{_sec_to_pace(min_ps)} ~ {_sec_to_pace(max_ps)}），整体控制不错，可以在长距离中更注重后半程配速保持")
            else:
                items.append(f"配速非常稳定（{_sec_to_pace(min_ps)} ~ {_sec_to_pace(max_ps)}，差距仅{spread}秒），节奏控制能力出色")

    # HR reasonableness
    if hr:
        if hr > 155:
            items.append(f"本次平均心率偏高（{hr}bpm），下次同类训练建议将配速放慢 10-15 秒，控制在有氧区间内，能获得更好的训练效果")
        elif hr < 130:
            items.append(f"心率控制得很好（{hr}bpm），轻松跑的基础很扎实，继续保持这个心率区间")

    # Cadence analysis
    if cadence:
        if cadence < 160:
            items.append(f"步频偏低（{cadence} 步/分），建议适当提高至 170-180 步/分，减小步幅能降低膝盖和踝关节的冲击力")
        elif cadence > 180:
            items.append(f"步频优秀（{cadence} 步/分），高步频有助于减少地面反作用力，降低受伤风险")

    # Trend-based suggestions
    if comp.get("trend_pace") and comp["trend_pace"]["direction"] == "up":
        items.append("速度正在提升，建议每两周做一次短距离冲刺（100m × 6组），进一步刺激神经肌肉适应")

    if comp.get("trend_distance") and comp["trend_distance"]["direction"] == "up":
        items.append("跑量在增加，注意每周增量不超过10%，避免受伤")

    if comp.get("trend_hr") and comp["trend_hr"]["direction"] == "up":
        items.append("心率有上升趋势，可能表示身体疲劳累积，建议保证充足睡眠，下次训练前评估身体感受")

    # Long run hydration
    if a.get("distance_km", 0) > 10:
        items.append("长距离跑步建议携带补给，每45分钟补充一次水分和能量")

    if len(items) < 2:
        items.append("继续保持规律训练，建议每周安排一次长距离慢跑作为有氧基础训练")

    return "。".join(items[:4]) + "。"


def _next_session_advice(a: dict) -> str:
    hr = a.get("avg_hr")
    dist = a.get("distance_km", 0)
    pace_sec = _pace_to_sec(a.get("avg_pace"))
    cadence = a.get("avg_cadence")
    hr_zones = a.get("hr_zones") or []

    # Check if session was high intensity
    high_intensity = False
    if hr_zones and isinstance(hr_zones, list):
        total_sec = sum(z.get("timeSec", z.get("duration", 0)) or 0 for z in hr_zones if isinstance(z, dict))
        high_sec = 0
        for z in hr_zones:
            if not isinstance(z, dict):
                continue
            name = z.get("zoneName", z.get("name", ""))
            if "阈" in name or "无氧" in name or "极限" in name:
                high_sec += z.get("timeSec", z.get("duration", 0)) or 0
        if total_sec > 0 and high_sec / total_sec > 0.2:
            high_intensity = True
    elif hr and hr > 155:
        high_intensity = True

    if high_intensity:
        return "下一次安排轻松跑，心率控制在有氧区间（对话测试：能完整说话不喘），距离4-6km即可，让身体充分恢复。高强度训练后的充分恢复比训练本身更重要。"

    if cadence and cadence < 160:
        return "下次训练可以专注于步频练习，尝试保持170步/分左右，缩小步幅配合高步频，距离4-5km即可。可以使用节拍器辅助。"

    if dist and dist > 10:
        return "下次适合做一次短距离恢复跑（3-4km），或者完全休息一天，让肌肉和关节充分修复。长距离后的48小时是恢复关键期。"

    if pace_sec and pace_sec < 330:  # faster than 5:30/km
        return "建议下次跑一次中等距离（5-7km），配速比本次慢15-20秒，专注于跑姿的流畅性而非速度。每一步「轻落快提」，感受髋关节发力。"

    return "下次训练建议：在本次基础上尝试增加1-2km距离，保持相同配速和心率区间，逐步建立有氧耐力基础。每次增加距离不超过10%。"
