"""
训练哲学注册表 — 护栏约束模式

每种哲学定义了不同的训练结构、强度配比和约束条件。
用户选择一种哲学后，12周内不应随意切换。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PhilosophyProfile:
    key: str
    name: str
    description: str
    intensity_ratio_high: float  # 高强度占比 (e.g. 0.20 for 80/20)
    intensity_ratio_low: float   # 低强度占比
    weekly_mileage_cap: float    # 周增幅上限
    high_max: int                # 每周高强度上限
    low_max: int                 # 每周低强度上限
    checkpoint_interval: int     # 检查点间隔 (weeks)
    blind_run_frequency: int     # 每N次训练标记1次盲跑


PHILOSOPHIES: dict[str, PhilosophyProfile] = {
    "polarised_80_20": PhilosophyProfile(
        key="polarised_80_20",
        name="80/20 极化训练",
        description="80%低强度轻松跑 + 20%高强度间歇/节奏。\"要么慢，要么快\"，避开灰色地带。"
                    "最广泛验证的耐力训练方法，由 Stephen Seiler 提出。",
        intensity_ratio_high=0.20,
        intensity_ratio_low=0.80,
        weekly_mileage_cap=0.10,
        high_max=2,
        low_max=5,
        checkpoint_interval=4,
        blind_run_frequency=8,
    ),
    "daniels_2q": PhilosophyProfile(
        key="daniels_2q",
        name="Daniels 2Q 训练法",
        description="每周2次质量课(Q1/Q2)，其余全为轻松跑。基于VDOT体系精确配速。"
                    "Jack Daniels 经典体系，适合对配速有精确要求的跑者。",
        intensity_ratio_high=0.22,
        intensity_ratio_low=0.78,
        weekly_mileage_cap=0.08,
        high_max=2,
        low_max=5,
        checkpoint_interval=4,
        blind_run_frequency=10,
    ),
}


def get_philosophy(key: str) -> Optional[PhilosophyProfile]:
    """获取哲学配置，未知key返回None"""
    return PHILOSOPHIES.get(key)


def list_philosophies() -> list[dict]:
    """列出所有可用哲学（返回简化dict供API使用）"""
    return [
        {
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "intensity_ratio": f"{int(p.intensity_ratio_high * 100)}/{int(p.intensity_ratio_low * 100)}",
            "weekly_mileage_cap": p.weekly_mileage_cap,
            "high_max": p.high_max,
            "checkpoint_interval": p.checkpoint_interval,
        }
        for p in PHILOSOPHIES.values()
    ]
