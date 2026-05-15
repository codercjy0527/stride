from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from services.pace_calculator import calculate_race_pace

router = APIRouter()


class RaceCalculateRequest(BaseModel):
    target_distance: str  # "5K", "10K", "half_marathon", "marathon"
    recent_5k_time: Optional[str] = None
    recent_10k_time: Optional[str] = None
    recent_half_time: Optional[str] = None


@router.post("/calculate")
def calculate(data: RaceCalculateRequest):
    return calculate_race_pace(
        target_distance=data.target_distance,
        recent_5k_time=data.recent_5k_time,
        recent_10k_time=data.recent_10k_time,
        recent_half_time=data.recent_half_time,
    )
