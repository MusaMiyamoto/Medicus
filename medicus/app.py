"""Web API and UI. Endpoints are plain `def` so slow CPU work runs in FastAPI's thread pool.

Who you are comes from the card login (medicus-authd), so there is no separate login here:
    normal session   journal assistant + patient record
    emergency        only /nod: life-critical information, read-only
    it               only the Sikkerhetssenter; never patient data
Anyone who has opened emergency access writes the report at /rapport.
"""

import json
import os
import secrets
import sys
import tempfile
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from epj import epic, get_journal
from epj import token as epj_token
from helsenett import config as integration
from helsenett import fnr as fnrlib
from helsenett.client import HelsenettError, get_client
import utstyr
from tilgang import arbeidssted
from tilgang.client import AuthError
from tilgang.client import call as auth_call

from . import demo, kilder, nettsteder, notes, revisjon, sikkerhet
from .audit import AuditLog
from .config import settings

STATIC = Path(__file__).parent / "static"
SAMPLE = Path(__file__).parent.parent / "samples" / "konsultasjon_eksempel.txt"
LOGO = Path(__file__).parent.parent / "branding" / "medicus-logo.svg"
BROWSER_LOGO = Path(__file__).parent.parent / "branding" / "nettleser.svg"

@asynccontextmanager
async def lifespan(_app):
    check_audit_chain()
    if settings.warmup:
        # In the background, so the service is up at once and Whisper is ready before the first patient.
        from .transcribe import warmup
        threading.Thread(target=warmup, name="whisper-warmup", daemon=True).start()
    yield


