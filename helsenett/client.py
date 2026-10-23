"""One interface for every health-network service Medicus uses.

    HelsenettClient            what Medicus needs (the "contract")
    SimulatedClient            talks to the local simulator (helsenett.sim)
    NhnClient                  the slot for Norsk helsenett's real services

Each method notes which real national service it maps to.
"""

import json
from typing import Protocol

import httpx

from . import config


class HelsenettError(Exception):
    pass


class IkkeTilkoblet(HelsenettError):
    """Raised by NhnClient until an agreement and credentials are in place."""


class Actor(dict):
    """Who is acting: {"navn", "hpr", "rolle", "virksomhet"}. Comes from the card login."""


class HelsenettClient(Protocol):
    def find_patient(self, fnr: str) -> dict:
        """Folkeregisteret / FHIR Patient."""

    def list_patients(self) -> list[dict]:
        """Simulator only: the synthetic test patients, for demos."""

    def critical_info(self, fnr: str) -> dict:
        """Kjernejournal: kritisk informasjon, legemidler (PLL), implantater, pårørende."""

    def encounters(self, fnr: str) -> list[dict]:
        """Pasientens journaldokumenter: visits and notes from every institution."""

    def add_note(self, fnr: str, actor: Actor, kind: str, text: str) -> dict:
        """Share a journal note (dokumentdeling)."""

    def prescriptions(self, fnr: str) -> list[dict]:
        """e-resept / Reseptformidleren."""

    def prescribe(self, fnr: str, actor: Actor, drug: str, dose: str, reason: str) -> dict:
        """Send an e-prescription."""

    def log_access(self, fnr: str, actor: Actor, mode: str, reason: str, what: str) -> dict:
        """Helsenorge: the patient sees who opened their record (innsynslogg + varsel)."""

    # Medicus Post: messages and image sharing inside the health network.

    def directory(self) -> list[dict]:
        """Adresseregisteret: who you can send to."""

    def inbox(self, actor: Actor) -> list[dict]:
        """Received messages (dialogmeldinger), plus checked external email."""

    def sent(self, actor: Actor) -> list[dict]:
        """Messages you have sent."""

    def read_message(self, actor: Actor, message_id: int) -> dict:
        """One message with attachments and, for external email, the phishing assessment."""

    def send_message(self, actor: Actor, to: list[str], subject: str, text: str, fnr: str,
                     files: list[tuple[str, bytes, str]]) -> dict:
        """Send a message, optionally with images (DICOM) and linked to a patient."""

    def report_message(self, actor: Actor, message_id: int) -> dict:
        """Report a suspicious email to IT security."""

    def attachment(self, actor: Actor, file_id: str, preview: bool) -> tuple[bytes, str, str]:
        """An attachment (bytes, media type, file name), or a PNG preview of an image."""


