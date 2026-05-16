"""
AI 跑步教练 — 基于 COROS MCP 数据的结构化分析 + LLM 生成建议
"""

import base64, httpx, logging
from datetime import date, timedelta
from sqlalchemy.orm import Session

from config import ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
from db.user import User
from db.training import TrainingPlan
from db.checkin import DailyCheckin
from db.metrics import FitnessMetrics
from db.activity import ActivityRecord
from services.philosophies import get_philosophy

logger = logging.getLogger(__name__)

# ── System Prompt ──

SYSTEM_PROMPT = """你是一位资深跑步教练，名叫「煜煜子」，专精 80/20 极化训练和运动科学数据分析。

## 自我介绍
初次对话或用户询问你是谁时，自称「煜煜子」，可以简单介绍自己的教练风格。

## 你的专业领域
- 80/20 极化训练：80% 低强度有氧 + 20% 中高强度
- 训练周期化：基础期 → 进展期 → 巅峰期 → 减量期
- 运动生理学：心率区间、乳酸阈值、VO₂max、HRV、训练负荷
- 跑步技术：步频、步幅、触地时间、垂直振幅
- 赛事策略：配速、补给、体能分配

## 说话风格
你是一只精通运动科学的猫系教练，说话风格融合以下特质：
- **犀利**：直击要害，不拐弯抹角。比如"你这周跑量涨太快了，膝盖不想要了是吧？"
- **幽默**：用风趣的比喻解释科学原理。"你的 AC/CT 比值 1.5，翻译成人话就是——你已经把自己逼到墙角了。"
- **可爱**：适度卖萌，但保持专业内核，不要油腻。
- **同理心**：理解跑者的焦虑和执着，先倾听再建议。"我懂你想破三的心情，但身体不会撒谎。"

## 喵规则（非常重要）
- 在多数句子末尾加上「喵~」
- 但不是每句都加——连续三句全加会显得烦人，适当穿插正常结尾
- 严肃分析（数据解读、风险警告）时喵要克制，建议性语句可以多喵
- 喵和标点之间不需要空格，直接「喵~」
- 示例：「你的 VO₂max 在提升，这条训练道路走对了喵~」「HRV 还在降，先把跑量砍掉 30% 再说。」

## 回答原则
1. 基于用户的实际数据给出具体、可执行的建议
2. 引用运动科学依据，而非个人经验
3. 量化建议：给出具体配速区间、训练时长、周跑量调整幅度
4. 分析训练负荷 (AC/CT 比值) 和恢复状态 (HRV/RHR/睡眠) 的平衡
5. 用中文回答，关键术语保留英文"""


# ── COROS Pre-analysis Pipeline ──

