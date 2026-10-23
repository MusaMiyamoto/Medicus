"""Web API and UI. Endpoints are plain `def` so slow CPU work runs in FastAPI's thread pool.

Who you are comes from the card login (medicus-authd), so there is no separate login here:
    normal session   journal assistant + patient record
    emergency        only /nod: life-critical information, read-only
    it               only the Sikkerhetssenter; never patient data
Anyone who has opened emergency access writes the report at /rapport.
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from helsenett import fnr as fnrlib
from helsenett.client import HelsenettError, get_client
from tilgang.client import AuthError
from tilgang.client import call as auth_call

from . import nettsteder, notes, sikkerhet
from .audit import AuditLog
from .config import settings

STATIC = Path(__file__).parent / "static"
SAMPLE = Path(__file__).parent.parent / "samples" / "konsultasjon_eksempel.txt"
LOGO = Path(__file__).parent.parent / "branding" / "medicus-logo.svg"
BROWSER_LOGO = Path(__file__).parent.parent / "branding" / "nettleser.svg"

app = FastAPI(title="Medicus", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def privacy_headers(request, call_next):
    # External sites opened from a Medicus page never see where the user came from.
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
audit = AuditLog(settings.audit_log)


def current_session() -> dict | None:
    """The logged-in person. MEDICUS_DEV_IDENTITY (JSON) is for development without the OS."""
    dev = os.getenv("MEDICUS_DEV_IDENTITY")
    if dev:
        return json.loads(dev)
    try:
        return auth_call("status")["okt"]
    except AuthError:
        return None


def normal_session() -> dict:
    session = current_session()
    if session is None:
        raise HTTPException(401, "Du er ikke logget inn.")
    if session["modus"] == "it":
        raise HTTPException(403, "IT-modus har ikke tilgang til pasientdata.")
    if session["modus"] != "normal":
        raise HTTPException(403, "Ikke tilgjengelig ved nødtilgang.")
    return session


def it_session() -> dict:
    session = current_session()
    if session is None or session["modus"] != "it":
        raise HTTPException(403, "Bare for IT-personell i IT-modus.")
    return session


def emergency_session() -> dict:
    session = current_session()
    if session is None or session["modus"] != "nød":
        raise HTTPException(403, "Krever nødtilgang.")
    return session


def actor(session: dict) -> dict:
    return {k: session[k] for k in ("navn", "rolle", "virksomhet", "hpr")}


def helsenett():
    return get_client()


def checked_fnr(fnr: str) -> str:
    if not fnrlib.is_valid(fnr):
        raise HTTPException(422, "Ugyldig fødselsnummer.")
    return fnr


class TranscriptIn(BaseModel):
    transcript: str


class ApprovalIn(BaseModel):
    note: str


class ConsentIn(BaseModel):
    svar: str = Field(pattern="^(ja|nei)$")


class NoteIn(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    notat: str = Field(min_length=1, max_length=20000)


class PrescriptionIn(BaseModel):
    legemiddel: str = Field(min_length=1, max_length=200)
    dosering: str = Field(min_length=1, max_length=300)
    indikasjon: str = Field(min_length=1, max_length=300)


@app.exception_handler(HelsenettError)
def helsenett_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=502)


# --- Pages -----------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/logo.svg")
def logo():
    return FileResponse(LOGO, media_type="image/svg+xml")


@app.get("/nettleser.svg")
def browser_logo():
    return FileResponse(BROWSER_LOGO, media_type="image/svg+xml")


@app.get("/pasient")
def patient_page():
    return FileResponse(STATIC / "pasient.html")


@app.get("/nod")
def emergency_page():
    return FileResponse(STATIC / "nod.html")


@app.get("/rapport")
def report_page():
    return FileResponse(STATIC / "rapport.html")


@app.get("/om")
def about_page():
    return FileResponse(STATIC / "om.html")


@app.get("/api/meg")
def me():
    session = current_session()
    if session is None:
        raise HTTPException(401, "Du er ikke logget inn.")
    keep = ("navn", "rolle", "stilling", "virksomhet", "hpr", "modus", "situasjon", "sekunder_igjen", "rapporter")
    return {k: session[k] for k in keep if k in session}


# --- Patient record (normal login) -----------------------------------------

@app.get("/api/pasienter")
def synthetic_patients(session: dict = Depends(current_session)):
    """Simulation only: the synthetic test patients, so demos don't need to type numbers."""
    if session is None:
        raise HTTPException(401, "Du er ikke logget inn.")
    if session["modus"] == "it":
        raise HTTPException(403, "IT-modus har ikke tilgang til pasientdata.")
    return helsenett().list_patients()


