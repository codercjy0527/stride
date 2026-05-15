from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from db.user import User
from routers.auth import get_current_user
from services.pose_analyzer import analyze_running_form

router = APIRouter()

# In-memory storage for analysis results (production would use DB)
_analyses = {}


@router.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import os
    from config import UPLOAD_DIR

    video_path = os.path.join(UPLOAD_DIR, f"video_{user.id}_{video.filename}")
    with open(video_path, "wb") as f:
        f.write(await video.read())

    result = await analyze_running_form(video_path)

    # Store in memory
    key = f"{user.id}_{len(_analyses)}"
    _analyses[key] = {"user_id": user.id, "filename": video.filename, "result": result}

    return result


@router.get("/analyses")
def list_analyses(user: User = Depends(get_current_user)):
    return [
        v for k, v in _analyses.items() if v["user_id"] == user.id
    ]
