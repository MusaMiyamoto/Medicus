"""Emergency access reports.

Emergency access starts at once, without asking why. Afterwards the person who opened it
must write a short report: what happened and why the access was needed. The report is due
before the end of the shift (REPORT_HOURS after the access started). Reports that are late
are flagged for the security officer.

Stored as a small JSON file next to the PIN counters, so a restart doesn't forget them.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from . import REPORT_HOURS

MIN_LENGTH = 20  # a sentence or two, not "ok"


class Reports:
    def __init__(self, path: Path | None, clock):
        self.path = path
        self.clock = clock
        self.items: list[dict] = []
        if path and path.exists():
            self.items = json.loads(path.read_text(encoding="utf-8"))

    def _save(self):
        if self.path is None:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def open(self, hpr: str, navn: str, situasjon: str) -> dict:
        start = self.clock()
        item = {"id": uuid.uuid4().hex[:12], "hpr": hpr, "navn": navn, "situasjon": situasjon,
                "startet": start, "frist": start + REPORT_HOURS * 3600,
                "rapport": None, "skrevet": None, "varslet": False}
        self.items.append(item)
        self._save()
        return item

    def missing(self, hpr: str) -> list[dict]:
        """Reports this person still has to write, oldest first."""
        return [self.public(i) for i in self.items if i["hpr"] == hpr and i["rapport"] is None]

    def write(self, report_id: str, hpr: str, text: str) -> dict:
        text = text.strip()
        if len(text) < MIN_LENGTH:
            raise ValueError("Skriv litt mer: hva skjedde, og hvorfor trengtes nødtilgang?")
        for item in self.items:
            if item["id"] == report_id and item["hpr"] == hpr and item["rapport"] is None:
                item["rapport"] = text[:5000]
                item["skrevet"] = self.clock()
                self._save()
                return self.public(item)
        raise LookupError("Fant ingen åpen rapport.")

    def newly_overdue(self) -> list[dict]:
        """Late reports nobody has been told about yet. Each one is returned only once."""
        late = [i for i in self.items if i["rapport"] is None and not i["varslet"] and self.clock() > i["frist"]]
        for item in late:
            item["varslet"] = True
        if late:
            self._save()
        return late

    def overdue(self) -> list[dict]:
        return [self.public(i) for i in self.items if i["rapport"] is None and self.clock() > i["frist"]]

    def public(self, item: dict) -> dict:
        stamp = lambda t: datetime.fromtimestamp(t).isoformat(timespec="minutes")  # noqa: E731
        return {"id": item["id"], "navn": item["navn"], "situasjon": item["situasjon"], "startet": stamp(item["startet"]),
                "frist": stamp(item["frist"]), "forsinket": item["rapport"] is None and self.clock() > item["frist"]}


def open_if_missing() -> int:
    """At login: open the report page if this person still owes an emergency report."""
    import subprocess

    from .client import AuthError, call

    try:
        session = call("status")["okt"]
    except AuthError:
        return 0
    if session and session["modus"] == "normal" and session.get("rapporter"):
        subprocess.Popen(["medicus-nettleser", "http://127.0.0.1:8000/rapport"])
    return 0
