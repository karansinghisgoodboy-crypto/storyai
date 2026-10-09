"""Central configuration for StoryAI."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    BASE_DIR = BASE_DIR

    # Storage
    DATABASE_PATH = Path(os.getenv("DATABASE_PATH") or BASE_DIR / "db" / "storyai.db")
    SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or BASE_DIR / "uploads")
    LOG_PATH = BASE_DIR / "storyai.log"

    # AI providers; local Ollama is the default, OpenAI is optional.
    AI_PROVIDER = (os.getenv("AI_PROVIDER", "ollama").strip().lower() or "ollama")
    OLLAMA_BASE_URL = (
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        or "http://127.0.0.1:11434"
    )
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

    # Server
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # hard cap on any request body (8 MB)
