import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "meetings.db"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

FALLBACK_MODELS = []
