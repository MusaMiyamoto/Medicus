"""Local speech-to-text with faster-whisper. Audio never leaves this machine."""

import sys
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def _model():
    # Imported lazily so the rest of the app (and the tests) work without it.
    from faster_whisper import WhisperModel

    return WhisperModel(settings.whisper_model, device="auto", compute_type=settings.whisper_compute)


def warmup() -> None:
    """Load the model now, so the first patient of the day doesn't wait for it. Never raises: if it
    fails, the model is loaded (and the error shown) at the first recording instead."""
    try:
        _model()
    except Exception as e:  # noqa: BLE001
        print(f"Whisper ble ikke lastet ved start ({type(e).__name__}); prøver igjen ved første opptak.",
              file=sys.stderr)


def transcribe(audio_path: str) -> tuple[str, float]:
    """Return (transcript, audio_duration_seconds)."""
    segments, info = _model().transcribe(
        audio_path, language=settings.whisper_language, vad_filter=True
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip(), info.duration
