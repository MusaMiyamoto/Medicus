"""Settings, read from environment variables so nothing is hard-coded per machine."""

import os
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    whisper_model: str = "medium"
    whisper_language: str = "no"
    whisper_compute: str = "int8"     # "float16" on a PC with a GPU
    warmup: bool = True               # load Whisper when the service starts, not during the first consultation
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma3:4b"
    llm_temperature: float = 0.2
    llm_timeout: int = 300            # seconds; a long note on a PC without a GPU can take minutes
    llm_max_chars: int = 60_000       # longest transcript sent to the model (about an hour's talk)
    note_max_chars: int = 8_000       # longest section kept from the model's reply
    upload_max_mb: int = 100          # largest recording that can be uploaded
    audit_log: Path = Path("data/audit.jsonl")
    demo: bool = False                # the public web demo (medicus/demo.py); never on in Medicus OS

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        """Defaults, overridden by MEDICUS_<NAME> environment variables (MEDICUS_LLM_TIMEOUT=600)."""
        values = {}
        for field in fields(cls):
            raw = env.get(f"MEDICUS_{field.name.upper()}")
            if raw is None:
                continue
            kind = type(field.default)
            if kind is bool:
                values[field.name] = raw.strip().lower() in ("1", "true", "yes", "ja")
            elif issubclass(kind, Path):
                values[field.name] = Path(raw)
            else:
                values[field.name] = kind(raw)
        return cls(**values)


settings = Settings.from_env()
