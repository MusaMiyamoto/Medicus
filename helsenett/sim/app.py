"""The simulator's API (used by Medicus through SimulatedClient) and its two web pages:

/helsenorge   what the patient sees: who opened their record, prescriptions, visits, disclosures
/utlevering   requests from authorities (e.g. police) and the institution's decision
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import fnr as fnrlib
from .. import hjemler
from . import seed
from .post import make_router

STATIC = Path(__file__).parent / "static"

CATEGORIES = ["Kritisk informasjon", "Legemidler", "Kontakter og notater"]


def now() -> str:
    return datetime.now().isoformat(timespec="minutes")


class Store:
    """All simulator data in one JSON file, written after each change."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = seed.state()
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def patient(self, fnr: str) -> dict:
        p = self.data["pasienter"].get(fnr)
        if p is None:
            raise HTTPException(404, "Fant ikke pasienten.")
        return p


class Actor(BaseModel):
    navn: str
    rolle: str
    virksomhet: str
    hpr: str


class NoteIn(BaseModel):
    aktor: Actor
    type: str = Field(min_length=1, max_length=80)
    notat: str = Field(min_length=1, max_length=20000)


class PrescriptionIn(BaseModel):
    aktor: Actor
    legemiddel: str = Field(min_length=1, max_length=200)
    dosering: str = Field(min_length=1, max_length=300)
    indikasjon: str = Field(min_length=1, max_length=300)


class AccessIn(BaseModel):
    aktor: Actor
    modus: str = Field(pattern="^(normal|nød)$")
    begrunnelse: str = Field(min_length=1, max_length=500)
    hva: str = Field(min_length=1, max_length=200)


class RequestIn(BaseModel):
    myndighetstype: str
    myndighet: str = Field(min_length=3, max_length=200)
    saksbehandler: str = Field(min_length=3, max_length=200)
    fnr: str
    hjemmel: str
    formal: str = Field(min_length=20, max_length=4000)
    data: list[str] = Field(min_length=1)
    periode: str = Field(default="", max_length=50)


class DecisionIn(BaseModel):
    beslutning: str = Field(pattern="^(godkjent|avslått)$")
    begrunnelse: str = Field(min_length=10, max_length=4000)
    behandlet_av: str = Field(min_length=3, max_length=200)
    varsle_pasient: bool = True
    utsatt_varsling_hjemmel: str = Field(default="", max_length=500)


def summary(p: dict) -> dict:
    return {"fnr": p["fnr"], "navn": p["navn"], "fodt": p["fodt"], "kjonn": p["kjonn"]}


def critical(p: dict) -> dict:
    return {
        "pasient": summary(p),
        "allergier": p["allergier"],
        "tilstander": p["tilstander"],
        "implantater": p["implantater"],
        "legemidler": [r for r in p["resepter"] if r["status"] == "Aktiv"],
        "parorende": p["parorende"],
    }


