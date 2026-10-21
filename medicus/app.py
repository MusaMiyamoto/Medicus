"""Web API and UI. Endpoints are plain `def` so slow CPU work runs in FastAPI's thread pool."""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import notes
from .audit import AuditLog
from .config import settings

STATIC = Path(__file__).parent / "static"
SAMPLE = Path(__file__).parent.parent / "samples" / "konsultasjon_eksempel.txt"

# Placeholder until clinicians log in with HelseID.
DEMO_USER = "demo-bruker"

app = FastAPI(title="Medicus", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
audit = AuditLog(settings.audit_log)


class TranscriptIn(BaseModel):
    transcript: str


class ApprovalIn(BaseModel):
    note: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/sample")
def sample():
    return {"transcript": SAMPLE.read_text(encoding="utf-8")}


@app.post("/api/transcribe")
def transcribe_audio(audio: UploadFile):
    from .transcribe import transcribe

    suffix = Path(audio.filename or "").suffix or ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        text, seconds = transcribe(path)
    except Exception as e:
        audit.record(DEMO_USER, "transcribe_failed", {"error": type(e).__name__})
        raise HTTPException(500, "Kunne ikke transkribere lydfilen.") from e
    finally:
        # The recording is deleted as soon as it has been transcribed.
        os.remove(path)
    audit.record(DEMO_USER, "transcribe", {"audio_seconds": round(seconds), "chars": len(text)})
    return {"transcript": text}


@app.post("/api/note")
def create_note(body: TranscriptIn):
    try:
        note = notes.generate_note(body.transcript)
    except notes.NoteError as e:
        audit.record(DEMO_USER, "note_failed", {"error": str(e)})
        raise HTTPException(502, str(e)) from e
    audit.record(DEMO_USER, "note_generated", {"model": settings.llm_model, "chars": len(body.transcript)})
    return {
        "sections": [{"key": k, "label": label, "text": note[k]} for k, label in notes.SECTIONS],
        "text": notes.format_note(note),
    }


@app.post("/api/approve")
def approve(body: ApprovalIn):
    audit.record(DEMO_USER, "note_approved", {"chars": len(body.note)})
    return {"ok": True}


@app.get("/api/audit/verify")
def verify_audit():
    ok, broken_line = audit.verify()
    return {"ok": ok, "broken_line": broken_line}
