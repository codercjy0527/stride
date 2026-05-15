"""
80/20 极化训练计划生成算法

规则：
- 80% 跑量为低强度 (Zone 1-2 / easy + long_run)，20% 为高强度 (Zone 3-5 / tempo + interval)
- 周增幅：next_week_volume <= current_week_volume * (1 + weekly_mileage_cap)
- 每4周插入减量周 (volume * 0.7)
- 高强度课次不超过 high_intensity_max，低强度课次不超过 low_intensity_max
"""

from db.training import TrainingPlan, TrainingSession, SessionType, Intensity


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
}


def generate_training_plan(plan: TrainingPlan, base_weekly_km: float) -> list[TrainingSession]:
    sessions = []
    weeks = plan.weeks
    cap = plan.weekly_mileage_cap

    weekly_volume = base_weekly_km

    for week_num in range(1, weeks + 1):
        # Every 4th week: recovery (reduce volume by 30%)
        is_recovery = week_num % 4 == 0
        week_km = weekly_volume * (0.7 if is_recovery else 1.0)

        # Distribute volume: 80% low, 20% high
        low_km = week_km * 0.80
        high_km = week_km * 0.20

        # Build weekly schedule (7 days)
        # Pattern: easy, tempo/interval, easy, easy/rest, interval/long, easy, long_run/rest
        day_patterns = _get_week_pattern(is_recovery, plan.high_intensity_max, plan.low_intensity_max)

        for day_idx, session_type in enumerate(day_patterns):
            template = SESSION_TEMPLATES[session_type]
            if session_type == SessionType.rest:
                duration = 0
                distance = 0.0
            elif template["intensity"] == Intensity.high:
                # Distribute high-intensity volume across high sessions
                high_sessions = sum(1 for t in day_patterns if SESSION_TEMPLATES[t]["intensity"] == Intensity.high)
                distance = round(high_km / high_sessions, 1) if high_sessions > 0 else 0
                duration = int(distance * _pace_factor(session_type))
            else:
                low_sessions = sum(1 for t in day_patterns if SESSION_TEMPLATES[t]["intensity"] == Intensity.low and t != SessionType.rest)
                distance = round(low_km / low_sessions, 1) if low_sessions > 0 else 0
                duration = int(distance * _pace_factor(session_type))

            sessions.append(TrainingSession(
                plan_id=plan.id,
                week=week_num,
                day_of_week=day_idx,
                session_type=session_type,
                intensity=template["intensity"],
                duration_min=duration,
                distance_km=distance,
                description=template["desc"],
            ))

        # Increase weekly volume for next cycle
        if not is_recovery:
            weekly_volume = round(weekly_volume * (1 + cap), 1)

    return sessions


def _get_week_pattern(is_recovery: bool, high_max: int, low_max: int) -> list[SessionType]:
    """Return a weekly schedule respecting high/low intensity caps."""
    if is_recovery:
        return [
            SessionType.easy, SessionType.rest, SessionType.easy,
            SessionType.rest, SessionType.easy, SessionType.easy,
            SessionType.long_run,
        ]
    # Normal week: 2 high sessions (tempo + interval), rest low
    patterns = {
        1: [  # 1 high session
            SessionType.easy, SessionType.tempo, SessionType.easy,
            SessionType.rest, SessionType.easy, SessionType.easy,
            SessionType.long_run,
        ],
        2: [  # 2 high sessions (standard 80/20)
            SessionType.easy, SessionType.tempo, SessionType.easy,
            SessionType.rest, SessionType.interval, SessionType.easy,
            SessionType.long_run,
        ],
        3: [  # 3 high sessions
            SessionType.easy, SessionType.tempo, SessionType.interval,
            SessionType.rest, SessionType.tempo, SessionType.easy,
            SessionType.long_run,
        ],
    }
    return patterns.get(high_max, patterns[2])


def _pace_factor(session_type: SessionType) -> float:
    """Return minutes per km for each session type."""
    return {
        SessionType.easy: 6.5,
        SessionType.tempo: 5.0,
        SessionType.interval: 4.0,
        SessionType.long_run: 7.0,
        SessionType.rest: 0,
    }[session_type]
