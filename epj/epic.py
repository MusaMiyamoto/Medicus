"""Moving a patient's record from Epic into Medicus.

Epic exports a patient as FHIR R4 (a Bundle file, or its FHIR API). Medicus reads:

    Patient                                  who it is (must have a fødselsnummer or D-nummer)
    AllergyIntolerance                       allergies
    Condition                                diagnoses / problems
    MedicationRequest, MedicationStatement   medicines
    DocumentReference                        notes and discharge letters (text only)

`read_bundle` turns the Bundle into a preview the clinician checks. `journal_notes` turns it into
journal notes. Allergies and medicines are imported as text marked "must be checked": Medicus never
puts them into the patient's critical information (kjernejournal) without a clinician doing it.
"""

import base64
import binascii

import httpx

from helsenett import fnr as fnrlib
from helsenett.client import HelsenettError

from . import fhir

NAME = "Epic"
MAX_ENTRIES = 5000
TEXT_TYPES = ("text/plain", "text/html", "text/markdown")

CRITICALITY = {"high": "Høy", "low": "Lav", "unable-to-assess": "Ukjent"}
CLINICAL_STATUS = {"active": "Aktiv", "recurrence": "Aktiv", "relapse": "Aktiv", "inactive": "Inaktiv",
                   "remission": "I remisjon", "resolved": "Avsluttet"}
MED_STATUS = {"active": "Aktiv", "completed": "Avsluttet", "stopped": "Seponert", "on-hold": "Pause",
              "intended": "Planlagt", "cancelled": "Avbrutt"}


class TransferError(HelsenettError):
    pass


def _not_in_error(resource: dict) -> bool:
    status = resource.get("status") or fhir.code_of(resource.get("verificationStatus"))
    return status not in ("entered-in-error", "refuted")


def _medicine_name(resource: dict, by_reference: dict) -> str:
    if resource.get("medicationCodeableConcept"):
        return fhir.text_of(resource["medicationCodeableConcept"])
    reference = resource.get("medicationReference", {})
    medication = by_reference.get(reference.get("reference", ""))
    return fhir.text_of(medication.get("code")) if medication else reference.get("display", "")


def _document_text(resource: dict, by_reference: dict) -> str | None:
    for content in resource.get("content", []):
        attachment = content.get("attachment", {})
        if not attachment.get("contentType", "text/plain").startswith(TEXT_TYPES):
            continue
        data = attachment.get("data")
        if data is None:  # the text is in a separate Binary resource in the same bundle
            data = by_reference.get(attachment.get("url", ""), {}).get("data")
        if data:
            try:
                return base64.b64decode(data).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                return None
    return None


def read_bundle(bundle: dict) -> dict:
    """Check an Epic FHIR Bundle and turn it into a preview. Raises TransferError if it can't be used."""
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise TransferError("Filen er ikke en FHIR-eksport (Bundle).")
    entries = bundle.get("entry", [])
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise TransferError("Eksporten er for stor eller ugyldig.")
    by_reference = {}
    for entry in entries:
        resource = (entry or {}).get("resource") or {}
        if resource.get("id"):
            by_reference[f"{resource.get('resourceType')}/{resource['id']}"] = resource
        if entry.get("fullUrl"):
            by_reference[entry["fullUrl"]] = resource

    patients = fhir.resources(bundle, "Patient")
    if len(patients) != 1:
        raise TransferError("Eksporten må gjelde nøyaktig én pasient.")
    patient = fhir.patient_summary(patients[0])
    if not fnrlib.is_valid(patient["fnr"]):
        raise TransferError("Pasienten i eksporten har ikke gyldig fødselsnummer eller D-nummer.")

    warnings = []
    allergies = [{"stoff": fhir.text_of(a.get("code")),
                  "reaksjon": ", ".join(fhir.text_of(m) for r in a.get("reaction", []) for m in r.get("manifestation", [])),
                  "alvorlighet": CRITICALITY.get(a.get("criticality", ""), "")}
                 for a in fhir.resources(bundle, "AllergyIntolerance") if _not_in_error(a)]
    conditions = [{"navn": fhir.text_of(c.get("code")),
                   "status": CLINICAL_STATUS.get(fhir.code_of(c.get("clinicalStatus")), ""),
                   "siden": str(c.get("onsetDateTime", ""))[:10]}
                  for c in fhir.resources(bundle, "Condition") if _not_in_error(c)]
    medicines = []
    for kind, dose_field in (("MedicationRequest", "dosageInstruction"), ("MedicationStatement", "dosage")):
        for m in fhir.resources(bundle, kind):
            if _not_in_error(m):
                medicines.append({"navn": _medicine_name(m, by_reference),
                                  "dosering": next((d.get("text", "") for d in m.get(dose_field, [])), ""),
                                  "status": MED_STATUS.get(m.get("status", ""), m.get("status", ""))})
    documents = []
    for d in fhir.resources(bundle, "DocumentReference"):
        if not _not_in_error(d):
            continue
        title = d.get("description") or fhir.text_of(d.get("type")) or "Dokument"
        text = _document_text(d, by_reference)
        if text is None:
            warnings.append(f"«{title}» er ikke tekst (for eksempel PDF eller bilde) og blir ikke overført.")
            continue
        documents.append({"tittel": title, "dato": str(d.get("date", ""))[:10],
                          "forfatter": ", ".join(a.get("display", "") for a in d.get("author", []) if a.get("display")),
                          "tekst": text.strip()})
    return {"kilde": NAME, "pasient": patient, "allergier": allergies, "tilstander": conditions,
            "legemidler": medicines, "dokumenter": documents, "advarsler": warnings}


