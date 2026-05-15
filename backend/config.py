import os, sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# DB path: next to EXE (PyInstaller) or in backend dir (dev)
if getattr(sys, "frozen", False):
    DB_DIR = os.path.dirname(sys.executable)
else:
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DB_DIR, exist_ok=True)
BASE_DIR = DB_DIR
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(DB_DIR, 'running.db')}")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # Gemini
COROS_MCP_URL = os.getenv("COROS_MCP_URL", "")

# COROS Open API OAuth
COROS_CLIENT_ID = os.getenv("COROS_CLIENT_ID", "")
COROS_CLIENT_SECRET = os.getenv("COROS_CLIENT_SECRET", "")
COROS_REDIRECT_URI = os.getenv("COROS_REDIRECT_URI", "http://localhost:8000/settings")
COROS_AUTH_URL = "https://openapi.coros.com/oauth2/authorize"
COROS_TOKEN_URL = "https://openapi.coros.com/oauth2/token"
COROS_API_BASE = "https://openapi.coros.com"

os.makedirs(UPLOAD_DIR, exist_ok=True)
