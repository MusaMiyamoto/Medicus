"""Settings, read from environment variables so nothing is hard-coded per machine."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("MEDICUS_HOST", "127.0.0.1")
    port: int = int(os.getenv("MEDICUS_PORT", "8000"))
    whisper_model: str = os.getenv("MEDICUS_WHISPER_MODEL", "medium")
    whisper_language: str = os.getenv("MEDICUS_WHISPER_LANGUAGE", "no")
    ollama_url: str = os.getenv("MEDICUS_OLLAMA_URL", "http://127.0.0.1:11434")
    llm_model: str = os.getenv("MEDICUS_LLM_MODEL", "gemma3:4b")
    audit_log: Path = Path(os.getenv("MEDICUS_AUDIT_LOG", "data/audit.jsonl"))


settings = Settings()
