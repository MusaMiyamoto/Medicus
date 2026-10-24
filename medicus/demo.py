"""The public web demo (MEDICUS_DEMO=1): try Medicus in a browser, with synthetic data only.

In Medicus OS you log in with a health-personnel card at the login screen (medicus-authd). A web demo
has no card reader, so this module stands in for it: the same demo cards (PIN 1234) and workplaces,
picked on /demo. Each browser gets its own session behind a random cookie, in memory only. Three wrong
PINs block that card, but only for that browser, so one visitor can't lock the demo for everyone.
Never switched on in Medicus OS.

The journal assistant has no speech or language model here: recordings are turned off, and the
example conversation becomes a fixed example note, marked as such.
"""

import contextvars
import json
import secrets
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tilgang import EMERGENCY_MINUTES, IT_ROLE, SITUATIONS
from tilgang.arbeidssted import Arbeidssted, position
from tilgang.cards import MAX_TRIES
from tilgang.nodrapport import Reports

ROOT = Path(__file__).parent.parent
CARDS = ROOT / "os/config/includes.chroot/etc/medicus/simkort-demo.json"
SITES = ROOT / "os/config/includes.chroot/etc/medicus/arbeidssteder-sim.json"
SAMPLE = ROOT / "samples/konsultasjon_eksempel.txt"
EXAMPLE_NOTE = ROOT / "samples/konsultasjon_eksempel_notat.json"
PAGE = Path(__file__).parent / "static" / "demo.html"

COOKIE = "medicus_demo"
VISITOR_SECONDS = 8 * 3600  # a browser's demo is forgotten after this long without use
MAX_VISITORS = 1000         # so a flood of new browsers can't fill the memory
# Pages that need a login: without one, the demo sends the visitor to the card picker.
PAGES = {"/", "/pasient", "/post", "/sikkerhet", "/nod", "/rapport", "/overforing"}
# Where a new browser gets its visitor (and cookie): logging in or emergency access on the card picker.
STARTS = {"/api/demo/logginn", "/api/demo/nod"}


class Visitor:
    def __init__(self):
        self.session: dict | None = None
        self.tries: dict[str, int] = {}  # wrong PINs per card, for this browser only
        self.reports = Reports(None, time.time)  # emergency reports, in memory
        self.seen = time.time()


visitors: dict[str, Visitor] = {}
# This request's visitor, set by the middleware in app.py from the cookie.
current: contextvars.ContextVar[Visitor | None] = contextvars.ContextVar("demo_visitor", default=None)


def load_cards() -> dict[str, dict]:
    return {c["card_id"]: c for c in json.loads(CARDS.read_text(encoding="utf-8"))}


def load_sites() -> list[Arbeidssted]:
    return [Arbeidssted(s["id"], s["navn"]) for s in json.loads(SITES.read_text(encoding="utf-8"))]


def visitor_for(token: str | None) -> Visitor | None:
    visitor = visitors.get(token) if token else None
    if visitor is not None:
        visitor.seen = time.time()
    return visitor


def _forget_old():
    now = time.time()
    for token in [t for t, v in visitors.items() if now - v.seen > VISITOR_SECONDS]:
        del visitors[token]
    extra = len(visitors) - MAX_VISITORS + 1
    if extra > 0:  # the least recently used go first
        for token in sorted(visitors, key=lambda t: visitors[t].seen)[:extra]:
            del visitors[token]


def session() -> dict | None:
    """This browser's session, shaped like medicus-authd's status, for current_session() in app.py."""
    visitor = current.get()
    if visitor is None or visitor.session is None:
        return None
    s = dict(visitor.session)
    if s["modus"] == "nød":
        left = int(s["utloper"] - time.time())
        if left <= 0:  # 30 minutes are up: emergency access closes, as in the OS
            visitor.session = None
            return None
        s["sekunder_igjen"] = left
    s["rapporter"] = visitor.reports.missing(s["hpr"])
    s["demo"] = True
    return s


def needs_login(path: str) -> bool:
    return path in PAGES and session() is None


def write_report(report_id: str, text: str) -> dict:
    """The emergency report. Raises ValueError (too short) or LookupError (no such open report)."""
    s = session()
    if s is None:
        raise LookupError("Du er ikke logget inn.")
    return current.get().reports.write(report_id, s["hpr"], text)


def end():
    visitor = current.get()
    if visitor is not None:
        visitor.session = None


def example_note(transcript: str) -> dict[str, str]:
    """The fixed note for the example conversation. Anything else can't be turned into a note here."""
    if " ".join(transcript.split()) != " ".join(SAMPLE.read_text(encoding="utf-8").split()):
        raise ValueError("I demoen finnes det ingen språkmodell. Bare eksempelsamtalen kan gjøres om til et notat "
                         "(et ferdig eksempelnotat). Trykk «Last eksempel» og prøv igjen.")
    return json.loads(EXAMPLE_NOTE.read_text(encoding="utf-8"))


# --- The card picker -----------------------------------------------------------

router = APIRouter()


