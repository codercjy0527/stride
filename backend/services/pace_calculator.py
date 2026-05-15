"""
赛事配速推算

使用 Riegel 公式：T2 = T1 × (D2/D1)^1.06
结合 VDOT 跑力值表进行校验
"""

import math

DISTANCE_MAP = {
    "5K": 5.0,
    "10K": 10.0,
    "half_marathon": 21.0975,
    "marathon": 42.195,
}

DISTANCE_LABEL = {
    "5K": "5公里",
    "10K": "10公里",
    "half_marathon": "半马 (21.1K)",
    "marathon": "全马 (42.2K)",
}

# VDOT table: vdot -> { distance_km: time_seconds }
# Simplified for common distances
VDOT_TABLE = {
    30: {"5K": 1680, "10K": 3490, "half_marathon": 7740, "marathon": 16140},
    35: {"5K": 1500, "10K": 3120, "half_marathon": 6900, "marathon": 14400},
    40: {"5K": 1360, "10K": 2820, "half_marathon": 6240, "marathon": 13020},
    45: {"5K": 1240, "10K": 2570, "half_marathon": 5700, "marathon": 11880},
    50: {"5K": 1140, "10K": 2360, "half_marathon": 5220, "marathon": 10920},
    55: {"5K": 1050, "10K": 2180, "half_marathon": 4820, "marathon": 10080},
    60: {"5K": 970, "10K": 2020, "half_marathon": 4470, "marathon": 9360},
    65: {"5K": 900, "10K": 1870, "half_marathon": 4140, "marathon": 8700},
    70: {"5K": 840, "10K": 1750, "half_marathon": 3870, "marathon": 8100},
    75: {"5K": 790, "10K": 1640, "half_marathon": 3630, "marathon": 7620},
    80: {"5K": 740, "10K": 1540, "half_marathon": 3400, "marathon": 7140},
}


def _parse_time(time_str: str) -> int:
    """Parse time string like '25:30' or '1:55:00' to seconds."""
    parts = time_str.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0])


def _format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _find_vdot(distance_km: float, time_sec: int) -> int:
    """Estimate VDOT from a race result."""
    for vdot in sorted(VDOT_TABLE.keys(), reverse=True):
        ref = VDOT_TABLE[vdot]
        # Find closest distance
        closest_dist = min(ref.keys(), key=lambda k: abs(DISTANCE_MAP.get(k, 5) - distance_km))
        expected = ref[closest_dist]
        if time_sec <= expected:
            return vdot
    return 30


def calculate_race_pace(
    target_distance: str,
    recent_5k_time: str | None = None,
    recent_10k_time: str | None = None,
    recent_half_time: str | None = None,
) -> dict:
    """
    Calculate predicted race time and pacing strategy.
    Uses Riegel formula: T2 = T1 * (D2 / D1) ** 1.06
    """
    target_km = DISTANCE_MAP.get(target_distance, 21.1)

    # Determine reference performance
    ref_time = None
    ref_dist = None

    if recent_half_time:
        ref_time = _parse_time(recent_half_time)
        ref_dist = DISTANCE_MAP["half_marathon"]
    elif recent_10k_time:
        ref_time = _parse_time(recent_10k_time)
        ref_dist = DISTANCE_MAP["10K"]
    elif recent_5k_time:
        ref_time = _parse_time(recent_5k_time)
        ref_dist = DISTANCE_MAP["5K"]
    else:
        # Default: 25 min 5K
        ref_time = 1500
        ref_dist = 5.0

    # Riegel formula
    predicted_seconds = ref_time * math.pow(target_km / ref_dist, 1.06)
    pace_per_km = predicted_seconds / target_km

    # VDOT cross-check
    vdot = _find_vdot(ref_dist, ref_time)
    vdot_check = None
    if target_distance in VDOT_TABLE.get(vdot, {}):
        vdot_check = _format_time(VDOT_TABLE[vdot][target_distance])

    # Generate splits
    split_count = int(target_km) if target_km <= 42.2 else 42
    splits = []
    for km in range(1, split_count + 1):
        splits.append({
            "km": km,
            "time": _format_time(km * pace_per_km),
        })

    # Race strategy recommendations
    strategy = []
    if target_distance == "marathon":
        strategy = [
            "前半程：以目标配速 +5-10s/km 保守出发，心率控制在 Zone 2-3",
            "25-35K：保持目标配速，注意补给（每 5K 补水，每 10K 能量胶）",
            "最后 7K：根据体能决定是否提速",
        ]
    elif target_distance == "half_marathon":
        strategy = [
            "前 5K：比目标配速慢 3-5s，充分热身",
            "5-16K：稳定在目标配速",
            "最后 5K：根据体感冲刺",
        ]
    elif target_distance in ("5K", "10K"):
        strategy = [
            "第 1K：控制节奏，别被带快",
            "中段：保持匀速，心率 Zone 4",
            "最后 1-2K：全力冲刺",
        ]

    return {
        "target_distance": target_distance,
        "predicted_time": _format_time(predicted_seconds),
        "pace_per_km": _format_time(pace_per_km),
        "vdot_estimate": vdot,
        "vdot_predicted_time": vdot_check,
        "splits": splits,
        "strategy": strategy,
    }
