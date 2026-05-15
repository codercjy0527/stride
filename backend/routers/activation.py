"""激活码验证 API"""
from fastapi import APIRouter, Query
from services.license import is_activated, activate, deactivate

router = APIRouter()


@router.get("/license/status")
def license_status():
    """获取激活状态（公开）"""
    return is_activated()


@router.post("/license/activate")
async def license_activate(code: str = Query(...)):
    """激活码验证"""
    return await activate(code)


@router.post("/license/deactivate")
def license_deactivate():
    """解除激活"""
    ok = deactivate()
    return {"ok": ok, "message": "已解除激活" if ok else "未找到激活信息"}