class LoginIn(BaseModel):
    kort: str = Field(max_length=40)
    pin: str = Field(default="", max_length=12)
    arbeidssted: str = Field(max_length=60)


class EmergencyIn(BaseModel):
    kort: str = Field(max_length=40)
    situasjon: str = Field(default="", max_length=80)
    arbeidssted: str = Field(max_length=60)


def new_visitor() -> str:
    """A new browser, on its first card picker action. Returns the token for its cookie."""
    _forget_old()
    token = secrets.token_urlsafe(24)
    visitor = visitors[token] = Visitor()
    current.set(visitor)
    return token


def set_cookie(request: Request, response: Response, token: str):
    # Set by the middleware in app.py, so it reaches the browser on error replies too (a wrong PIN):
    # otherwise every wrong PIN from a new browser would count as its first.
    response.set_cookie(COOKIE, token, max_age=VISITOR_SECONDS, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https")


def _visitor() -> Visitor:
    visitor = current.get()
    if visitor is None:
        raise HTTPException(400, "Demoøkten mangler. Last siden på nytt.")
    return visitor


def _card_and_site(card_id: str, site_id: str) -> tuple[dict, Arbeidssted]:
    card = load_cards().get(card_id)
    if card is None:
        raise HTTPException(404, "Ukjent kort.")
    site = next((s for s in load_sites() if s.id == site_id), None)
    if site is None:
        raise HTTPException(422, "Velg et arbeidssted.")
    return card, site


def _new_session(card: dict, site: Arbeidssted, mode: str) -> dict:
    return {"navn": card["navn"], "rolle": card["rolle"], "hpr": card["hpr"], "modus": mode,
            "startet": datetime.now().isoformat(timespec="seconds"),
            "virksomhet": site.navn, "arbeidssted_id": site.id,
            "stilling": position(card.get("stillinger", {}), card["rolle"], site)}


def _check_not_blocked(visitor: Visitor, card_id: str):
    if visitor.tries.get(card_id, 0) >= MAX_TRIES:
        raise HTTPException(423, "Kortet er sperret etter tre feil PIN-forsøk. I Medicus OS må IT låse det opp. "
                                 "I demoen: trykk «Start demoen på nytt».")


@router.get("/demo")
def demo_page():
    return FileResponse(PAGE)


@router.get("/api/demo")
def demo_info():
    visitor = current.get()
    cards = [{"kort": c["card_id"], "navn": c["navn"], "rolle": c["rolle"],
              "sperret": visitor is not None and visitor.tries.get(c["card_id"], 0) >= MAX_TRIES}
             for c in load_cards().values()]
    s = session()
    return {"kort": cards, "arbeidssteder": [s.public() for s in load_sites()], "situasjoner": SITUATIONS,
            "okt": {k: s[k] for k in ("navn", "rolle", "stilling", "virksomhet", "modus")} if s else None}


@router.post("/api/demo/logginn")
def demo_login(body: LoginIn):
    visitor = _visitor()
    card, site = _card_and_site(body.kort, body.arbeidssted)
    _check_not_blocked(visitor, body.kort)
    if not secrets.compare_digest(body.pin.encode(), card["demo_pin"].encode()):
        visitor.tries[body.kort] = visitor.tries.get(body.kort, 0) + 1
        left = MAX_TRIES - visitor.tries[body.kort]
        raise HTTPException(401, f"Feil PIN. {left} forsøk igjen." if left else "Feil PIN. Kortet er nå sperret.")
    visitor.tries[body.kort] = 0
    mode = "it" if card["rolle"] == IT_ROLE else "normal"
    visitor.session = _new_session(card, site, mode)
    return {"modus": mode, "til": "/sikkerhet" if mode == "it" else "/demo"}


@router.post("/api/demo/nod")
def demo_emergency(body: EmergencyIn):
    """Emergency access: card and a tap on the situation, no PIN. A report is due afterwards."""
    visitor = _visitor()
    card, site = _card_and_site(body.kort, body.arbeidssted)
    if card["rolle"] == IT_ROLE:
        raise HTTPException(403, "Nødtilgang er bare for helsepersonell.")
    _check_not_blocked(visitor, body.kort)
    situation = body.situasjon if body.situasjon in SITUATIONS else "Ikke oppgitt"
    report = visitor.reports.open(card["hpr"], card["navn"], situation)
    visitor.session = _new_session(card, site, "nød") | {
        "situasjon": situation, "rapport_id": report["id"], "utloper": time.time() + EMERGENCY_MINUTES * 60}
    return {"modus": "nød", "til": "/nod"}


@router.post("/api/demo/loggut")
def demo_logout():
    end()
    return {"ok": True}


@router.post("/api/demo/nullstill")
def demo_reset(response: Response):
    """Start over: forget this browser's session, blocked cards and reports."""
    visitor = current.get()
    for token in [t for t, v in visitors.items() if v is visitor]:
        del visitors[token]
    current.set(None)
    response.delete_cookie(COOKIE)
    return {"ok": True}