app = FastAPI(title="Medicus", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def privacy_headers(request, call_next):
    # External sites opened from a Medicus page never see where the user came from.
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Patient data is never written to the browser's disk cache. Pages and scripts are checked against
    # the server every time, so an update never leaves old page code running against a new API.
    api = request.url.path.startswith("/api/")
    response.headers["Cache-Control"] = "no-store" if api else "no-cache"
    return response


@app.middleware("http")
async def demo_visitor(request, call_next):
    # The public web demo only (settings.demo); in Medicus OS this does nothing. Added last, so it runs
    # first: every route below knows this browser's demo session.
    if not settings.demo:
        if request.url.path == "/demo" or request.url.path.startswith("/api/demo"):
            return JSONResponse({"detail": "Ikke funnet."}, status_code=404)
        return await call_next(request)
    demo.current.set(demo.visitor_for(request.cookies.get(demo.COOKIE)))
    if request.method == "GET" and demo.needs_login(request.url.path):
        return RedirectResponse("/demo", status_code=303)
    token = None
    if demo.current.get() is None and request.method == "POST" and request.url.path in demo.STARTS:
        token = demo.new_visitor()
    response = await call_next(request)
    if token:
        demo.set_cookie(request, response, token)
    return response


app.include_router(demo.router)


audit = AuditLog(settings.audit_log)
audit_at_start: dict = {}  # {"ok", "linje"}: the chain check when the service started


def check_audit_chain():
    """Check this service's audit log chain at start, and say so loudly (and in the log) if it's broken."""
    ok, line = audit.verify()
    audit_at_start.update(ok=ok, linje=line)
    if not ok:
        print(f"REVISJONSLOGGEN ER BRUTT på linje {line} ({settings.audit_log}). "
              "Kjør «sudo medicus-revisjon sjekk».", file=sys.stderr)
        audit.record("system", "audit_chain_broken_at_start", {"linje": line})


def audit_chain_check() -> dict:
    """For the Sikkerhetssenter."""
    name = "Revisjonskjede"
    if not audit_at_start:
        return {"navn": name, "status": sikkerhet.INFO, "forklaring": "Kjeden sjekkes når Medicus starter."}
    if audit_at_start["ok"]:
        return {"navn": name, "status": sikkerhet.OK, "forklaring": "Loggkjeden var hel da Medicus startet."}
    return {"navn": name, "status": sikkerhet.FAIL,
            "forklaring": f"Loggkjeden er brutt på linje {audit_at_start['linje']}. Noen kan ha endret loggen. "
                          "Varsle sikkerhetsteamet og kjør «sudo medicus-revisjon sjekk»."}


def current_session() -> dict | None:
    """The logged-in person. MEDICUS_DEV_IDENTITY (JSON) is for development without the OS."""
    if settings.demo:
        return demo.session()
    dev = os.getenv("MEDICUS_DEV_IDENTITY")
    if dev:
        return json.loads(dev)
    try:
        session = auth_call("status")["okt"]
    except AuthError:
        return None
    # Card taken out: the session is only held for the card to come back. Nothing may use it meanwhile.
    return None if session and "holdt_sekunder_igjen" in session else session


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


def journal():
    """Where approved notes go and the doctor's patient list comes from (helsenett or DIPS)."""
    return get_journal()


# How long the record system takes to answer (seconds, newest last). Only durations: no people,
# no patients. Shown as a median in the Sikkerhetssenter, so slowness can be proven and followed up.
response_times: deque = deque(maxlen=200)


def timed(call, *args):
    start = time.monotonic()
    try:
        return call(*args)
    finally:
        response_times.append(time.monotonic() - start)


# The doctor's patient list, fetched at login (medicus-forhent) so the picker is ready at once.
# Kept in memory only, for PATIENT_LIST_SECONDS, and only for the same person in the same login.
PATIENT_LIST_SECONDS = 300
patient_lists: dict = {}


def cached_patient_list(session: dict, refresh: bool = False) -> dict:
    key = (session["hpr"], session.get("startet"))
    now = time.monotonic()
    for old in [k for k, (at, _) in patient_lists.items() if now - at > PATIENT_LIST_SECONDS]:
        del patient_lists[old]
    if refresh or key not in patient_lists:
        j = journal()
        patient_lists[key] = (now, {"system": j.name, "pasienter": timed(j.my_patients, actor(session))})
    at, data = patient_lists[key]
    return {**data, "hentet_for_sekunder": round(now - at)}


def checked_fnr(fnr: str) -> str:
    if not fnrlib.is_valid(fnr):
        raise HTTPException(422, "Ugyldig fødselsnummer.")
    return fnr


class TranscriptIn(BaseModel):
    transcript: str


class ApprovalIn(BaseModel):
    note: str = Field(min_length=1, max_length=20000)
    fnr: str = ""  # the chosen patient: then the note is saved in their record


class ConsentIn(BaseModel):
    svar: str = Field(pattern="^(ja|nei)$")


class NoteIn(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    notat: str = Field(min_length=1, max_length=20000)


class ReasonIn(BaseModel):
    begrunnelse: str = Field(min_length=1, max_length=40)
    forklaring: str = Field(default="", max_length=300)


# Why someone opens a record of a patient who is not on their own list (not their fastlege-list patient,
# and not seen by them). Logged where the patient can see it, on Helsenorge.
REASONS = ("Pasienten er hos meg nå", "Tilsyn eller konsultasjon", "Vakt", "Henvisning eller epikrise", "Annet")


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
    keep = ("navn", "rolle", "stilling", "virksomhet", "hpr", "modus", "situasjon", "sekunder_igjen", "rapporter",
            "demo")
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


def is_own_patient(session: dict, fnr: str) -> bool:
    """On the clinician's own list. If the list can't be fetched, nobody is: then a reason is asked for."""
    try:
        return any(p.get("fnr") == fnr for p in cached_patient_list(session)["pasienter"])
    except Exception:  # noqa: BLE001 - the journal system is down; ask for a reason rather than block
        return False


def read_record(fnr: str, session: dict, reason: str) -> dict:
    client = helsenett()
    record = {
        "pasient": client.find_patient(fnr),
        "kritisk": client.critical_info(fnr),
        "kontakter": client.encounters(fnr),
        "resepter": client.prescriptions(fnr),
    }
    client.log_access(fnr, actor(session), "normal", reason, "Journal")
    return record


@app.get("/api/pasient/{fnr}")
def open_patient(fnr: str, session: dict = Depends(normal_session)):
    fnr = checked_fnr(fnr)
    if not is_own_patient(session, fnr):
        raise HTTPException(409, {"begrunnelse_kreves": True, "valg": REASONS,
                                  "melding": "Pasienten er ikke på listen din. Oppgi hvorfor du åpner journalen."})
    record = read_record(fnr, session, "Behandling")
    audit.record(session["hpr"], "patient_opened", {"patient": fnrlib.mask(fnr)})
    return record


@app.post("/api/pasient/{fnr}/apne")
def open_patient_with_reason(fnr: str, body: ReasonIn, session: dict = Depends(normal_session)):
    """A patient outside the clinician's list: the reason is shown to the patient and kept in the audit log."""
    fnr = checked_fnr(fnr)
    if body.begrunnelse not in REASONS:
        raise HTTPException(422, "Velg en begrunnelse fra listen.")
    explanation = " ".join(body.forklaring.split())
    if body.begrunnelse == "Annet" and len(explanation) < 10:
        raise HTTPException(422, "Skriv kort hvorfor du åpner journalen (minst 10 tegn).")
    reason = f"{body.begrunnelse}: {explanation}" if explanation else body.begrunnelse
    record = read_record(fnr, session, reason)
    audit.record(session["hpr"], "patient_opened_with_reason", {"patient": fnrlib.mask(fnr), "begrunnelse": reason})
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


def workplace_check() -> dict:
    site = arbeidssted.load()
    return sikkerhet.workplace(site.id, site.navn, arbeidssted.certificate_site())


@app.get("/api/sikkerhet")
def security_status(_session: dict = Depends(it_session)):
    try:
        late = [] if settings.demo else auth_call("overdue")["rapporter"]
    except AuthError:
        late = None
    devices = sikkerhet.medical_devices(utstyr.connected(), utstyr.load())
    return sikkerhet.checks() + [sikkerhet.emergency_reports(late), devices, sikkerhet.machine_certificate(),
                                 sikkerhet.response_time(list(response_times)), revisjon.status_check(),
                                 audit_chain_check(), workplace_check()]


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
    if settings.demo:
        try:
            return demo.write_report(body.id, body.tekst)
        except (ValueError, LookupError) as e:
            raise HTTPException(422, str(e)) from e
    try:
        return auth_call("report", id=body.id, tekst=body.tekst)["rapport"]
    except AuthError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/nod/avslutt")
def emergency_end(session: dict = Depends(emergency_session)):
    if settings.demo:
        demo.end()
        return {"ok": True}
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

    if settings.demo:
        raise HTTPException(403, "Opptak er slått av i demoen: her finnes ingen talegjenkjenning. "
                                 "Trykk «Last eksempel» for å prøve med eksempelsamtalen.")
    if not has_consent(session):
        raise HTTPException(403, "Pasienten må samtykke før samtalen tas opp eller lastes opp.")

    suffix = Path(audio.filename or "").suffix or ".webm"
    max_bytes = settings.upload_max_mb * 1024 * 1024
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        # Copied in pieces, and stopped as soon as it's too big, so a huge file never fills the disk.
        size = 0
        with os.fdopen(fd, "wb") as f:
            while chunk := audio.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Lydfilen er for stor (over {settings.upload_max_mb} MB).")
                f.write(chunk)
        text, seconds = transcribe(path)
    except HTTPException:
        audit.record(session["hpr"], "transcribe_refused_too_large", {"max_mb": settings.upload_max_mb})
        raise
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
        if settings.demo:
            try:
                note = demo.example_note(body.transcript)
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
        else:
            note = notes.generate_note(body.transcript)
    except notes.NoteError as e:
        # The error's type only (what caused it, e.g. ConnectError), like transcribe_failed: no free text.
        audit.record(session["hpr"], "note_failed", {"error": type(e.__cause__ or e).__name__})
        raise HTTPException(502, str(e)) from e
    checked = kilder.check_note(body.transcript, note)
    audit.record(session["hpr"], "note_generated", {"model": settings.llm_model, "chars": len(body.transcript),
                                                    "sentences_without_source": checked["uten_kilde"]})
    return {
        "sections": [{"key": k, "label": label, "text": note[k]} for k, label in notes.SECTIONS],
        "text": notes.format_note(note),
        "kilder": checked,
    }


class SourceCheckIn(BaseModel):
    transcript: str = Field(max_length=100_000)
    seksjoner: dict[str, str]


@app.post("/api/kildesjekk")
def check_sources(body: SourceCheckIn, _session: dict = Depends(normal_session)):
    """The clinician edited the draft: check its sentences against the conversation again.
    Nothing is stored; it is plain word matching, no language model."""
    if sum(len(text) for text in body.seksjoner.values()) > 50_000:
        raise HTTPException(413, "Notatet er for langt.")
    return kilder.check_note(body.transcript, body.seksjoner)


@app.get("/api/journal/pasienter")
def my_patients(oppdater: bool = False, session: dict = Depends(normal_session)):
    """The doctor's own patients, for the patient picker. Searching happens in the browser."""
    return cached_patient_list(session, refresh=oppdater)


@app.get("/api/journal/pasient/{fnr}")
def look_up_patient(fnr: str, session: dict = Depends(normal_session)):
    """A patient who is not on the doctor's list, typed in by fødselsnummer."""
    patient = timed(journal().find_patient, checked_fnr(fnr))
    audit.record(session["hpr"], "patient_looked_up", {"patient": fnrlib.mask(fnr)})
    return patient


@app.post("/api/approve")
def approve(body: ApprovalIn, session: dict = Depends(normal_session)):
    saved = None
    if body.fnr:
        j = journal()
        timed(j.save_note, checked_fnr(body.fnr), actor(session), "Journalnotat", body.note)
        saved = j.name
    audit.record(session["hpr"], "note_approved", {"chars": len(body.note), "samtykke_opptak": has_consent(session),
                                                    "patient": fnrlib.mask(body.fnr) if saved else None,
                                                    "saved_in": saved})
    drafts.pop(session["hpr"], None)  # approved: the draft is done
    return {"ok": True, "lagret_i": saved}


# --- Unfinished notes (utkast) ---------------------------------------------------
# If the session ends before the note is approved (the card wasn't back within 15 minutes, or a
# colleague logged in), the work isn't lost: the page saves the draft here as you type, and offers
# it back at your next login. In this service's memory only (never on disk), only for the same
# person, for at most one shift, and gone once approved or discarded.

DRAFT_SECONDS = 12 * 3600
drafts: dict[str, dict] = {}  # hpr -> {"at", "transcript", "seksjoner", "fnr"}


class DraftIn(BaseModel):
    transcript: str = Field(max_length=100_000)
    seksjoner: dict[str, str] = {}
    fnr: str = Field("", max_length=11)


def _drop_old_drafts():
    for hpr in [h for h, d in drafts.items() if time.time() - d["at"] > DRAFT_SECONDS]:
        del drafts[hpr]


@app.put("/api/utkast")
def save_draft(body: DraftIn, session: dict = Depends(normal_session)):
    if sum(len(t) for t in body.seksjoner.values()) > 50_000:
        raise HTTPException(413, "Notatet er for langt.")
    _drop_old_drafts()
    if not body.transcript.strip() and not any(t.strip() for t in body.seksjoner.values()):
        drafts.pop(session["hpr"], None)
        return {"lagret": False}
    drafts[session["hpr"]] = {"at": time.time(), **body.model_dump()}
    return {"lagret": True}


@app.get("/api/utkast")
def get_draft(session: dict = Depends(normal_session)):
    _drop_old_drafts()
    draft = drafts.get(session["hpr"])
    if draft is None:
        return {"utkast": None}
    saved = datetime.fromtimestamp(draft["at"]).strftime("%H:%M")
    return {"utkast": {k: draft[k] for k in ("transcript", "seksjoner", "fnr")} | {"lagret_kl": saved}}


@app.delete("/api/utkast")
def discard_draft(session: dict = Depends(normal_session)):
    if drafts.pop(session["hpr"], None) is not None:
        audit.record(session["hpr"], "draft_discarded", {})
    return {"ok": True}


# --- Moving a record from Epic (normal login) --------------------------------
# Two steps: the export is read and shown (forhåndsvisning), then the clinician confirms the
# patient and imports it. The preview waits on the server for TRANSFER_SECONDS.

TRANSFER_SECONDS = 30 * 60
MAX_EXPORT_BYTES = 20 * 1024 * 1024
transfers: dict[str, dict] = {}  # preview id -> {"hpr", "at", "data"}


class FetchIn(BaseModel):
    fnr: str


class ImportIn(BaseModel):
    id: str
    fnr: str


@app.get("/overforing")
def transfer_page():
    return FileResponse(STATIC / "overforing.html")


def transfer_preview(session: dict, transfer: dict) -> dict:
    for key in [k for k, v in transfers.items() if time.time() - v["at"] > TRANSFER_SECONDS]:
        del transfers[key]
    preview_id = secrets.token_urlsafe(12)
    transfers[preview_id] = {"hpr": session["hpr"], "at": time.time(), "data": transfer}
    j = journal()
    try:
        here = j.find_patient(transfer["pasient"]["fnr"])
    except HelsenettError:
        here = None
    audit.record(session["hpr"], "transfer_previewed",
                 {"patient": fnrlib.mask(transfer["pasient"]["fnr"]), "source": transfer["kilde"]})
    return {**transfer, "id": preview_id, "her": here, "journalsystem": j.name}


@app.post("/api/overforing/epic/fil")
def transfer_from_file(fil: UploadFile, session: dict = Depends(normal_session)):
    raw = fil.file.read(MAX_EXPORT_BYTES + 1)
    if len(raw) > MAX_EXPORT_BYTES:
        raise HTTPException(413, "Filen er for stor (over 20 MB).")
    try:
        transfer = epic.read_bundle(json.loads(raw))
    except ValueError as e:
        raise HTTPException(422, "Filen er ikke en gyldig FHIR-eksport (JSON).") from e
    except epic.TransferError as e:
        raise HTTPException(422, str(e)) from e
    return transfer_preview(session, transfer)


@app.post("/api/overforing/epic/hent")
def transfer_from_server(body: FetchIn, session: dict = Depends(normal_session)):
    settings = integration.load().get("epic", {})
    source = epic.EpicSource(settings.get("fhir_url") or "http://epic.invalid",
                             epj_token.from_file(settings.get("token_fil", ""), "Epic"))
    try:
        transfer = epic.read_bundle(source.bundle_for(checked_fnr(body.fnr)))
    except epic.TransferError as e:
        raise HTTPException(422, str(e)) from e
    return transfer_preview(session, transfer)


@app.post("/api/overforing/importer")
def transfer_import(body: ImportIn, session: dict = Depends(normal_session)):
    item = transfers.get(body.id)
    if item is None or item["hpr"] != session["hpr"] or time.time() - item["at"] > TRANSFER_SECONDS:
        raise HTTPException(404, "Forhåndsvisningen er utløpt. Last inn eksporten på nytt.")
    transfer = item["data"]
    fnr = transfer["pasient"]["fnr"]
    if body.fnr != fnr:
        raise HTTPException(422, "Pasienten du bekreftet stemmer ikke med eksporten.")
    j, who = journal(), actor(session)
    notes = epic.journal_notes(transfer, who, date.today().isoformat())
    for title, text in notes:
        j.save_note(fnr, who, title, text)
    del transfers[body.id]
    # The patient sees on Helsenorge that their record was moved, and by whom.
    helsenett().log_access(fnr, who, "normal", f"Overføring av journal fra {transfer['kilde']}", "Journal")
    audit.record(session["hpr"], "record_transferred",
                 {"patient": fnrlib.mask(fnr), "source": transfer["kilde"], "notes": len(notes), "saved_in": j.name})
    return {"ok": True, "notater": len(notes), "lagret_i": j.name}


@app.get("/api/audit/verify")
def verify_audit():
    ok, broken_line = audit.verify()
    return {"ok": ok, "broken_line": broken_line}
