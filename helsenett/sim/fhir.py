"""A tiny FHIR R4 server for the simulator, playing the part of a hospital journal system (DIPS).

Only what epj/dips.py uses: find a patient by fødselsnummer, the doctor's patients today, and
saving a note. Patient ids are simply the (synthetic) fødselsnummer.
"""

import base64
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from epj import fhir

from . import seed

GENDER = {v: k for k, v in fhir.GENDER.items()} | {"Jente": "female", "Gutt": "male"}


def patient_resource(p: dict) -> dict:
    return {"resourceType": "Patient", "id": p["fnr"],
            "identifier": [{"system": fhir.FNR, "value": p["fnr"]}],
            "name": [{"text": p["navn"]}], "birthDate": p["fodt"], "gender": GENDER.get(p["kjonn"], "unknown")}


def searchset(matches: list[dict], included: list[dict] = ()) -> dict:
    return {"resourceType": "Bundle", "type": "searchset", "total": len(matches),
            "entry": [{"resource": r, "search": {"mode": "match"}} for r in matches] +
                     [{"resource": r, "search": {"mode": "include"}} for r in included]}


def value_for(param: str, system: str) -> str:
    wanted_system, _, value = param.partition("|")
    return value if wanted_system == system else ""


def make_fhir_router(store, now) -> APIRouter:
    router = APIRouter(prefix="/fhir")

    @router.get("/Patient")
    def find_patient(identifier: str = ""):
        p = store.data["pasienter"].get(value_for(identifier, fhir.FNR))
        return searchset([patient_resource(p)] if p else [])

    @router.get("/Encounter")
    def todays_encounters(request: Request):
        hpr = value_for(request.query_params.get("practitioner.identifier", ""), fhir.HPR)
        mine = [p for p in store.data["pasienter"].values() if p["fastlege"]["hpr"] == hpr]
        today = date.today().isoformat()
        encounters = [{"resourceType": "Encounter", "id": f"time-{p['fnr']}", "status": "planned",
                       "subject": {"reference": f"Patient/{p['fnr']}"}, "period": {"start": today}} for p in mine]
        return searchset(encounters, [patient_resource(p) for p in mine])

    @router.post("/DocumentReference", status_code=201)
    async def save_document(request: Request):
        doc = await request.json()
        fnr = doc.get("subject", {}).get("reference", "").removeprefix("Patient/")
        try:
            text = base64.b64decode(doc["content"][0]["attachment"]["data"]).decode("utf-8")
            author = doc["author"][0]
        except (KeyError, IndexError, ValueError) as e:
            raise HTTPException(400, "Ugyldig DocumentReference.") from e
        with store.lock:
            entries = store.patient(fnr)["kontakter"]
            entries.append({"tid": now(), "virksomhet": seed.SYKEHUS,
                            "aktor": {"navn": author.get("display", ""), "rolle": "", "virksomhet": seed.SYKEHUS,
                                      "hpr": author.get("identifier", {}).get("value", "")},
                            "type": doc.get("description") or fhir.text_of(doc.get("type")), "notat": text})
            store.save()
        return JSONResponse({**doc, "id": f"doc-{len(entries)}"}, status_code=201)

    return router
