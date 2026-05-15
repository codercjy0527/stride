import os, sys, traceback, logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("stride")

from database import init_db
from routers import auth, training, checkin, ai, video, race, coros, activities, activation

app = FastAPI(title="Stride", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_errors(request: Request, call_next):
    """Log full tracebacks for 500 errors."""
    try:
        return await call_next(request)
    except Exception:
        tb = traceback.format_exc()
        logger.error(f"500 on {request.method} {request.url.path}:\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Server error: {traceback.format_exc(limit=1).splitlines()[-1]}"},
        )


# Auth endpoints removed — app uses a single default user
app.include_router(training.router, prefix="/api", tags=["training"])
app.include_router(checkin.router, prefix="/api", tags=["checkin"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(video.router, prefix="/api/video", tags=["video"])
app.include_router(race.router, prefix="/api/race", tags=["race"])
app.include_router(coros.router, prefix="/api/coros", tags=["coros"])
app.include_router(activities.router, prefix="/api", tags=["activities"])
app.include_router(activation.router, prefix="/api", tags=["activation"])

# Frontend path: env var (PyInstaller) → relative (dev)
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"),
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static files
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
