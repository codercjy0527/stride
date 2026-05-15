"""
桌面启动器 —— 启动后端服务 + 打开浏览器
支持 PyInstaller 打包环境和开发模式，启动时运行自诊断
"""
import os
import sys
import time
import threading
import webbrowser


def get_base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def status(ok: bool, label: str, detail: str = "") -> str:
    """Format a status line."""
    icon = "  [OK]" if ok else "  [FAIL]"
    d = f"  ({detail})" if detail else ""
    return f"{icon} {label}{d}"


def run_diagnostics(base: str) -> list[str]:
    """Run startup diagnostics. Returns a list of status lines."""
    lines = []
    lines.append("=" * 50)
    lines.append("  Stride 启动自检")
    lines.append("=" * 50)

    # ── 1. Python / System ──
    lines.append(status(True, f"Python {sys.version_info.major}.{sys.version_info.minor}"))

    # ── 2. SSL certs ──
    try:
        import certifi
        import ssl
        ssl.create_default_context(cafile=certifi.where())
        lines.append(status(True, "SSL 证书 (certifi)"))
    except Exception as e:
        lines.append(status(False, "SSL 证书 (certifi)", str(e)[:60]))
        lines.append(status(False, "  HTTPS 请求可能失败，COROS 登录/同步不可用"))

    # ── 3. Database ──
    try:
        import sqlalchemy  # noqa: F401
        os.environ.setdefault("FRONTEND_DIR", os.path.join(base, "frontend", "dist"))
        os.environ.setdefault("RUNNING_DIR", base)
        os.environ.setdefault("ACTIVATION_MODE", "test")
        from database import init_db, engine
        init_db()
        import sqlite3
        db_path = str(engine.url).replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
        lines.append(status(True, f"数据库 ({db_path[-40:]})"))
    except Exception as e:
        lines.append(status(False, "数据库", str(e)[:60]))

    # ── 4. COROS API ──
    try:
        import coros_api  # noqa: F401
        lines.append(status(True, "COROS 原生 API"))
    except ImportError:
        lines.append(status(False, "COROS 原生 API", "模块未安装"))
        lines.append(status(False, "  可通过 Cookie 方式登录 COROS"))

    try:
        import auth.storage  # noqa: F401
    except ImportError:
        lines.append(status(False, "  auth.storage 缺失", "需检查 PyInstaller hidden imports"))

    # ── 5. COROS Web (Cookie) ──
    try:
        import httpx  # noqa: F401
        lines.append(status(True, "COROS Web 登录 (httpx)"))
    except ImportError:
        lines.append(status(False, "COROS Web 登录 (httpx)", "模块未安装"))

    # ── 6. AI Coach ──
    try:
        from services.ai_coach import _fallback_reply
        _fallback_reply("test")
        lines.append(status(True, "AI 教练模块"))
    except Exception as e:
        lines.append(status(False, "AI 教练模块", str(e)[:60]))

    # ── 7. Frontend ──
    if getattr(sys, "frozen", False):
        frontend_dir = os.path.join(base, "frontend", "dist")
    else:
        frontend_dir = os.path.join(os.path.dirname(base), "frontend", "dist")
    if os.path.isdir(frontend_dir) and os.path.isfile(os.path.join(frontend_dir, "index.html")):
        lines.append(status(True, "前端静态文件"))
    else:
        lines.append(status(False, "前端静态文件", frontend_dir[-40:]))

    # ── 8. Key dependencies ──
    for pkg, label in [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("passlib", "Passlib"),
    ]:
        try:
            __import__(pkg)
            lines.append(status(True, label))
        except ImportError:
            lines.append(status(False, label))

    # ── Summary ──
    failures = sum(1 for l in lines if "[FAIL]" in l)
    lines.append("-" * 50)
    if failures == 0:
        lines.append("  全部检查通过，启动服务中...")
    else:
        lines.append(f"  {failures} 项异常，服务可能部分功能不可用")
    lines.append("=" * 50)
    return lines


def open_browser(port: int):
    """Wait for server to be ready, then open browser."""
    import urllib.request

    url = f"http://127.0.0.1:{port}/api/health"
    for i in range(30):
        time.sleep(1)
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                break
        except Exception:
            pass
    else:
        print(f"\n  [!!] 服务启动超时，请手动打开浏览器访问 http://localhost:{port}\n")
        return

    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        print(f"\n  [!!] 无法自动打开浏览器，请手动访问 http://localhost:{port}\n")


def main():
    base = get_base_dir()
    if base not in sys.path:
        sys.path.insert(0, base)

    port = int(os.environ.get("PORT", 8000))

    # ── Run diagnostics ──
    for line in run_diagnostics(base):
        print(line)
    print()

    # Open browser in background
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    import main
    import uvicorn

    uvicorn.run(
        main.app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
