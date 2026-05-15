"""
Coros 健康数据管理与每日训练计划动态微调

数据来源（三种方式）：
1. Coros MCP 服务器自动同步
2. 手动录入
3. CSV 文件导入

数据字段：
- 睡眠数据 (时长、质量)
- 静息心率
- HRV (心率变异性)
- 疲劳度 (0-100)
- 恢复度 (0-100)

基于当日数据动态微调训练计划：
- 恢复度 < 40% → 建议休息
- 恢复度 < 60% → 建议降低强度
- 疲劳度 > 75 → 建议休息
- 疲劳度 > 60 → 建议减量
- HRV < 40 → 建议轻松跑
- 睡眠 < 6h → 建议低强度
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session
import httpx

from config import COROS_MCP_URL
from db.user import User
from db.metrics import FitnessMetrics


def sync_from_coros(user: User, db: Session) -> list[FitnessMetrics]:
    """从 Coros MCP 服务器同步健康数据。如无 MCP 地址则返回空。"""
    if not COROS_MCP_URL:
        return []

    try:
        resp = httpx.get(
            f"{COROS_MCP_URL}/metrics",
            params={"days": 14},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        new_metrics = []
        for item in data.get("metrics", []):
            metric_date = (
                date.fromisoformat(item["date"])
                if isinstance(item["date"], str) else item["date"]
            )

            existing = (
                db.query(FitnessMetrics)
                .filter(FitnessMetrics.user_id == user.id, FitnessMetrics.date == metric_date)
                .first()
            )
            if existing:
                continue

            m = FitnessMetrics(
                user_id=user.id,
                date=metric_date,
                sleep_hours=item.get("sleep_hours"),
                sleep_quality=item.get("sleep_quality"),
                resting_hr=item.get("resting_hr"),
                hrv=item.get("hrv"),
                fatigue_score=item.get("fatigue_score"),
                recovery_score=item.get("recovery_score"),
            )
            db.add(m)
            new_metrics.append(m)

        db.commit()
        return new_metrics
    except Exception:
        return []


def import_csv_data(user: User, db: Session, rows: list[dict]) -> int:
    """Import Coros data from parsed CSV rows. Returns count of imported records."""
    imported = 0
    for row_data in rows:
        row_date = row_data.get("date")
        if not row_date:
            continue

        existing = (
            db.query(FitnessMetrics)
            .filter(FitnessMetrics.user_id == user.id, FitnessMetrics.date == row_date)
            .first()
        )

        if existing:
            for key, value in row_data.items():
                if key != "date" and value is not None:
                    setattr(existing, key, value)
        else:
            m = FitnessMetrics(user_id=user.id, **row_data)
            db.add(m)

        imported += 1

    db.commit()
    return imported


def get_daily_adjustment(user: User, db: Session) -> dict:
    """Generate daily training adjustment based on health data."""
    today = date.today()
    today_metric = (
        db.query(FitnessMetrics)
        .filter(FitnessMetrics.user_id == user.id, FitnessMetrics.date == today)
        .first()
    )

    if not today_metric:
        return {"message": "今日暂无健康数据，请前往设置页录入", "adjustment": "none"}

    suggestions = []
    adjustment = "none"

    if today_metric.recovery_score is not None:
        if today_metric.recovery_score < 40:
            adjustment = "rest"
            suggestions.append("恢复度偏低，建议今日完全休息或仅做 20-30 分钟轻松散步")
        elif today_metric.recovery_score < 60:
            adjustment = "reduce"
            suggestions.append("恢复度一般，建议降低训练强度，将高强度课改为轻松跑")

    if today_metric.fatigue_score is not None:
        if today_metric.fatigue_score > 75:
            adjustment = "rest"
            suggestions.append("疲劳度较高，注意过度训练风险，建议安排休息日")
        elif today_metric.fatigue_score > 60:
            if adjustment == "none":
                adjustment = "reduce"
            suggestions.append("有一定疲劳累积，减少今日训练量 20-30%")

    if today_metric.hrv is not None and today_metric.hrv < 40:
        suggestions.append("HRV 偏低，交感神经活跃，身体可能处于应激状态，建议轻松跑 + 充足睡眠")

    if today_metric.sleep_hours is not None:
        if today_metric.sleep_hours < 6:
            suggestions.append("睡眠不足，建议优先补觉，训练以低强度为主")
        elif today_metric.sleep_hours >= 7.5:
            suggestions.append("睡眠充足，身体状态良好，可正常执行训练")

    if not suggestions:
        suggestions.append("各项指标正常，按计划执行训练。继续保持！")
        adjustment = "normal"

    return {
        "date": str(today),
        "metrics": {
            "sleep_hours": today_metric.sleep_hours,
            "sleep_quality": today_metric.sleep_quality,
            "resting_hr": today_metric.resting_hr,
            "hrv": today_metric.hrv,
            "fatigue_score": today_metric.fatigue_score,
            "recovery_score": today_metric.recovery_score,
        },
        "adjustment": adjustment,
        "suggestions": suggestions,
    }