@app.get("/api/pasient/{fnr}")
def open_patient(fnr: str, session: dict = Depends(normal_session)):
    fnr = checked_fnr(fnr)
    client = helsenett()
    record = {
        "pasient": client.find_patient(fnr),
        "kritisk": client.critical_info(fnr),
        "kontakter": client.encounters(fnr),
        "resepter": client.prescriptions(fnr),
    }
    client.log_access(fnr, actor(session), "normal", "Behandling", "Journal")
    audit.record(session["hpr"], "patient_opened", {"patient": fnrlib.mask(fnr)})
    return record


@app.post("/api/pasient/{fnr}/notat")
def add_note(fnr: str, body: NoteIn, session: dict = Depends(normal_session)):
    entry = helsenett().add_note(checked_fnr(fnr), actor(session), body.type, body.notat)
    audit.record(session["hpr"], "note_shared", {"patient": fnrlib.mask(fnr), "chars": len(body.notat)})
    return entry


@app.post("/api/pasient/{fnr}/resept")
def prescribe(fnr: str, body: PrescriptionIn, session: dict = Depends(normal_session)):
    if session["rolle"] != "Lege":
        raise HTTPException(403, "Bare leger kan forskrive resept.")
    entry = helsenett().prescribe(checked_fnr(fnr), actor(session), body.legemiddel, body.dosering, body.indikasjon)
    audit.record(session["hpr"], "prescription_sent", {"patient": fnrlib.mask(fnr)})
    return entry


# --- Medicus Post: messages and image sharing (normal login) ---------------

@app.get("/post")
def post_page():
    return FileResponse(STATIC / "post.html")


@app.get("/api/post/adresser")
def post_directory(_session: dict = Depends(normal_session)):
    return helsenett().directory()


@app.get("/api/post/innboks")
def post_inbox(session: dict = Depends(normal_session)):
    return helsenett().inbox(actor(session))


@app.get("/api/post/sendt")
def post_sent(session: dict = Depends(normal_session)):
    return helsenett().sent(actor(session))


@app.get("/api/post/{message_id}")
def post_read(message_id: int, session: dict = Depends(normal_session)):
    return helsenett().read_message(actor(session), message_id)


@app.post("/api/post/{message_id}/rapporter")
def post_report(message_id: int, session: dict = Depends(normal_session)):
    audit.record(session["hpr"], "phishing_reported", {"message": message_id})
    return helsenett().report_message(actor(session), message_id)


@app.post("/api/post")
def post_send(til: list[str] = Form(...), emne: str = Form(...), tekst: str = Form(...), fnr: str = Form(""),
              filer: list[UploadFile] = File(default=[]), session: dict = Depends(normal_session)):
    if fnr:
        checked_fnr(fnr)
    files = [(f.filename or "vedlegg", f.file.read(), f.content_type or "application/octet-stream") for f in filer]
    result = helsenett().send_message(actor(session), til, emne, tekst, fnr, files)
    audit.record(session["hpr"], "message_sent", {"to": len(til), "attachments": len(files),
                                                   "patient": fnrlib.mask(fnr) if fnr else None})
    return result


@app.get("/api/post/vedlegg/{file_id}")
def post_attachment(file_id: str, visning: bool = False, session: dict = Depends(normal_session)):
    content, media_type, name = helsenett().attachment(actor(session), file_id, visning)
    headers = {} if visning else {"Content-Disposition": f'attachment; filename="{name}"'}
    return Response(content, media_type=media_type, headers=headers)


# --- Medicus Nettleser start page --------------------------------------------

@app.get("/nettsteder")
def sites_page():
    return FileResponse(STATIC / "nettsteder.html")


@app.get("/api/nettsteder")
def sites():
    return [{"gruppe": group, "nettsteder": [{"domene": d, "navn": n, "beskrivelse": b} for d, n, b in sites]}
            for group, sites in nettsteder.GROUPS]


# --- Sikkerhetssenter --------------------------------------------------------

@app.get("/sikkerhet")
def security_page():
    return FileResponse(STATIC / "sikkerhet.html")


@app.get("/api/sikkerhet")
def security_status(_session: dict = Depends(it_session)):
    try:
        late = auth_call("overdue")["rapporter"]
    except AuthError:
        late = None
    return sikkerhet.checks() + [sikkerhet.emergency_reports(late)]


