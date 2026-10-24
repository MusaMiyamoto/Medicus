"""Small FHIR R4 helpers shared by the DIPS and Epic code. Plain dicts, no FHIR library.

Norwegian identifiers in FHIR are written as "system|value", where the system is the OID below.
"""

import base64
from datetime import datetime

FNR = "urn:oid:2.16.578.1.12.4.1.4.1"   # fødselsnummer
DNR = "urn:oid:2.16.578.1.12.4.1.4.2"   # D-nummer
HPR = "urn:oid:2.16.578.1.12.4.1.4.4"   # HPR-nummer (health personnel)

GENDER = {"male": "Mann", "female": "Kvinne", "other": "Annet", "unknown": "Ukjent"}


def text_of(concept: dict | None) -> str:
    """A CodeableConcept as plain text: its text, or the first coding's display or code."""
    if not concept:
        return ""
    if concept.get("text"):
        return concept["text"]
    for coding in concept.get("coding", []):
        if coding.get("display") or coding.get("code"):
            return coding.get("display") or coding["code"]
    return ""


def code_of(concept: dict | None) -> str:
    for coding in (concept or {}).get("coding", []):
        if coding.get("code"):
            return coding["code"]
    return ""


def name_of(patient: dict) -> str:
    for name in patient.get("name", []):
        if name.get("text"):
            return name["text"]
        full = " ".join([*name.get("given", []), name.get("family", "")]).strip()
        if full:
            return full
    return ""


def fnr_of(patient: dict) -> str:
    """The fødselsnummer (or D-nummer) of a FHIR Patient, or "" if it has none."""
    for system in (FNR, DNR):
        for identifier in patient.get("identifier", []):
            if identifier.get("system") == system and identifier.get("value"):
                return str(identifier["value"])
    return ""


def patient_summary(patient: dict) -> dict:
    """A FHIR Patient in the same shape as the rest of Medicus uses."""
    return {"fnr": fnr_of(patient), "navn": name_of(patient), "fodt": patient.get("birthDate", ""),
            "kjonn": GENDER.get(patient.get("gender", ""), "")}


def resources(bundle: dict, kind: str | None = None) -> list[dict]:
    entries = [e.get("resource") or {} for e in bundle.get("entry", [])]
    return [r for r in entries if kind is None or r.get("resourceType") == kind]


def document(patient_id: str, author: dict, title: str, text: str, now: datetime | None = None) -> dict:
    """An approved journal note as a FHIR DocumentReference with the text inline."""
    when = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    return {
        "resourceType": "DocumentReference",
        "status": "current",
        "docStatus": "final",
        "type": {"coding": [{"system": "http://loinc.org", "code": "11506-3", "display": "Progress note"}],
                 "text": title},
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": when,
        "author": [{"identifier": {"system": HPR, "value": author["hpr"]}, "display": author["navn"]}],
        "description": title,
        "content": [{"attachment": {"contentType": "text/plain; charset=utf-8", "title": title, "creation": when,
                                    "data": base64.b64encode(text.encode("utf-8")).decode("ascii")}}],
    }
