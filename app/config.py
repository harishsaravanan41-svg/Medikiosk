import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory (app/config.py -> project root)
BASE_DIR = Path(__file__).resolve().parent.parent
# Application package directory
APP_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "medikiosk-secure-default-key")
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))

    # Qwen LLM Config
    # Modes: "custom_api" (X-API-Key + /v1/chat/completions or /v1/chat), "local_endpoint" (OpenAI-compat)
    QWEN_MODE = os.getenv("QWEN_MODE", "custom_api")
    QWEN_API_URL = os.getenv("QWEN_API_URL")
    QWEN_API_BASE = QWEN_API_URL or os.getenv("QWEN_API_BASE", "http://localhost:8000/v1/chat/completions")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-compliance")

    # STT Config (Whisper)
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

    # TTS Config (Piper / Fallback)
    TTS_ENGINE = os.getenv("TTS_ENGINE", "auto")
    PIPER_VOICE_MODEL = os.getenv("PIPER_VOICE_MODEL", "en_US-lessac-medium")
    PIPER_EXE_PATH = os.getenv("PIPER_EXE_PATH", "piper")

    # Storage Paths
    DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
    SESSIONS_DIR = DATA_DIR / "sessions"
    AUDIO_CACHE_DIR = APP_DIR / os.getenv("AUDIO_CACHE_DIR", "static/audio")

    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
