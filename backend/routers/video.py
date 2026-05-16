from fastapi import APIRouter, Depends, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from db.user import User
from routers.auth import get_current_user
from services.pose_analyzer import analyze_running_form

router = APIRouter()

_analyses: dict[str, dict] = {}


@router.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    view_angle: str = Form(default="side", description="拍摄角度: side/rear/front"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import os
    from config import UPLOAD_DIR

    video_path = os.path.join(UPLOAD_DIR, f"video_{user.id}_{video.filename}")
    with open(video_path, "wb") as f:
        f.write(await video.read())

    result = await analyze_running_form(video_path, view_angle)

    key = f"{user.id}_{len(_analyses)}"
    _analyses[key] = {"user_id": user.id, "filename": video.filename, "result": result}

    return result


@router.post("/analyze/barefoot")
async def analyze_barefoot(
    video: UploadFile = File(...),
    shod_video_key: str = Form(default="", description="穿鞋分析的 key"),
    view_angle: str = Form(default="side"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """赤足跑姿分析 + 与穿鞋结果对比"""
    import os
    from config import UPLOAD_DIR

    video_path = os.path.join(UPLOAD_DIR, f"video_barefoot_{user.id}_{video.filename}")
    with open(video_path, "wb") as f:
        f.write(await video.read())

    result = await analyze_running_form(video_path, view_angle)

    # 查找穿鞋分析结果做对比
    comparison = None
    if shod_video_key and shod_video_key in _analyses:
        shod = _analyses[shod_video_key]["result"]
        comparison = _build_comparison(shod, result)

    key = f"{user.id}_{len(_analyses)}"
    _analyses[key] = {"user_id": user.id, "filename": f"barefoot_{video.filename}", "result": result}

    return {"result": result, "comparison": comparison}


@router.get("/analyses")
def list_analyses(user: User = Depends(get_current_user)):
    return [
        {"key": k, **{kk: vv for kk, vv in v.items() if kk != "result"},
         "score": v["result"].get("score"), "cadence": v["result"].get("cadence")}
        for k, v in _analyses.items() if v["user_id"] == user.id
    ]


def _build_comparison(shod: dict, barefoot: dict) -> dict:
    """对比穿鞋 vs 赤足的跑姿差异。"""
    diffs = []
    metrics = [
        ("cadence", "步频", "spm"),
        ("ground_contact_time", "触地时间", "ms"),
        ("vertical_oscillation", "垂直振幅", "cm"),
    ]
    for key, label, unit in metrics:
        sv = shod.get(key)
        bv = barefoot.get(key)
        if sv and bv and isinstance(sv, (int, float)) and isinstance(bv, (int, float)):
            delta = bv - sv
            diffs.append({"metric": label, "shod": sv, "barefoot": bv, "delta": delta, "unit": unit})

    # 赤足时触地时间通常更短、步频更高 — 这说明鞋子的缓冲可能改变了自然跑姿
    insights = []
    gct = next((d for d in diffs if d["metric"] == "触地时间"), None)
    cad = next((d for d in diffs if d["metric"] == "步频"), None)

    if gct and gct["delta"] < -10:
        insights.append("赤足时触地时间显著缩短，说明鞋子缓冲可能让你无意识延长了触地。建议选择薄底/低落差的跑鞋。")
    if cad and cad["delta"] > 5:
        insights.append("赤足时步频自然提高，这是身体本能的保护机制。训练时可参考这个步频作为目标。")

    return {"differences": diffs, "insights": insights}
