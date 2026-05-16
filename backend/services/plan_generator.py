"""
训练计划生成算法 — 护栏约束模式

核心原则:
- 基于单一训练哲学生成，不混合体系
- 80%低强度 + 20%高强度 (或哲学自定义比例)
- 周增幅受护栏约束: next_week <= current * (1 + cap)
- 每4周插入检查点训练（替换一次高强度课）
- 每N次训练随机标记盲跑（不看手表凭体感）
"""

from db.training import TrainingPlan, TrainingSession, SessionType, Intensity
from services.philosophies import get_philosophy, PHILOSOPHIES


# 检查点训练模板
CHECKPOINT_TEMPLATES = {
    "5k_time_trial": {
        "duration_range": (20, 35),
        "distance_factor": (5, 5),
        "desc": "🔬 检查点: 5K计时测试 — 全力跑5公里，记录成绩，用于评估体能进展",
    },
    "threshold_test": {
        "duration_range": (25, 40),
        "distance_factor": (6, 8),
        "desc": "🔬 检查点: 阈值配速测试 — 30分钟阈值强度跑，记录平均配速和心率",
    },
}

# 完整训练模板库
SESSION_TEMPLATES = {
    SessionType.easy: {
        "duration_range": (30, 60),
        "distance_factor": (5, 10),
        "intensity": Intensity.low,
        "desc": "轻松跑 - 心率Zone 1-2，轻松对话配速",
    },
    SessionType.long_run: {
        "duration_range": (60, 120),
        "distance_factor": (12, 25),
        "intensity": Intensity.low,
        "desc": "长距离慢跑 - 心率Zone 1-2，建立有氧耐力",
    },
    SessionType.tempo: {
        "duration_range": (30, 50),
        "distance_factor": (6, 12),
        "intensity": Intensity.high,
        "desc": "节奏跑 - 心率Zone 3-4，乳酸阈值训练",
    },
    SessionType.interval: {
        "duration_range": (25, 45),
        "distance_factor": (4, 8),
        "intensity": Intensity.high,
        "desc": "间歇跑 - 心率Zone 4-5，最大摄氧量提升",
    },
    SessionType.rest: {
        "duration_range": (0, 0),
        "distance_factor": (0, 0),
        "intensity": Intensity.low,
        "desc": "休息日",
    },
    SessionType.fartlek: {
        "duration_range": (35, 55),
        "distance_factor": (7, 12),
        "intensity": Intensity.high,
        "desc": "法特莱克跑 - 自由变速，感受不同强度区间的切换",
    },
    SessionType.hills: {
        "duration_range": (30, 45),
        "distance_factor": (5, 9),
        "intensity": Intensity.high,
        "desc": "坡道训练 - 上坡发力/下坡恢复，提升腿部力量和跑姿经济性",
    },
}


def generate_training_plan(plan: TrainingPlan, base_weekly_km: float) -> list[TrainingSession]:
    """
    基于护栏约束模式生成训练计划。

    Args:
        plan: TrainingPlan ORM对象 (含philosophy, fitness_level等)
        base_weekly_km: 基础周跑量 (km)
    """
    profile = get_philosophy(plan.philosophy or "polarised_80_20")
    if profile is None:
        profile = PHILOSOPHIES["polarised_80_20"]

    sessions = []
    weeks = plan.weeks
    cap = plan.weekly_mileage_cap or profile.weekly_mileage_cap
    high_max = plan.high_intensity_max or profile.high_max
    low_max = plan.low_intensity_max or profile.low_max
    weekly_volume = base_weekly_km

    blind_run_counter = 0

    for week_num in range(1, weeks + 1):
        is_recovery = week_num % profile.checkpoint_interval == 0
        week_km = weekly_volume * (0.7 if is_recovery else 1.0)
        is_checkpoint_week = is_recovery and week_num >= profile.checkpoint_interval

        low_km = week_km * profile.intensity_ratio_low
        high_km = week_km * profile.intensity_ratio_high

        day_pattern = _get_week_pattern(
            is_recovery=is_recovery,
            is_checkpoint_week=is_checkpoint_week,
            high_max=high_max,
            low_max=low_max,
            philosophy=profile.key,
        )

        for day_idx, session_type in enumerate(day_pattern):
            template = _get_template(session_type, is_checkpoint_week)
            if session_type == SessionType.rest:
                duration = 0
                distance = 0.0
            elif template["intensity"] == Intensity.high or session_type == SessionType.checkpoint:
                high_sessions = sum(
                    1 for t in day_pattern
                    if _get_template(t, is_checkpoint_week)["intensity"] == Intensity.high
                    or t == SessionType.checkpoint
                )
                distance = round(high_km / high_sessions, 1) if high_sessions > 0 else 0
                duration = int(distance * _pace_factor(session_type))
            else:
                low_sessions = sum(
                    1 for t in day_pattern
                    if _get_template(t, is_checkpoint_week)["intensity"] == Intensity.low
                    and t != SessionType.rest
                )
                distance = round(low_km / low_sessions, 1) if low_sessions > 0 else 0
                duration = int(distance * _pace_factor(session_type))

            is_blind = False
            if session_type not in (SessionType.rest, SessionType.checkpoint):
                blind_run_counter += 1
                if blind_run_counter % profile.blind_run_frequency == 0:
                    is_blind = True

            desc = template["desc"]
            if is_checkpoint_week and session_type == SessionType.checkpoint:
                checkpoint_type = "5k_time_trial" if week_num <= 8 else "threshold_test"
                ct = CHECKPOINT_TEMPLATES[checkpoint_type]
                desc = ct["desc"]
                distance = ct["distance_factor"][0]
                duration = int(distance * _pace_factor(SessionType.interval))
            if is_blind:
                desc += " 🔇盲跑 - 不看手表，凭体感控制强度"

            sessions.append(TrainingSession(
                plan_id=plan.id,
                week=week_num,
                day_of_week=day_idx,
                session_type=SessionType.checkpoint if (is_checkpoint_week and session_type == SessionType.checkpoint) else session_type,
                intensity=template["intensity"],
                duration_min=duration,
                distance_km=distance,
                description=desc,
                is_checkpoint=is_checkpoint_week and session_type == SessionType.checkpoint,
                is_blind_run=is_blind,
            ))

        if not is_recovery:
            weekly_volume = round(weekly_volume * (1 + cap), 1)

    return sessions