class SimulatedClient:
    def __init__(self, url: str, http: httpx.Client | None = None):
        self.http = http or httpx.Client(base_url=url, timeout=10)

    def _call(self, method: str, path: str, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise HelsenettError("Får ikke kontakt med helsenettet (simulator).") from e
        if response.status_code == 404:
            raise HelsenettError("Fant ikke pasienten.")
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text) if response.content else ""
            raise HelsenettError(f"Helsenettet svarte med feil: {detail}")
        return response.json()

    def find_patient(self, fnr):
        return self._call("GET", f"/api/pasient/{fnr}")

    def list_patients(self):
        return self._call("GET", "/api/pasienter")

    def critical_info(self, fnr):
        return self._call("GET", f"/api/kjernejournal/{fnr}")

    def encounters(self, fnr):
        return self._call("GET", f"/api/journal/{fnr}")

    def add_note(self, fnr, actor, kind, text):
        return self._call("POST", f"/api/journal/{fnr}", json={"aktor": actor, "type": kind, "notat": text})

    def prescriptions(self, fnr):
        return self._call("GET", f"/api/resepter/{fnr}")

    def prescribe(self, fnr, actor, drug, dose, reason):
        return self._call(
            "POST", f"/api/resepter/{fnr}",
            json={"aktor": actor, "legemiddel": drug, "dosering": dose, "indikasjon": reason},
        )

    def log_access(self, fnr, actor, mode, reason, what):
        return self._call(
            "POST", f"/api/innsyn/{fnr}",
            json={"aktor": actor, "modus": mode, "begrunnelse": reason, "hva": what},
        )

    @staticmethod
    def _as(actor):
        return {"X-Medicus-HPR": actor["hpr"]}

    def directory(self):
        return self._call("GET", "/api/post/adresser")

    def inbox(self, actor):
        return self._call("GET", "/api/post/innboks", headers=self._as(actor))

    def sent(self, actor):
        return self._call("GET", "/api/post/sendt", headers=self._as(actor))

    def read_message(self, actor, message_id):
        return self._call("GET", f"/api/post/{int(message_id)}", headers=self._as(actor))

    def send_message(self, actor, to, subject, text, fnr, files):
        data = {"aktor": json.dumps(actor), "til": to, "emne": subject, "tekst": text, "fnr": fnr}
        upload = [("filer", (name, content, kind)) for name, content, kind in files]
        return self._call("POST", "/api/post", data=data, files=upload or None)

    def report_message(self, actor, message_id):
        return self._call("POST", f"/api/post/{int(message_id)}/rapporter", headers=self._as(actor))

    def attachment(self, actor, file_id, preview):
        if not file_id.isalnum():
            raise HelsenettError("Ugyldig vedlegg.")
        path = f"/api/post/vedlegg/{file_id}" + ("/visning" if preview else "")
        try:
            response = self.http.get(path, headers=self._as(actor))
        except httpx.HTTPError as e:
            raise HelsenettError("Får ikke kontakt med helsenettet (simulator).") from e
        if response.status_code >= 400:
            raise HelsenettError(response.json().get("detail", "Kunne ikke hente vedlegget."))
        disposition = response.headers.get("content-disposition", "")
        name = disposition.split('filename="')[-1].rstrip('"') if "filename=" in disposition else "vedlegg"
        return response.content, response.headers.get("content-type", "application/octet-stream"), name


class NhnClient:
    """Placeholder for the real services. Every call explains what is still missing.

    When an agreement exists, each method is implemented against the service named in
    HelsenettClient, authenticating with a HelseID access token (client credentials with
    private_key_jwt, issued to this Medicus installation).
    """

    MISSING = (
        "Medicus er ikke koblet til Norsk helsenett ennå. Det krever medlemskap i helsenettet, "
        "registrert HelseID-klient og godkjenning for {service}. Se docs/helsenorge-integrasjon.md."
    )

    SERVICES = {
        "find_patient": "Folkeregisteret (via NHN)",
        "list_patients": "testpasienter (finnes bare i simulator)",
        "critical_info": "Kjernejournal",
        "encounters": "pasientens journaldokumenter",
        "add_note": "dokumentdeling",
        "prescriptions": "e-resept",
        "prescribe": "e-resept",
        "log_access": "Helsenorge innsynslogg",
        "directory": "Adresseregisteret",
        "inbox": "meldingsutveksling i helsenettet",
        "sent": "meldingsutveksling i helsenettet",
        "read_message": "meldingsutveksling i helsenettet",
        "send_message": "meldingsutveksling og bildedeling i helsenettet",
        "report_message": "virksomhetens IT-sikkerhet",
        "attachment": "bildedeling",
    }

    def __init__(self, settings: dict):
        self.settings = settings

    def __getattr__(self, name):
        if name not in self.SERVICES:
            raise AttributeError(name)

        def not_connected(*_args, **_kwargs):
            raise IkkeTilkoblet(self.MISSING.format(service=self.SERVICES[name]))

        return not_connected


def get_client(settings: dict | None = None) -> HelsenettClient:
    settings = settings or config.load()
    mode = settings.get("modus", "simulert")
    if mode == "simulert":
        return SimulatedClient(settings["simulert"]["url"])
    if mode == "nhn":
        return NhnClient(settings.get("nhn", {}))
    raise HelsenettError(f"Ukjent modus i integrasjon.toml: {mode!r}")