def _get_coros_analysis(user: User, db: Session) -> dict:
    """Fetch COROS data via native API and compute structured analysis.

    Returns a dict with keys:
      - athlete: VO2max, running_level, threshold_pace, race_predictions
      - load: acute_load, chronic_load, ac_ratio, ratio_trend, risk_level, load_comment
      - recovery: hrv_latest, hrv_baseline, hrv_deviation, rhr_latest, rhr_trend,
                  recovery_score, sleep_avg, sleep_trend, deep_sleep_pct
      - pace_zones: easy, aerobic, threshold, interval (all in /km format)
      - stamina: current, trend_7d
    """
    result: dict = {"athlete": {}, "load": {}, "recovery": {}, "pace_zones": {}, "stamina": {}}

    try:
        from services.coros_mcp_cli import _get_coros_client, asyncio_run

        auth = _get_coros_client(user_id=user.id, db=db)
        if auth is None:
            return result

        import coros_api

        # ── 1. Athlete profile (VO2max, race predictions, threshold pace) ──
        try:
            profile = asyncio_run(coros_api.fetch_athlete_profile(auth))
            if profile:
                result["athlete"] = {
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

        # ── 2. Daily records (30 days for load/recovery trends) ──
        today = date.today()
        start = (today - timedelta(days=30)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")

        try:
            records = asyncio_run(coros_api.fetch_daily_records(auth, start, end))
            if records:
                result["load"] = _compute_load_status(records)
                result["recovery"].update(_compute_recovery_status(records))
                result["stamina"] = _compute_stamina_status(records)
        except Exception:
            pass

        # ── 3. Sleep detail (14 days for phase breakdown) ──
        try:
            sleep_start = (today - timedelta(days=14)).strftime("%Y%m%d")
            sleep_records = asyncio_run(coros_api.fetch_sleep(auth, sleep_start, end))
            if sleep_records:
                result["recovery"].update(_compute_sleep_status(sleep_records))
        except Exception:
            pass

        # ── 4. Pace zones from threshold pace ──
        tp = result["athlete"].get("threshold_pace")
        if tp:
            result["pace_zones"] = _compute_pace_zones(tp)

    except Exception as e:
        logger.warning(f"COROS analysis pipeline error: {e}")

    return result


def _get_local_db_analysis(user: User, db: Session) -> dict:
    """Fallback: compute structured analysis from local DB when COROS API is unavailable.

    Reads from FitnessMetrics (CSV-imported or manually entered) and ActivityRecord
    to produce the same analysis structure as the COROS API pipeline.
    """
    result: dict = {"athlete": {}, "load": {}, "recovery": {}, "pace_zones": {}, "stamina": {}}

    today = date.today()
    metrics = (
        db.query(FitnessMetrics)
        .filter(FitnessMetrics.user_id == user.id)
        .order_by(FitnessMetrics.date.desc())
        .limit(60).all()
    )
    if not metrics:
        return result

    # ── Athlete profile extraction ──
    vo2max_vals = [m.vo2max for m in metrics if m.vo2max]
    if vo2max_vals:
        result["athlete"]["vo2max"] = max(vo2max_vals)

    # Estimate threshold pace from best 5K/10K time
    activities = (
        db.query(ActivityRecord)
        .filter(ActivityRecord.user_id == user.id, ActivityRecord.distance_km.isnot(None),
                ActivityRecord.duration_sec.isnot(None))
        .order_by(ActivityRecord.activity_date.desc())
        .limit(100).all()
    )
    tp = _estimate_threshold_pace(activities)
    if tp:
        result["athlete"]["threshold_pace"] = tp
        result["pace_zones"] = _compute_pace_zones(tp)

    # Extract best race performances for predictions
    race_preds = _extract_race_bests(activities)
    if race_preds:
        result["athlete"]["race_predictions"] = race_preds

    # ── Load status from local metrics ──
    ati_vals = []
    cti_vals = []
    ratios = []
    for m in reversed(metrics):  # chronological order
        if m.ati is not None and m.ati > 0:
            ati_vals.append(float(m.ati))
        if m.cti is not None and m.cti > 0:
            cti_vals.append(float(m.cti))
        if m.training_load_ratio is not None and m.training_load_ratio > 0:
            ratios.append(float(m.training_load_ratio))

    if ratios or ati_vals:
        result["load"] = _compute_load_status_local(ati_vals, cti_vals, ratios)

    # ── Recovery status from local metrics ──
    hrv_vals = [int(m.hrv) for m in metrics if m.hrv and m.hrv > 0]
    rhr_vals = [int(m.resting_hr) for m in metrics if m.resting_hr and m.resting_hr > 0]
    rec_vals = [int(m.recovery_score) for m in metrics if m.recovery_score is not None and m.recovery_score >= 0]

    recovery: dict = {
        "hrv_latest": hrv_vals[0] if hrv_vals else None,
        "rhr_latest": rhr_vals[0] if rhr_vals else None,
        "recovery_score": rec_vals[0] if rec_vals else None,
        "hrv_status": "", "rhr_status": "", "sleep_status": "",
    }

    if len(hrv_vals) >= 14:
        baseline = sum(hrv_vals[1:15]) / min(len(hrv_vals) - 1, 14)
        recovery["hrv_baseline"] = round(baseline, 0)
        if baseline > 0:
            dev = (hrv_vals[0] - baseline) / baseline * 100
            recovery["hrv_deviation"] = round(dev, 1)
            if dev < -20:
                recovery["hrv_status"] = "⚠️ HRV 显著低于基线 (恢复不足/过度训练信号)"
            elif dev < -10:
                recovery["hrv_status"] = "HRV 略低于基线 (注意恢复)"
            elif dev > 10:
                recovery["hrv_status"] = "HRV 高于基线 (良好的适应状态)"
            else:
                recovery["hrv_status"] = "HRV 稳定，自主神经状态良好"

    if len(rhr_vals) >= 14:
        recent_avg = sum(rhr_vals[0:7]) / min(len(rhr_vals), 7)
        prev_avg = sum(rhr_vals[7:14]) / max(len(rhr_vals) - 7, 1)
        diff = recent_avg - prev_avg
        if diff > 5:
            recovery["rhr_trend"] = "rising"
            recovery["rhr_status"] = f"⚠️ 静息心率上升 {diff:.0f}bpm (疲劳/恢复不足信号)"
        elif diff > 3:
            recovery["rhr_trend"] = "slightly_rising"
            recovery["rhr_status"] = f"静息心率微升 {diff:.0f}bpm，关注恢复"
        elif diff < -3:
            recovery["rhr_trend"] = "falling"
            recovery["rhr_status"] = "静息心率下降 (体能进步信号)"
        else:
            recovery["rhr_status"] = "静息心率稳定"

    result["recovery"] = recovery

    # ── Sleep status ──
    sleep_hours = [float(m.sleep_hours) for m in metrics if m.sleep_hours and m.sleep_hours > 0]
    deep_mins = [m.deep_sleep_min for m in metrics if m.deep_sleep_min and m.deep_sleep_min > 0]
    rem_mins = [m.rem_sleep_min for m in metrics if m.rem_sleep_min and m.rem_sleep_min > 0]
    qualities = [m.sleep_quality for m in metrics if m.sleep_quality and m.sleep_quality > 0]

    if sleep_hours:
        avg_sleep = round(sum(sleep_hours[:7]) / min(len(sleep_hours), 7), 1)
        recovery["sleep_avg"] = avg_sleep
        if len(sleep_hours) >= 14:
            recent = sum(sleep_hours[:7]) / min(len(sleep_hours[:7]), 7)
            prev = sum(sleep_hours[7:14]) / max(len(sleep_hours[7:14]), 1)
            if recent > prev + 0.5:
                recovery["sleep_trend"] = "improving"
            elif recent < prev - 0.5:
                recovery["sleep_trend"] = "declining"

        if avg_sleep < 6.5:
            recovery["sleep_status"] = f"⚠️ 睡眠严重不足 ({avg_sleep}h)，这是恢复的头号瓶颈"
        elif avg_sleep < 7.5:
            recovery["sleep_status"] = f"睡眠偏少 ({avg_sleep}h)，建议增加至 7.5h+"
        else:
            recovery["sleep_status"] = f"睡眠充足 ({avg_sleep}h)"

    if deep_mins and sleep_hours:
        avg_deep_pct = sum(d / (s * 60) * 100 for d, s in zip(deep_mins[:7], sleep_hours[:7])) / min(len(deep_mins), 7)
        recovery["deep_sleep_pct"] = round(avg_deep_pct, 1)
    if rem_mins and sleep_hours:
        avg_rem_pct = sum(r / (s * 60) * 100 for r, s in zip(rem_mins[:7], sleep_hours[:7])) / min(len(rem_mins), 7)
        recovery["rem_sleep_pct"] = round(avg_rem_pct, 1)
    if qualities:
        recovery["sleep_quality_avg"] = round(sum(qualities[:7]) / min(len(qualities), 7), 0)

    # ── Stamina ──
    stamina = [m.stamina_level for m in metrics if m.stamina_level is not None]
    stamina_7d = [m.stamina_7d for m in metrics if m.stamina_7d is not None]
    if stamina:
        result["stamina"] = {
            "stamina_level": stamina[0],
            "stamina_7d": stamina_7d[0] if stamina_7d else None,
        }

    return result


def _compute_load_status_local(ati_vals: list, cti_vals: list, ratios: list) -> dict:
    """Compute load status from local DB metric arrays (same logic as COROS version)."""
    result: dict = {"acute_load": None, "chronic_load": None, "ac_ratio": None,
                     "ratio_trend": "stable", "risk_level": "unknown", "load_comment": ""}

    if ati_vals:
        result["acute_load"] = round(ati_vals[-1], 0)
    if cti_vals:
        result["chronic_load"] = round(cti_vals[-1], 0)

    if ratios:
        latest = ratios[-1]
        result["ac_ratio"] = round(latest, 2)
        if len(ratios) >= 14:
            recent_avg = sum(ratios[-7:]) / 7
            prev_avg = sum(ratios[-14:-7]) / 7
            if recent_avg > prev_avg * 1.05:
                result["ratio_trend"] = "rising"
            elif recent_avg < prev_avg * 0.95:
                result["ratio_trend"] = "falling"

        if latest > 1.5:
            result["risk_level"] = "high"
            result["load_comment"] = "训练负荷过高，有过度训练风险。建议立即减量 30-40%，增加恢复日。"
        elif latest > 1.3:
            result["risk_level"] = "elevated"
            result["load_comment"] = "功能型过量。训练刺激充足但需注意恢复，建议本周减量 15-20%。"
        elif latest > 1.0:
            result["risk_level"] = "optimal"
            result["load_comment"] = "负荷适中，处于最佳训练刺激区间。可维持当前训练量。"
        elif latest > 0.8:
            result["risk_level"] = "low"
            result["load_comment"] = "负荷偏低，训练刺激不足。可适度增加跑量或强度。"
        else:
            result["risk_level"] = "detraining"
            result["load_comment"] = "负荷过低，存在能力退化风险。建议逐步恢复训练。"

    return result


def _estimate_threshold_pace(activities) -> str | None:
    """Estimate threshold pace from best 5K or 10K time using Riegel formula."""
    best_5k_sec = None
    best_10k_sec = None

    for a in activities:
        dist = a.distance_km or 0
        dur = a.duration_sec or 0
        if dist <= 0 or dur <= 0:
            continue
        if 4.8 <= dist <= 5.2:
            pace_sec = dur / dist
            best_5k_sec = min(best_5k_sec, pace_sec) if best_5k_sec else pace_sec
        if 9.7 <= dist <= 10.3:
            pace_sec = dur / dist
            best_10k_sec = min(best_10k_sec, pace_sec) if best_10k_sec else pace_sec

    # Prefer 10K pace as threshold estimate (closer to lactate threshold)
    ref_pace = best_10k_sec or best_5k_sec
    if not ref_pace:
        return None

    # 10K pace ≈ 105% of threshold pace; 5K ≈ 110%
    if best_10k_sec:
        tp_sec = best_10k_sec / 1.05
    else:
        tp_sec = best_5k_sec / 1.10

    m = int(tp_sec // 60)
    s = int(tp_sec % 60)
    return f"{m}:{s:02d}"


def _extract_race_bests(activities) -> dict:
    """Extract best race performances at standard distances."""
    bests: dict = {}
    dist_map = [(5.0, "5k"), (10.0, "10k"), (21.1, "half_marathon"), (42.2, "marathon")]

    for a in activities:
        dist = a.distance_km or 0
        dur = a.duration_sec or 0
        if dist <= 0 or dur <= 0:
            continue
        for race_dist, key in dist_map:
            if abs(dist - race_dist) / race_dist <= 0.05:
                dur_min = dur / 60
                h = int(dur_min // 60)
                m = int(dur_min % 60)
                s = int(dur % 60)
                time_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
                if key not in bests or dur < bests.get(f"{key}_sec", float("inf")):
                    bests[key] = time_str
                    bests[f"{key}_sec"] = dur

    return {k: v for k, v in bests.items() if not k.endswith("_sec")}


def _compute_load_status(records) -> dict:
    """Compute training load status from 30-day COROS daily records."""
    ati_vals = []
    cti_vals = []
    ratios = []
    comments = []

    for r in records:
        if getattr(r, "ati", None) is not None and getattr(r, "ati", 0) > 0:
            ati_vals.append(float(r.ati))
        if getattr(r, "cti", None) is not None and getattr(r, "cti", 0) > 0:
            cti_vals.append(float(r.cti))
        if getattr(r, "training_load_ratio", None) is not None and r.training_load_ratio > 0:
            ratios.append(float(r.training_load_ratio))

    result: dict = {"acute_load": None, "chronic_load": None, "ac_ratio": None,
                     "ratio_trend": "stable", "risk_level": "unknown", "load_comment": ""}

    if ati_vals:
        result["acute_load"] = round(ati_vals[-1], 0)
    if cti_vals:
        result["chronic_load"] = round(cti_vals[-1], 0)

    if ratios:
        latest = ratios[-1]
        result["ac_ratio"] = round(latest, 2)

        # Trend (compare last 7 vs previous 7)
        if len(ratios) >= 14:
            recent_avg = sum(ratios[-7:]) / 7
            prev_avg = sum(ratios[-14:-7]) / 7
            if recent_avg > prev_avg * 1.05:
                result["ratio_trend"] = "rising"
            elif recent_avg < prev_avg * 0.95:
                result["ratio_trend"] = "falling"

        # Risk level based on AC/CT ratio
        if latest > 1.5:
            result["risk_level"] = "high"
            result["load_comment"] = "训练负荷过高，有过度训练风险。建议立即减量 30-40%，增加恢复日。"
        elif latest > 1.3:
            result["risk_level"] = "elevated"
            result["load_comment"] = "功能型过量。训练刺激充足但需注意恢复，建议本周减量 15-20%。"
        elif latest > 1.0:
            result["risk_level"] = "optimal"
            result["load_comment"] = "负荷适中，处于最佳训练刺激区间。可维持当前训练量。"
        elif latest > 0.8:
            result["risk_level"] = "low"
            result["load_comment"] = "负荷偏低，训练刺激不足。可适度增加跑量或强度。"
        else:
            result["risk_level"] = "detraining"
            result["load_comment"] = "负荷过低，存在能力退化风险。建议逐步恢复训练。"

    return result


def _compute_recovery_status(records) -> dict:
    """Compute recovery status from COROS daily records."""
    hrv_vals = []
    rhr_vals = []
    recovery_vals = []

    for r in records:
        h = getattr(r, "avg_sleep_hrv", None)
        if h is not None and h > 0:
            hrv_vals.append(int(h))
        rhr = getattr(r, "rhr", None)
        if rhr is not None and rhr > 0:
            rhr_vals.append(int(rhr))
        rec = getattr(r, "recovery_score", None)
        if rec is not None and rec > 0:
            recovery_vals.append(int(rec))

    result: dict = {
        "hrv_latest": None, "hrv_baseline": None, "hrv_deviation": None, "hrv_status": "",
        "rhr_latest": None, "rhr_trend": "stable", "rhr_status": "",
        "recovery_score": None,
    }

    if hrv_vals:
        result["hrv_latest"] = hrv_vals[-1]
        if len(hrv_vals) >= 14:
            baseline = sum(hrv_vals[:14]) / min(len(hrv_vals), 14)
            result["hrv_baseline"] = round(baseline, 0)
            if baseline > 0:
                dev = (hrv_vals[-1] - baseline) / baseline * 100
                result["hrv_deviation"] = round(dev, 1)
                if dev < -20:
                    result["hrv_status"] = "⚠️ HRV 显著低于基线 (恢复不足/过度训练信号)"
                elif dev < -10:
                    result["hrv_status"] = "HRV 略低于基线 (注意恢复)"
                elif dev > 10:
                    result["hrv_status"] = "HRV 高于基线 (良好的适应状态)"
                else:
                    result["hrv_status"] = "HRV 稳定，自主神经状态良好"

    if rhr_vals:
        result["rhr_latest"] = rhr_vals[-1]
        if len(rhr_vals) >= 14:
            recent_avg = sum(rhr_vals[-7:]) / 7
            prev_avg = sum(rhr_vals[-14:-7]) / 7
            diff = recent_avg - prev_avg
            if diff > 5:
                result["rhr_trend"] = "rising"
                result["rhr_status"] = f"⚠️ 静息心率上升 {diff:.0f}bpm (疲劳/恢复不足的早期信号)"
            elif diff > 3:
                result["rhr_trend"] = "slightly_rising"
                result["rhr_status"] = f"静息心率微升 {diff:.0f}bpm，关注恢复"
            elif diff < -3:
                result["rhr_trend"] = "falling"
                result["rhr_status"] = "静息心率下降 (体能进步信号)"
            else:
                result["rhr_status"] = "静息心率稳定"

    if recovery_vals:
        result["recovery_score"] = recovery_vals[-1]

    return result


def _compute_sleep_status(sleep_records) -> dict:
    """Compute sleep trends from COROS sleep data."""
    durations = []
    deep_pcts = []
    rem_pcts = []
    qualities = []

    for s in sleep_records:
        dur = getattr(s, "total_duration_minutes", None)
        if dur and dur > 0:
            durations.append(dur / 60)
        phases = getattr(s, "phases", None)
        if phases and dur and dur > 0:
            deep = getattr(phases, "deep_minutes", 0) or 0
            rem = getattr(phases, "rem_minutes", 0) or 0
            deep_pcts.append(deep / dur * 100)
            rem_pcts.append(rem / dur * 100)
        q = getattr(s, "quality_score", None)
        if q and q > 0:
            qualities.append(q)

    result: dict = {"sleep_avg": None, "sleep_trend": "stable", "deep_sleep_pct": None,
                     "rem_sleep_pct": None, "sleep_quality_avg": None, "sleep_status": ""}

    if durations:
        result["sleep_avg"] = round(sum(durations[-7:]) / min(len(durations), 7), 1)
        if len(durations) >= 14:
            recent_avg = sum(durations[-7:]) / min(len(durations[-7:]), 7)
            prev_avg = sum(durations[-14:-7]) / max(len(durations[-14:-7]), 1)
            diff = recent_avg - prev_avg
            if diff > 0.5:
                result["sleep_trend"] = "improving"
            elif diff < -0.5:
                result["sleep_trend"] = "declining"

        if result["sleep_avg"] < 6.5:
            result["sleep_status"] = f"⚠️ 睡眠严重不足 ({result['sleep_avg']}h)，这是恢复的头号瓶颈"
        elif result["sleep_avg"] < 7.5:
            result["sleep_status"] = f"睡眠偏少 ({result['sleep_avg']}h)，建议增加至 7.5h+"
        else:
            result["sleep_status"] = f"睡眠充足 ({result['sleep_avg']}h)"

    if deep_pcts:
        result["deep_sleep_pct"] = round(sum(deep_pcts[-7:]) / min(len(deep_pcts), 7), 1)
    if rem_pcts:
        result["rem_sleep_pct"] = round(sum(rem_pcts[-7:]) / min(len(rem_pcts), 7), 1)
    if qualities:
        result["sleep_quality_avg"] = round(sum(qualities[-7:]) / min(len(qualities), 7), 0)

    return result


def _compute_stamina_status(records) -> dict:
    """Extract stamina trend from daily records."""
    stamina_vals = [(r.stamina_level, r.stamina_level_7d)
                    for r in records
                    if getattr(r, "stamina_level", None) is not None
                    and getattr(r, "stamina_level_7d", None) is not None]
    if stamina_vals:
        latest, trend = stamina_vals[-1]
        return {"stamina_level": latest, "stamina_7d": trend}
    return {}


def _compute_pace_zones(threshold_pace: str) -> dict:
    """Compute training pace zones from threshold pace (format: '4:15' for 4:15/km)."""
    try:
        parts = threshold_pace.strip().split(":")
        tp_sec = int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return {}

    def _fmt(sec: float) -> str:
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m}:{s:02d}"

    return {
        "threshold_pace": threshold_pace,
        "easy": f"{_fmt(tp_sec * 1.25)}-{_fmt(tp_sec * 1.40)}/km",
        "aerobic": f"{_fmt(tp_sec * 1.08)}-{_fmt(tp_sec * 1.20)}/km",
        "threshold": f"{_fmt(tp_sec * 0.97)}-{_fmt(tp_sec * 1.03)}/km",
        "interval": f"快于 {_fmt(tp_sec * 0.92)}/km",
        "recovery": f"慢于 {_fmt(tp_sec * 1.45)}/km",
    }


# ── Structured Context Builder ──

def _build_structured_context(user: User, db: Session) -> str:
    """Build structured analysis context for the LLM.

    Layers (in priority order):
    1. COROS pre-analysis (athlete profile, load, recovery, pace zones)
    2. Local DB training plans
    3. Local DB recent activities
    4. Checkin mood data
    """
    sections = []

    # ── Layer 1: COROS Analysis (with local DB fallback) ──
    coros = _get_coros_analysis(user, db)

    # Fallback: if COROS API unavailable, compute from local DB
    has_coros_data = bool(coros.get("athlete") or coros.get("load") or coros.get("recovery", {}).get("hrv_latest"))
    if not has_coros_data:
        coros = _get_local_db_analysis(user, db)

    athlete = coros.get("athlete", {})
    if athlete.get("vo2max") or athlete.get("threshold_pace"):
        lines = ["## COROS 体能评估"]
        if athlete.get("vo2max"):
            lines.append(f"- VO₂max: {athlete['vo2max']}")
        if athlete.get("running_level"):
            lines.append(f"- 跑步等级: {athlete['running_level']}")
        if athlete.get("threshold_pace"):
            lines.append(f"- 阈值配速: {athlete['threshold_pace']}/km")
        rp = athlete.get("race_predictions", {})
        if rp:
            preds = ", ".join(f"{k}={v}" for k, v in rp.items() if v)
            if preds:
                lines.append(f"- 赛事预测: {preds}")
        sections.append("\n".join(lines))

    load = coros.get("load", {})
    if load.get("ac_ratio") is not None:
        lines = ["## 训练负荷分析"]
        lines.append(f"- 急性负荷(ATI): {load.get('acute_load', '?')} | 慢性负荷(CTI): {load.get('chronic_load', '?')}")
        lines.append(f"- AC/CT 比值: {load['ac_ratio']:.2f}")
        lines.append(f"- 趋势: {load.get('ratio_trend', 'stable')}")
        lines.append(f"- 风险等级: **{load.get('risk_level', 'unknown').upper()}**")
        if load.get("load_comment"):
            lines.append(f"- 评价: {load['load_comment']}")
        sections.append("\n".join(lines))

    recovery = coros.get("recovery", {})
    if recovery:
        lines = ["## 恢复状态分析"]
        if recovery.get("hrv_latest"):
            lines.append(f"- HRV 最新: {recovery['hrv_latest']}ms"
                         + (f" (基线: {recovery.get('hrv_baseline', '?')}ms, {recovery.get('hrv_status', '')})" if recovery.get("hrv_baseline") else ""))
        if recovery.get("rhr_latest"):
            lines.append(f"- 静息心率: {recovery['rhr_latest']}bpm — {recovery.get('rhr_status', '')}")
        if recovery.get("recovery_score") is not None:
            lines.append(f"- 恢复度: {recovery['recovery_score']}%")
        if recovery.get("sleep_avg"):
            lines.append(f"- 平均睡眠: {recovery['sleep_avg']}h — {recovery.get('sleep_status', '')}"
                         + (f" (深睡 {recovery.get('deep_sleep_pct', '?')}%, REM {recovery.get('rem_sleep_pct', '?')}%)" if recovery.get("deep_sleep_pct") else ""))
        if recovery.get("sleep_quality_avg"):
            lines.append(f"- 睡眠质量评分: {recovery['sleep_quality_avg']}")
        sections.append("\n".join(lines))

    stamina = coros.get("stamina", {})
    if stamina.get("stamina_level"):
        lines = ["## 体能状态"]
        lines.append(f"- 体能水平: {stamina['stamina_level']:.1f}")
        if stamina.get("stamina_7d"):
            lines.append(f"- 7日趋势: {stamina['stamina_7d']:.1f}")
        sections.append("\n".join(lines))

    pace_zones = coros.get("pace_zones", {})
    if pace_zones:
        lines = ["## 训练配速区间 (基于阈值配速)"]
        for label, zone in [("恢复跑", "recovery"), ("轻松跑", "easy"), ("有氧跑", "aerobic"),
                             ("阈值跑", "threshold"), ("间歇跑", "interval")]:
            if zone in pace_zones:
                lines.append(f"- {label}: {pace_zones[zone]}")
        sections.append("\n".join(lines))

    # ── Layer 2: Training Plans ──
    from db.training import TrainingSession as TS
    from services.philosophies import get_philosophy as gp
    plans = db.query(TrainingPlan).filter(TrainingPlan.user_id == user.id).all()
    if plans:
        lines = ["## 当前训练计划"]
        for plan in plans:
            sessions = plan.sessions or []
            completed = sum(1 for s in sessions if s.completed)
            total = len([s for s in sessions if hasattr(s, 'session_type') and
                         s.session_type.value != "rest"])
            pct = round(completed / max(total, 1) * 100)

            ph = plan.philosophy if hasattr(plan, 'philosophy') and plan.philosophy else "polarised_80_20"
            ph_profile = gp(ph)
            ph_name = ph_profile.name if ph_profile else "80/20极化训练"

            lines.append(f"- {plan.name}: {plan.weeks}周, {ph_name}, 目标{plan.target_race}, "
                          f"完成 {completed}/{total} ({pct}%)")

            # Checkpoint results
            checkpoints = [s for s in sessions if hasattr(s, 'is_checkpoint') and s.is_checkpoint and s.checkpoint_result_sec]
            if checkpoints:
                lines.append("  检查点记录:")
                for cp in sorted(checkpoints, key=lambda x: x.week):
                    result = f"{cp.checkpoint_result_sec // 60}:{cp.checkpoint_result_sec % 60:02d}"
                    lines.append(f"    第{cp.week}周: {result}")

        sections.append("\n".join(lines))

    # ── Layer 3: Recent Activities ──
    activities = db.query(ActivityRecord).filter(
        ActivityRecord.user_id == user.id
    ).order_by(ActivityRecord.activity_date.desc()).limit(14).all()

    if activities:
        lines = ["## 近期运动记录"]
        for a in activities[:10]:
            dur = round(a.duration_sec / 60, 1) if a.duration_sec else "?"
            parts = [f"{a.activity_date}:"]
            if a.distance_km: parts.append(f"{a.distance_km}km")
            if a.avg_pace: parts.append(f"配速{a.avg_pace}")
            if a.avg_hr: parts.append(f"心率{a.avg_hr}")
            parts.append(f"{dur}min")
            if a.elevation_gain: parts.append(f"爬升{a.elevation_gain}m")
            lines.append("- " + " ".join(parts))

        # Weekly summary
        recent7 = activities[:7]
        weekly_km = sum(a.distance_km or 0 for a in recent7)
        weekly_runs = len([a for a in recent7 if a.distance_km])
        hr_vals = [a.avg_hr for a in recent7 if a.avg_hr]
        weekly_hr = int(sum(hr_vals) / len(hr_vals)) if hr_vals else 0
        lines.append(f"\n近7天: 跑量 {weekly_km:.1f}km, {weekly_runs}次, 平均心率 {weekly_hr}bpm")

        # Week-over-week comparison
        prev7 = activities[7:14]
        prev_km = sum(a.distance_km or 0 for a in prev7)
        if prev_km > 0:
            diff_pct = (weekly_km - prev_km) / prev_km * 100
            trend = "增加" if diff_pct > 5 else "减少" if diff_pct < -5 else "持平"
            lines.append(f"vs 前7天: 跑量{trend} ({diff_pct:+.0f}%)")

        sections.append("\n".join(lines))

    # ── Layer 4: Mood Checkins ──
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == user.id
    ).order_by(DailyCheckin.date.desc()).limit(7).all()
    if checkins:
        moods = [c.mood for c in checkins if c.mood]
        if moods:
            avg_mood = sum(moods) / len(moods)
            status = "良好" if avg_mood >= 4 else "一般" if avg_mood >= 3 else "偏低"
            lines = ["## 体感状态"]
            lines.append(f"近7天平均心情: {avg_mood:.1f}/5 — {status}")
            sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _build_context_summary(coros: dict) -> str:
    """Build a one-line executive summary for the LLM to orient immediately."""
    parts = []

    athlete = coros.get("athlete", {})
    if athlete.get("vo2max"):
        parts.append(f"VO₂max {athlete['vo2max']}")
    if athlete.get("threshold_pace"):
        parts.append(f"阈值配速 {athlete['threshold_pace']}")

    load = coros.get("load", {})
    if load.get("risk_level"):
        risk_labels = {"high": "🔴 高风险", "elevated": "🟡 偏高", "optimal": "🟢 最佳",
                       "low": "🔵 偏低", "detraining": "⚪ 过低"}
        parts.append(f"负荷: {risk_labels.get(load['risk_level'], load['risk_level'])}")

    recovery = coros.get("recovery", {})
    warnings = []
    if recovery.get("hrv_deviation") is not None and recovery["hrv_deviation"] < -15:
        warnings.append("HRV显著下降")
    if recovery.get("rhr_trend") == "rising":
        warnings.append("RHR上升中")
    if recovery.get("sleep_avg") and recovery["sleep_avg"] < 6.5:
        warnings.append("睡眠不足")
    if warnings:
        parts.append(f"⚠️ {', '.join(warnings)}")

    return " | ".join(parts) if parts else ""


# ── Checkpoint Analysis ──

CHECKPOINT_SYSTEM_PROMPT = """你是一位遵循「护栏约束模式」的跑步教练。当前用户刚完成了一次检查点测试。

## 分析规则
1. 对比本次成绩和上次成绩，判断趋势（进步/退步/平台）
2. 你可以建议调整以下变量中的 **仅一个**：
   - weekly_volume（周跑量）
   - intensity_distribution（强度配比）
   - long_run_distance（长距离距离）
   - recovery_days（恢复天数）
   - session_pace（训练配速）
3. **严禁**建议更换训练哲学
4. 如果恢复指标（HRV/RHR/睡眠）有异常，优先建议降低训练负荷
5. 给出具体的调整幅度（例如"下周跑量降低 10%"，而不只是"降低跑量"）

## 输出格式
1. 检查点成绩对比（一句话）
2. 趋势判断 + 可能的短板
3. 推荐调整的一个变量 + 具体幅度
4. 调整后的预期效果

用中文回答，保持煜煜子的猫系风格喵~"""


async def analyze_checkpoint(
    user: User,
    plan: TrainingPlan,
    checkpoint_week: int,
    current_result_sec: int,
    previous_result_sec: int | None,
    delta_pct: float | None,
    trend: str,
    db: Session,
    provider: str = "deepseek",
    api_key: str = "",
    model: str = "",
) -> str:
    """用AI分析检查点测试结果，给出单变量调整建议"""
    philosophy = get_philosophy(plan.philosophy or "polarised_80_20")
    ph_label = philosophy.name if philosophy else "80/20 极化训练"

    delta_text = ""
    if previous_result_sec and delta_pct is not None:
        direction = "快于" if delta_pct > 0 else "慢于"
        prev_str = f"{previous_result_sec // 60}:{previous_result_sec % 60:02d}"
        curr_str = f"{current_result_sec // 60}:{current_result_sec % 60:02d}"
        delta_text = f"上次: {prev_str} | 本次: {curr_str} | {direction}上次 {abs(delta_pct)}%"

    user_msg = f"""## 检查点分析 - 第{checkpoint_week}周

训练哲学: {ph_label}
体能水平: {plan.fitness_level or '未知'}
近期成绩: {plan.recent_race_result or '未提供'}
伤病备注: {plan.injury_notes or '无'}

检查点结果:
- 趋势: {trend}
- {delta_text}

请分析这次检查点的结果，并根据护栏约束模式给出单变量调整建议。"""

    context = _build_structured_context(user, db)
    full_system = f"{CHECKPOINT_SYSTEM_PROMPT}\n\n## 用户训练数据\n{context if context else '暂无数据'}"

    if provider == "deepseek":
        key = api_key or DEEPSEEK_API_KEY
        if key:
            return await _call_deepseek(full_system, user_msg, key, model)
    elif provider == "claude":
        key = api_key or ANTHROPIC_API_KEY
        if key:
            return await _call_claude(full_system, user_msg, key, model)
    elif provider == "openai":
        key = api_key or OPENAI_API_KEY
        if key:
            return await _call_openai(full_system, user_msg, key, model)
    elif provider == "gemini":
        key = api_key or GOOGLE_API_KEY
        if key:
            return await _call_gemini(full_system, user_msg, key, model)

    return _fallback_checkpoint_reply(trend, delta_text, plan.philosophy or "polarised_80_20")


def _fallback_checkpoint_reply(trend: str, delta_text: str, philosophy_key: str) -> str:
    """无API Key时的检查点分析回退"""
    trend_labels = {
        "improving": "在进步",
        "declining": "有所退步",
        "plateauing": "处于平台期",
        "baseline": "是第一个检查点",
    }
    advice = {
        "improving": "继续保持当前训练节奏，不急着加量喵~ 先巩固适应再考虑微调。",
        "declining": "建议先降低 10% 周跑量或增加一天恢复日。HRV 下降是身体在说话喵~",
        "plateauing": "可以尝试调整一次强度课的配速（比当前快 5s/km），给身体新的刺激。",
        "baseline": "第一个检查点作为基准线。接下来4周保持训练一致性是最重要的事喵~",
    }
    return f"""## 检查点分析

{delta_text or '首次检查点 - 建立基准线'}

趋势: {trend_labels.get(trend, trend)}

### 建议
{advice.get(trend, '请保持训练一致性。')}

---
*提示：配置 API Key 后可获得 AI 教练的详细分析喵~*"""


# ── Main Chat Functions ──

async def ai_coach_chat(message: str, user: User, db: Session, provider: str = "deepseek", api_key: str = "", model: str = "") -> str:
    context = _build_structured_context(user, db)
    full_system = f"{SYSTEM_PROMPT}\n\n## 当前训练数据\n{context if context else '用户暂无训练数据'}\n\n请基于以上数据进行专业分析并回答用户问题。"

    if provider == "deepseek":
        key = api_key or DEEPSEEK_API_KEY
        if key:
            return await _call_deepseek(full_system, message, key, model)
    elif provider == "claude":
        key = api_key or ANTHROPIC_API_KEY
        if key:
            return await _call_claude(full_system, message, key, model)
    elif provider == "openai":
        key = api_key or OPENAI_API_KEY
        if key:
            return await _call_openai(full_system, message, key, model)
    elif provider == "gemini":
        key = api_key or GOOGLE_API_KEY
        if key:
            return await _call_gemini(full_system, message, key, model)

    return _fallback_reply(context)


async def analyze_screenshot(image_path: str, message: str, user: User, db: Session, provider: str = "deepseek", api_key: str = "", model: str = "") -> str:
    context = _build_structured_context(user, db)
    system = f"""你是一位专业跑步教练，擅长分析运动数据截图（Keep、悦跑圈、Strava、Garmin、Coros 等）。

请先分析截图中的数据，再结合以下用户历史训练数据进行综合分析：

{context}

请按以下结构输出：
1. **截图数据概况** — 从截图中提取的关键数据
2. **与历史数据对比** — 本次表现 vs 近期趋势
3. **短板诊断** — 2-3 个关键问题（结合负荷、恢复、配速数据）
4. **优化建议** — 具体、可执行的训练调整方案
5. **风险提示** — 如发现过度训练风险或恢复不足"""

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    user_msg = message or "请分析这张运动数据截图，结合我的训练历史给出综合分析"

    if provider == "deepseek":
        key = api_key or DEEPSEEK_API_KEY
        if key:
            return await _call_deepseek_vision(system, user_msg, img_b64, key, model)
    elif provider == "claude":
        key = api_key or ANTHROPIC_API_KEY
        if key:
            return await _call_claude_vision(system, user_msg, img_b64, key, model)
    elif provider == "openai":
        key = api_key or OPENAI_API_KEY
        if key:
            return await _call_openai_vision(system, user_msg, img_b64, key, model)
    elif provider == "gemini":
        key = api_key or GOOGLE_API_KEY
        if key:
            return await _call_gemini_vision(system, user_msg, img_b64, key, model)

    return _fallback_reply(context)


# ── LLM API Calls (unchanged) ──

async def _call_deepseek(system: str, user_msg: str, api_key: str, model: str = "") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"DeepSeek API 错误 (HTTP {r.status_code}): {r.text[:200]}"


async def _call_deepseek_vision(system: str, user_msg: str, image_b64: str, api_key: str, model: str = "") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": user_msg},
                    ]},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"DeepSeek API 错误 (HTTP {r.status_code}): {r.text[:200]}"


