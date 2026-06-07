"""
config.py — centralised settings loaded from .env
All modules import from here; never hardcode keys elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def project_path(value: str) -> str:
    """Resolve relative project paths from the folder containing config.py."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str(PROJECT_DIR / path)


def env_bool(name: str, default: str = "false") -> bool:
    """Read a boolean environment variable."""
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


class Config:
    # ── API keys ─────────────────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")

    # ── LangSmith ────────────────────────────────────────
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "adas-safety-bot")

    # ── Vector DB paths ──────────────────────────────────
    CHROMA_VIDEO_DB_PATH: str = project_path(os.getenv("CHROMA_VIDEO_DB_PATH", "./vectordb/video_db"))
    CHROMA_STANDARDS_DB_PATH: str = project_path(os.getenv("CHROMA_STANDARDS_DB_PATH", "./vectordb/standards_db"))
    CHROMA_LOCAL_STANDARDS_DB_PATH: str = project_path(
        os.getenv("CHROMA_LOCAL_STANDARDS_DB_PATH", "./vectordb/local_standards_db")
    )

    # ── Collection names ─────────────────────────────────
    VIDEO_COLLECTION_NAME: str = os.getenv("VIDEO_COLLECTION_NAME", "adas_videos")
    STANDARDS_COLLECTION_NAME: str = os.getenv("STANDARDS_COLLECTION_NAME", "iso_standards")
    LOCAL_STANDARDS_COLLECTION_NAME: str = os.getenv(
        "LOCAL_STANDARDS_COLLECTION_NAME",
        "local_iso_standards",
    )

    # ── Chunking ─────────────────────────────────────────
    VIDEO_CHUNK_SIZE: int = int(os.getenv("VIDEO_CHUNK_SIZE", 400))
    VIDEO_CHUNK_OVERLAP: int = int(os.getenv("VIDEO_CHUNK_OVERLAP", 50))
    STANDARDS_CHUNK_SIZE: int = int(os.getenv("STANDARDS_CHUNK_SIZE", 300))
    STANDARDS_CHUNK_OVERLAP: int = int(os.getenv("STANDARDS_CHUNK_OVERLAP", 40))

    # ── Models ───────────────────────────────────────────
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "12000"))
    OPENAI_TIMEOUT: float = float(os.getenv("OPENAI_TIMEOUT", "300"))

    # ── Optional open-source draft model ─────────────────
    LOCAL_LLM_PROVIDER: str = os.getenv("LOCAL_LLM_PROVIDER", "ollama").lower()
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b-instruct")
    LOCAL_LLM_TIMEOUT: float = float(os.getenv("LOCAL_LLM_TIMEOUT", "300"))
    LOCAL_LLM_NUM_CTX: int = int(os.getenv("LOCAL_LLM_NUM_CTX", "16384"))
    LOCAL_LLM_NUM_PREDICT: int = int(os.getenv("LOCAL_LLM_NUM_PREDICT", "4000"))
    LOCAL_LORA_OLLAMA_MODEL: str = os.getenv("LOCAL_LORA_OLLAMA_MODEL", "qwen-safety-lora")
    LOCAL_LORA_API_URL: str = os.getenv("LOCAL_LORA_API_URL", "")
    LOCAL_LORA_TIMEOUT: float = float(os.getenv("LOCAL_LORA_TIMEOUT", "300"))
    LOCAL_EMBEDDING_MODEL: str = os.getenv(
        "LOCAL_EMBEDDING_MODEL",
        "BAAI/bge-small-en-v1.5",
    )

    # ── Text-to-speech output ────────────────────────────
    TTS_ENABLED: bool = env_bool("TTS_ENABLED")

    # ── Speech-to-text input ─────────────────────────────
    STT_MODEL: str = os.getenv("STT_MODEL", "base")
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "")

    # OpenAI TTS settings
    TTS_MODEL: str = os.getenv("TTS_MODEL", "tts-1")
    TTS_VOICE: str = os.getenv("TTS_VOICE", "alloy")

    TTS_OUTPUT_DIR: str = project_path(os.getenv("TTS_OUTPUT_DIR", "./outputs/tts"))
    TTS_AUTOPLAY: bool = env_bool("TTS_AUTOPLAY")
    TTS_MAX_CHARS: int = int(os.getenv("TTS_MAX_CHARS", "3500"))

    def validate(self) -> None:
        """Raise early if critical keys are missing."""
        if not self.OPENAI_API_KEY:
            raise EnvironmentError("OPENAI_API_KEY is not set. Check your .env file.")
        if not self.LANGCHAIN_API_KEY:
            print("[WARNING] LANGCHAIN_API_KEY not set — LangSmith tracing disabled.")


cfg = Config()