def journal_notes(transfer: dict, actor: dict, today: str) -> list[tuple[str, str]]:
    """The transfer as journal notes: one summary, then one note per document. (title, text) pairs."""
    def lines(items, fmt):
        return "\n".join(f"- {fmt(i)}" for i in items) or "- Ingen registrert"

    source = transfer["kilde"]
    summary = "\n\n".join([
        f"Journalopplysninger overført fra {source} {today} av {actor['navn']} ({actor['rolle']}).",
        "ALLERGIER (må kontrolleres før de registreres som kritisk informasjon):\n" + lines(
            transfer["allergier"], lambda a: " – ".join(x for x in (a["stoff"], a["reaksjon"], a["alvorlighet"]) if x)),
        "DIAGNOSER / PROBLEMER:\n" + lines(
            transfer["tilstander"], lambda c: " – ".join(x for x in (c["navn"], c["status"], c["siden"] and f"fra {c['siden']}") if x)),
        f"LEGEMIDLER (slik de var registrert i {source}; avstem legemiddellisten):\n" + lines(
            transfer["legemidler"], lambda m: " – ".join(x for x in (m["navn"], m["dosering"], m["status"]) if x)),
    ])
    notes = [(f"Overført fra {source}: sammendrag", summary)]
    for d in transfer["dokumenter"]:
        header = " · ".join(x for x in (d["dato"], d["forfatter"]) if x)
        notes.append((f"Overført fra {source}: {d['tittel']}", f"{header}\n\n{d['tekst']}" if header else d["tekst"]))
    return notes


class EpicSource:
    """Fetch a patient straight from an Epic FHIR R4 server, as a Bundle for read_bundle."""

    KINDS = ("AllergyIntolerance", "Condition", "MedicationRequest", "DocumentReference")

    def __init__(self, url: str, token, http: httpx.Client | None = None):
        self.token = token
        self.http = http or httpx.Client(base_url=url.rstrip("/"), timeout=30)

    def _get(self, path: str, accept: str = "application/fhir+json", **params) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token()}", "Accept": accept}
        try:
            response = self.http.get(path, params=params, headers=headers)
        except httpx.HTTPError as e:
            raise HelsenettError(f"Får ikke kontakt med {NAME}.") from e
        if response.status_code >= 400:
            raise HelsenettError(f"{NAME} svarte med feil ({response.status_code}).")
        return response

    def _inline_texts(self, document: dict):
        """Epic keeps note text in a separate Binary. Fetch it, but only from this same server,
        so the access token is never sent anywhere else."""
        base = str(self.http.base_url).rstrip("/") + "/"
        for content in document.get("content", []):
            attachment = content.get("attachment", {})
            url = attachment.get("url", "")
            if attachment.get("data") or not attachment.get("contentType", "text/plain").startswith(TEXT_TYPES):
                continue
            if url.startswith(base):
                url = url[len(base):]
            if url.startswith("Binary/"):
                attachment["data"] = base64.b64encode(self._get(f"/{url}", accept="text/plain").content).decode()

    def bundle_for(self, fnr: str) -> dict:
        found = fhir.resources(self._get("/Patient", identifier=f"{fhir.FNR}|{fnr}").json(), "Patient")
        if not found:
            raise HelsenettError(f"Fant ikke pasienten i {NAME}.")
        patient = found[0]
        entries = [{"resource": patient}]
        for kind in self.KINDS:
            # Only one page: up to 200 of each. Enough for a summary; the rest stays in Epic.
            for resource in fhir.resources(self._get(f"/{kind}", patient=patient["id"], _count="200").json(), kind):
                if kind == "DocumentReference":
                    self._inline_texts(resource)
                entries.append({"resource": resource})
        return {"resourceType": "Bundle", "type": "collection", "entry": entries}