def _get_template(session_type: SessionType, is_checkpoint_week: bool) -> dict:
    """获取训练模板，检查点周替换"""
    if is_checkpoint_week and session_type == SessionType.checkpoint:
        return {"intensity": Intensity.high, "distance_factor": (5, 5), "duration_range": (20, 35), "desc": ""}
    return SESSION_TEMPLATES.get(session_type, SESSION_TEMPLATES[SessionType.easy])


def _get_week_pattern(
    is_recovery: bool,
    is_checkpoint_week: bool,
    high_max: int,
    low_max: int,
    philosophy: str,
) -> list[SessionType]:
    """返回周训练安排，支持检查点注入"""

    # 检查点周：替换一次高强度课为检查点测试
    if is_checkpoint_week:
        # Daniels 2Q 用阈值测试，80/20 用 5K 计时
        patterns = {
            1: [
                SessionType.easy, SessionType.easy, SessionType.easy,
                SessionType.rest, SessionType.checkpoint, SessionType.easy,
                SessionType.long_run,
            ],
            2: [
                SessionType.easy, SessionType.tempo, SessionType.easy,
                SessionType.rest, SessionType.checkpoint, SessionType.easy,
                SessionType.long_run,
            ],
            3: [
                SessionType.easy, SessionType.tempo, SessionType.interval,
                SessionType.rest, SessionType.checkpoint, SessionType.easy,
                SessionType.long_run,
            ],
        }
        return patterns.get(high_max, patterns[2])

    # 纯减量周（无检查点）
    if is_recovery:
        return [
            SessionType.easy, SessionType.rest, SessionType.easy,
            SessionType.rest, SessionType.easy, SessionType.easy,
            SessionType.long_run,
        ]

    # Daniels 2Q 法：Q1(间歇/节奏) + Q2(法特莱克/坡道) + 其余轻松
    if philosophy == "daniels_2q":
        return [
            SessionType.easy, SessionType.interval, SessionType.easy,
            SessionType.rest, SessionType.fartlek, SessionType.easy,
            SessionType.long_run,
        ]

    # 默认 80/20 极化
    patterns = {
        1: [
            SessionType.easy, SessionType.tempo, SessionType.easy,
            SessionType.rest, SessionType.easy, SessionType.easy,
            SessionType.long_run,
        ],
        2: [
            SessionType.easy, SessionType.tempo, SessionType.easy,
            SessionType.rest, SessionType.interval, SessionType.easy,
            SessionType.long_run,
        ],
        3: [
            SessionType.easy, SessionType.tempo, SessionType.interval,
            SessionType.rest, SessionType.tempo, SessionType.easy,
            SessionType.long_run,
        ],
    }
    return patterns.get(high_max, patterns[2])


def _pace_factor(session_type: SessionType) -> float:
    """返回每种训练类型的配速系数 (min/km)"""
    return {
        SessionType.easy: 6.5,
        SessionType.tempo: 5.0,
        SessionType.interval: 4.0,
        SessionType.long_run: 7.0,
        SessionType.rest: 0,
        SessionType.checkpoint: 4.0,
        SessionType.fartlek: 5.2,
        SessionType.hills: 5.8,
    }.get(session_type, 6.5)
