"""DIPS Arena, the journal system at most Norwegian hospitals, over its FHIR R4 interface.

What Medicus does with it:
    my_patients(actor)   today's patients for this doctor (Encounters where the doctor takes part)
    find_patient(fnr)    the patient, found by fødselsnummer
    save_note(...)       the approved note, saved as a DocumentReference

The code speaks standard FHIR R4. Before it is used against a real DIPS, the health trust and DIPS
must confirm which searches their installation supports and give Medicus a HelseID client with
access. Until then `token` raises IkkeTilkoblet with that explanation.
"""

from datetime import date

import httpx

from helsenett.client import HelsenettError

from . import fhir

NAME = "DIPS Arena"


class DipsClient:
    name = NAME

    def __init__(self, url: str, token, http: httpx.Client | None = None):
        self.token = token  # a function that returns an access token (see epj.token)
        self.http = http or httpx.Client(base_url=url.rstrip("/"), timeout=15)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.token()}", "Accept": "application/fhir+json"}
        if "json" in kwargs:
            headers["Content-Type"] = "application/fhir+json"
        try:
            response = self.http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as e:
            raise HelsenettError(f"Får ikke kontakt med {NAME}.") from e
        if response.status_code in (401, 403):
            raise HelsenettError(f"{NAME} avviste tilgangen. Kontakt IT.")
        if response.status_code >= 400:
            raise HelsenettError(f"{NAME} svarte med feil ({response.status_code}).")
        return response.json() if response.content else {}

    def _patient(self, fnr: str) -> dict:
        bundle = self._call("GET", "/Patient", params={"identifier": f"{fhir.FNR}|{fnr}"})
        found = fhir.resources(bundle, "Patient")
        if not found:
            raise HelsenettError(f"Fant ikke pasienten i {NAME}.")
        return found[0]

    def find_patient(self, fnr: str) -> dict:
        return fhir.patient_summary(self._patient(fnr))

    def my_patients(self, actor: dict) -> list[dict]:
        bundle = self._call("GET", "/Encounter", params={
            "practitioner.identifier": f"{fhir.HPR}|{actor['hpr']}",
            "date": f"ge{date.today().isoformat()}",
            "_include": "Encounter:subject",
            "_count": "100",
        })
        patients = [fhir.patient_summary(p) for p in fhir.resources(bundle, "Patient")]
        return [p for p in patients if p["fnr"]]

    def save_note(self, fnr: str, actor: dict, title: str, text: str) -> dict:
        patient = self._patient(fnr)
        created = self._call("POST", "/DocumentReference", json=fhir.document(patient["id"], actor, title, text))
        return {"system": NAME, "id": created.get("id", "")}