# --- Emergency access ------------------------------------------------------

@app.get("/api/nod/pasient/{fnr}")
def emergency_patient(fnr: str, session: dict = Depends(emergency_session)):
    fnr = checked_fnr(fnr)
    client = helsenett()
    info = client.critical_info(fnr)
    client.log_access(fnr, actor(session), "nød", f"Nødtilgang: {session.get('situasjon', 'ikke oppgitt')}",
                      "Kritisk informasjon")
    audit.record(session["hpr"], "emergency_patient_opened", {"patient": fnrlib.mask(fnr)})
    return info


class ReportIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    tekst: str = Field(min_length=1, max_length=5000)


@app.post("/api/nodrapport")
def write_emergency_report(body: ReportIn, session: dict = Depends(current_session)):
    """The person who opened emergency access explains why. Works in a normal or emergency session."""
    if session is None:
        raise HTTPException(401, "Du er ikke logget inn.")
    try:
        return auth_call("report", id=body.id, tekst=body.tekst)["rapport"]
    except AuthError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/nod/avslutt")
def emergency_end(session: dict = Depends(emergency_session)):
    try:
        auth_call("end")
    except AuthError as e:
        raise HTTPException(500, str(e)) from e
    return {"ok": True}


# --- Journal assistant (normal login) --------------------------------------

@app.get("/api/sample")
def sample(_session: dict = Depends(normal_session)):
    return {"transcript": SAMPLE.read_text(encoding="utf-8")}


# Recording a consultation needs the patient's yes. The doctor confirms it on screen before the
# recording starts; the answer is logged. A "yes" lasts for one consultation (CONSENT_SECONDS).
CONSENT_SECONDS = 2 * 3600
consents: dict[str, float] = {}  # HPR number -> when the patient said yes


def has_consent(session: dict) -> bool:
    given = consents.get(session["hpr"])
    return given is not None and time.time() - given < CONSENT_SECONDS


@app.post("/api/samtykke")
def recording_consent(body: ConsentIn, session: dict = Depends(normal_session)):
    if body.svar == "ja":
        consents[session["hpr"]] = time.time()
    else:
        consents.pop(session["hpr"], None)
    audit.record(session["hpr"], "recording_consent", {"svar": body.svar})
    return {"ok": True}


@app.delete("/api/samtykke")
def withdraw_consent(session: dict = Depends(normal_session)):
    """The patient changed their mind: the recording is thrown away in the browser, never sent."""
    consents.pop(session["hpr"], None)
    audit.record(session["hpr"], "recording_consent_withdrawn", {})
    return {"ok": True}


@app.post("/api/transcribe")
def transcribe_audio(audio: UploadFile, session: dict = Depends(normal_session)):
    from .transcribe import transcribe

    if not has_consent(session):
        raise HTTPException(403, "Pasienten må samtykke før samtalen tas opp eller lastes opp.")

    suffix = Path(audio.filename or "").suffix or ".webm"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        text, seconds = transcribe(path)
    except Exception as e:
        audit.record(session["hpr"], "transcribe_failed", {"error": type(e).__name__})
        raise HTTPException(500, "Kunne ikke transkribere lydfilen.") from e
    finally:
        # The recording is deleted as soon as it has been transcribed.
        os.remove(path)
    audit.record(session["hpr"], "transcribe", {"audio_seconds": round(seconds), "chars": len(text)})
    return {"transcript": text}


@app.post("/api/note")
def create_note(body: TranscriptIn, session: dict = Depends(normal_session)):
    try:
        note = notes.generate_note(body.transcript)
    except notes.NoteError as e:
        audit.record(session["hpr"], "note_failed", {"error": str(e)})
        raise HTTPException(502, str(e)) from e
    audit.record(session["hpr"], "note_generated", {"model": settings.llm_model, "chars": len(body.transcript)})
    return {
        "sections": [{"key": k, "label": label, "text": note[k]} for k, label in notes.SECTIONS],
        "text": notes.format_note(note),
    }


@app.post("/api/approve")
def approve(body: ApprovalIn, session: dict = Depends(normal_session)):
    audit.record(session["hpr"], "note_approved", {"chars": len(body.note), "samtykke_opptak": has_consent(session)})
    return {"ok": True}


@app.get("/api/audit/verify")
def verify_audit():
    ok, broken_line = audit.verify()
    return {"ok": ok, "broken_line": broken_line}
