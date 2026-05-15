"""
本地激活码验证
生成机器ID → 检查本地license → 验证激活服务器
"""
import os
import json
import uuid
import hashlib
import platform
import time
from datetime import datetime

LICENSE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "license.dat")
ACTIVATION_SERVER = os.environ.get("ACTIVATION_SERVER", "http://192.168.5.10:9000")
LICENSE_TTL_DAYS = 365  # 离线激活有效天数


def get_machine_id() -> str:
    """生成机器唯一ID（基于 MAC + 主机名）"""
    import socket
    raw = str(uuid.getnode()) + socket.gethostname() + platform.node()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_license() -> dict | None:
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)
        # Verify machine binding
        if data.get("machine_id") != get_machine_id():
            return None
        return data
    except Exception:
        return None


def save_license(data: dict):
    data["machine_id"] = get_machine_id()
    data["saved_at"] = datetime.now().isoformat()
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_activated() -> dict:
    """检查激活状态"""
    # Test mode: always activated
    if os.environ.get("ACTIVATION_MODE") == "test":
        return {"activated": True, "code": "TEST-****-****-****"}

    lic = load_license()
    if not lic:
        return {"activated": False, "reason": "未激活"}

    # Check offline expiry
    saved = lic.get("saved_at")
    if saved:
        saved_dt = datetime.fromisoformat(saved)
        if (datetime.now() - saved_dt).days > LICENSE_TTL_DAYS:
            return {"activated": False, "reason": "激活已过期，请重新联网验证"}

    return {"activated": True, "code": lic.get("code", "")[:8] + "***"}


async def activate(code: str) -> dict:
    """联网验证激活码（测试模式下跳过联网）"""
    if os.environ.get("ACTIVATION_MODE") == "test":
        save_license({"code": code.strip().upper()})
        return {"ok": True, "message": "测试模式激活成功"}

    mid = get_machine_id()

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{ACTIVATION_SERVER}/validate",
                json={"code": code.strip().upper(), "machine_id": mid},
            )
            if resp.status_code == 200:
                data = resp.json()
                save_license({"code": code.strip().upper()})
                return {"ok": True, "message": data.get("message", "激活成功")}
            elif resp.status_code >= 400:
                try:
                    detail = resp.json().get("detail", "激活失败")
                except Exception:
                    detail = f"服务器错误 (HTTP {resp.status_code})"
                return {"ok": False, "message": detail}
            return {"ok": False, "message": f"未知错误 (HTTP {resp.status_code})"}
    except Exception as e:
        return {"ok": False, "message": f"无法连接激活服务器: {str(e)[:100]}"}


def _simple_encrypt(text: str) -> str:
    """简单加密（本地存储用，非高强度）"""
    import base64
    key = get_machine_id().encode()[:16]
    result = bytes(c ^ key[i % len(key)] for i, c in enumerate(text.encode()))
    return base64.b64encode(result).decode()


def _simple_decrypt(enc: str) -> str:
    """简单解密"""
    import base64
    key = get_machine_id().encode()[:16]
    data = base64.b64decode(enc)
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(data)).decode()


def deactivate():
    """清除本地激活"""
    if os.path.exists(LICENSE_FILE):
        os.remove(LICENSE_FILE)
        return True
    return False