async def _call_claude(system: str, user_msg: str, api_key: str, model: str = "") -> str:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model or "claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text
    except Exception as e:
        return f"Claude API 错误: {str(e)[:200]}"


async def _call_claude_vision(system: str, user_msg: str, image_b64: str, api_key: str, model: str = "") -> str:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model or "claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": user_msg},
            ]}],
        )
        return response.content[0].text
    except Exception as e:
        return f"Claude API 错误: {str(e)[:200]}"


async def _call_openai(system: str, user_msg: str, api_key: str, model: str = "") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "gpt-4o",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"ChatGPT API 错误 (HTTP {r.status_code}): {r.text[:200]}"


async def _call_openai_vision(system: str, user_msg: str, image_b64: str, api_key: str, model: str = "") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or "gpt-4o",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": user_msg},
                    ]},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"ChatGPT Vision API 错误 (HTTP {r.status_code}): {r.text[:200]}"


async def _call_gemini(system: str, user_msg: str, api_key: str, model: str = "") -> str:
    gemini_model = model or "gemini-2.0-flash"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user_msg}]}],
            },
        )
        if r.status_code == 200:
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return f"Gemini API 错误 (HTTP {r.status_code}): {r.text[:200]}"


async def _call_gemini_vision(system: str, user_msg: str, image_b64: str, api_key: str, model: str = "") -> str:
    gemini_model = model or "gemini-2.0-flash"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    {"text": user_msg},
                ]}],
            },
        )
        if r.status_code == 200:
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return f"Gemini Vision API 错误 (HTTP {r.status_code}): {r.text[:200]}"


def _fallback_reply(context: str) -> str:
    return f"""您好！我是 AI 跑步教练。

由于未配置 API Key，我目前无法进行深度分析。请在「设置」页面配置 API Key：

- **DeepSeek API**：在 https://platform.deepseek.com 获取，性价比高
- **Claude API**：在 https://console.anthropic.com 获取

配置后即可使用 AI 教练功能。

## 当前训练数据
{context if context else '暂无数据'}"""
