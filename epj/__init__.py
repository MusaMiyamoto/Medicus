"""The journal system (EPJ) where approved notes are saved and the doctor's patient list comes from.

    HelsenettJournal   the default: notes are shared through the health network (or its simulator)
    DipsClient         DIPS Arena over FHIR R4 (epj/dips.py)

Every journal has the same three methods: my_patients(actor), find_patient(fnr) and
save_note(fnr, actor, title, text). Which one is used is set in /etc/medicus/integrasjon.toml:

    [journal]
    system = "helsenett"   # or "dips"

Moving a patient's record *from* Epic is in epj/epic.py.
"""

from helsenett import config
from helsenett.client import HelsenettError, get_client

from . import token
from .dips import DipsClient


class HelsenettJournal:
    def __init__(self, client):
        self.client = client
        self.name = "Helsenett (simulert)" if type(client).__name__ == "SimulatedClient" else "Helsenett"

    def my_patients(self, actor):
        return self.client.my_patients(actor)

    def find_patient(self, fnr):
        return self.client.find_patient(fnr)

    def save_note(self, fnr, actor, title, text):
        self.client.add_note(fnr, actor, title, text)
        return {"system": self.name, "id": ""}


def get_journal(settings: dict | None = None):
    settings = settings or config.load()
    system = settings.get("journal", {}).get("system", "helsenett")
    if system == "helsenett":
        return HelsenettJournal(get_client(settings))
    if system == "dips":
        dips = settings.get("dips", {})
        return DipsClient(dips.get("fhir_url") or "http://dips.invalid", token.from_file(dips.get("token_fil", ""), "DIPS"))
    raise HelsenettError(f"Ukjent journalsystem i integrasjon.toml: {system!r}")
