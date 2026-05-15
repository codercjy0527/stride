from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from db.user import User
from routers.auth import get_current_user
from services.ai_coach import ai_coach_chat, analyze_screenshot

router = APIRouter()


@router.post("/chat")
async def chat(
    message: str = Form(""),
    image: Optional[UploadFile] = File(None),
    provider: str = Form("deepseek"),
    model: str = Form(""),
    api_key: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if image:
        import os
        from config import UPLOAD_DIR
        img_path = os.path.join(UPLOAD_DIR, f"chat_{user.id}_{image.filename}")
        with open(img_path, "wb") as f:
            f.write(await image.read())
        reply = await analyze_screenshot(img_path, message, user, db, provider, api_key, model)
    else:
        reply = await ai_coach_chat(message, user, db, provider, api_key, model)

    return {"reply": reply}
