"""Local speech-to-text with faster-whisper. Audio never leaves this machine."""

from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def _model():
    # Imported lazily so the rest of the app (and the tests) work without it.
    from faster_whisper import WhisperModel

    return WhisperModel(settings.whisper_model, device="auto", compute_type="int8")


def transcribe(audio_path: str) -> tuple[str, float]:
    """Return (transcript, audio_duration_seconds)."""
    segments, info = _model().transcribe(
        audio_path, language=settings.whisper_language, vad_filter=True
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip(), info.duration