def create_app(state_path: Path) -> FastAPI:
    store = Store(state_path)
    app = FastAPI(title="Helsenett-simulator", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(make_router(store, state_path.parent / f"{state_path.stem}-vedlegg"))

    @app.get("/")
    def root():
        return RedirectResponse("/helsenorge")

    @app.get("/helsenorge")
    def helsenorge_page():
        return FileResponse(STATIC / "helsenorge.html")

    @app.get("/utlevering")
    def disclosure_page():
        return FileResponse(STATIC / "utlevering.html")

    @app.get("/api/pasienter")
    def list_patients():
        return [summary(p) for p in store.data["pasienter"].values()]

    @app.get("/api/pasient/{fnr}")
    def get_patient(fnr: str):
        p = store.patient(fnr)
        return {**summary(p), "fastlege": p["fastlege"]}

    @app.get("/api/kjernejournal/{fnr}")
    def get_critical(fnr: str):
        return critical(store.patient(fnr))

    @app.get("/api/journal/{fnr}")
    def get_encounters(fnr: str):
        return sorted(store.patient(fnr)["kontakter"], key=lambda k: k["tid"], reverse=True)

    @app.post("/api/journal/{fnr}")
    def add_encounter(fnr: str, body: NoteIn):
        with store.lock:
            entry = {"tid": now(), "virksomhet": body.aktor.virksomhet, "aktor": body.aktor.model_dump(),
                     "type": body.type, "notat": body.notat}
            store.patient(fnr)["kontakter"].append(entry)
            store.save()
        return entry

    @app.get("/api/resepter/{fnr}")
    def get_prescriptions(fnr: str):
        return sorted(store.patient(fnr)["resepter"], key=lambda r: r["tid"], reverse=True)

    @app.post("/api/resepter/{fnr}")
    def prescribe(fnr: str, body: PrescriptionIn):
        if body.aktor.rolle != "Lege":
            raise HTTPException(403, "Bare leger kan forskrive resept.")
        with store.lock:
            entry = {"tid": now(), "aktor": body.aktor.model_dump(), "legemiddel": body.legemiddel,
                     "dosering": body.dosering, "indikasjon": body.indikasjon, "status": "Aktiv"}
            store.patient(fnr)["resepter"].append(entry)
            store.save()
        return entry

    @app.get("/api/innsyn/{fnr}")
    def get_access_log(fnr: str):
        return sorted(store.patient(fnr)["innsyn"], key=lambda e: e["tid"], reverse=True)

    @app.post("/api/innsyn/{fnr}")
    def log_access(fnr: str, body: AccessIn):
        with store.lock:
            entry = {"tid": now(), "aktor": body.aktor.model_dump(), "modus": body.modus,
                     "begrunnelse": body.begrunnelse, "hva": body.hva}
            store.patient(fnr)["innsyn"].append(entry)
            store.save()
        return entry

    @app.get("/api/utleveringer/{fnr}")
    def get_disclosures(fnr: str):
        return store.patient(fnr)["utleveringer"]

    @app.get("/api/utlevering")
    def list_requests():
        return {"forespørsler": sorted(store.data["utleveringer"], key=lambda r: r["id"], reverse=True),
                "myndigheter": hjemler.AUTHORITIES, "kategorier": CATEGORIES}

    @app.post("/api/utlevering")
    def submit_request(body: RequestIn):
        if not fnrlib.is_valid(body.fnr):
            raise HTTPException(422, "Ugyldig fødselsnummer.")
        store.patient(body.fnr)
        if body.myndighetstype not in hjemler.BY_TYPE:
            raise HTTPException(422, "Velg type myndighet fra listen.")
        if not hjemler.allowed(body.myndighetstype, body.hjemmel):
            raise HTTPException(422, "Denne lovhjemmelen gjelder ikke for denne myndigheten.")
        if not set(body.data) <= set(CATEGORIES):
            raise HTTPException(422, "Ukjent datakategori.")
        with store.lock:
            requests = store.data["utleveringer"]
            entry = {"id": max((r["id"] for r in requests), default=0) + 1, "tid": now(),
                     **body.model_dump(), "status": "Til behandling"}
            requests.append(entry)
            store.save()
        return entry

    @app.post("/api/utlevering/{request_id}/vedtak")
    def decide(request_id: int, body: DecisionIn):
        with store.lock:
            request = next((r for r in store.data["utleveringer"] if r["id"] == request_id), None)
            if request is None:
                raise HTTPException(404, "Fant ikke forespørselen.")
            if request["status"] != "Til behandling":
                raise HTTPException(409, "Forespørselen er allerede behandlet.")
            if body.beslutning == "godkjent" and not body.varsle_pasient and not body.utsatt_varsling_hjemmel.strip():
                raise HTTPException(422, "Oppgi lovhjemmel for å utsette varsel til pasienten.")
            request.update({
                "status": "Godkjent" if body.beslutning == "godkjent" else "Avslått",
                "vedtak": {**body.model_dump(), "tid": now()},
            })
            if body.beslutning == "godkjent":
                p = store.patient(request["fnr"])
                request["utlevert"] = released_data(p, request)
                if body.varsle_pasient:
                    p["utleveringer"].append({
                        "tid": now(), "mottaker": request["myndighet"], "hjemmel": request["hjemmel"],
                        "formal": request["formal"], "data": request["data"],
                        "behandlet_av": body.behandlet_av,
                    })
            store.save()
        return request

    return app


def released_data(p: dict, request: dict) -> dict:
    """Only the categories that were approved, and only the requested period."""
    period = request.get("periode", "").strip()
    out = {}
    if "Kritisk informasjon" in request["data"]:
        c = critical(p)
        out["Kritisk informasjon"] = {k: c[k] for k in ("allergier", "tilstander", "implantater")}
    if "Legemidler" in request["data"]:
        out["Legemidler"] = [r for r in p["resepter"] if r["tid"].startswith(period)]
    if "Kontakter og notater" in request["data"]:
        out["Kontakter og notater"] = [k for k in p["kontakter"] if k["tid"].startswith(period)]
    return out


def make_app() -> FastAPI:
    return create_app(Path(os.getenv("MEDICUS_SIM_STATE", "data/helsenett-sim.json")))
