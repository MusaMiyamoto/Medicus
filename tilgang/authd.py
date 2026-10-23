"""medicus-authd: the single source of truth for "who is logged in, and how".

Protocol: one JSON request per connection on a UNIX socket, one JSON reply.
The caller's user id comes from the kernel (SO_PEERCRED), so it can't be faked.

    status          anyone        card in reader + active session
    cards           anyone        simulated cards (simulation mode only)
    insert/remove   anyone        simulated card reader (simulation mode only)
    login           root (PAM)    card + PIN → normal session (IT cards: IT session)
    emergency       root (PAM)    card + situation → 30-minute emergency session + a report to write
    report          the session's user or the Medicus service: write an emergency report
    verify          root (PAM)    IT card + PIN confirms an admin action (sudo)
    end             root, the session's user, or the Medicus service
"""

import json
import os
import pwd
import socket
import struct
import threading
import time
from datetime import datetime, timedelta

from medicus.audit import AuditLog

from . import EMERGENCY_MINUTES, EMERGENCY_USER, IT_ROLE, SITUATIONS
from .arbeidssted import UNKNOWN, Arbeidssted, load_sim_sites, position
from .arbeidssted import load as load_site
from .cards import CardError, SimulatedReader
from .nodrapport import Reports

MAX_REQUEST = 8192


class Authority:
    """All decisions, without any socket code, so it can be tested directly."""

    def __init__(self, reader: SimulatedReader, audit: AuditLog, trusted_service_uids: set[int],
                 simulated: bool = True, clock=time.time, site: Arbeidssted = UNKNOWN,
                 sim_sites: list[Arbeidssted] = (), reports: Reports | None = None):
        self.reader = reader
        self.audit = audit
        self.trusted = trusted_service_uids
        self.simulated = simulated
        self.clock = clock
        self.site = site
        self.sim_sites = list(sim_sites)
        self.session: dict | None = None
        self.reports = reports or Reports(None, clock)
        self.lock = threading.Lock()

    def _session(self) -> dict | None:
        s = self.session
        if s and s.get("utloper") and self.clock() > s["utloper"]:
            self.audit.record(s["hpr"], "emergency_expired", {"user": s["username"]})
            self.session = None
        return self.session

    def _flag_late_reports(self):
        for item in self.reports.newly_overdue():
            self.audit.record(item["hpr"], "emergency_report_overdue", {"report": item["id"]})

    def handle(self, request: dict, uid: int) -> dict:
        with self.lock:
            self._flag_late_reports()
            command = request.get("cmd")
            handler = getattr(self, f"cmd_{command}", None)
            if handler is None:
                return {"ok": False, "error": "Ukjent kommando."}
            try:
                return {"ok": True, **(handler(request, uid) or {})}
            except PermissionError as e:
                return {"ok": False, "error": str(e) or "Ikke tillatt."}
            except CardError as e:
                return {"ok": False, "error": str(e)}

    def _require_root(self, uid):
        if uid != 0:
            raise PermissionError("Bare innloggingssystemet kan gjøre dette.")

    def _require_sim(self):
        if not self.simulated:
            raise PermissionError("Simulert kortleser er slått av.")

    def cmd_status(self, _req, _uid):
        card = self.reader.inserted()
        session = self._session()
        public = None
        if session:
            public = {k: v for k, v in session.items() if k != "uid"}
            if session.get("utloper"):
                public["sekunder_igjen"] = max(0, int(session["utloper"] - self.clock()))
            public["rapporter"] = self.reports.missing(session["hpr"])
        reply = {"kort": card.public() if card else None, "okt": public, "simulert": self.simulated,
                 "arbeidssted": self.site.public()}
        if card:
            reply["kort"]["stilling"] = position(card.stillinger, card.rolle, self.site)
            reply["kort"]["sperret"] = self.reader.is_blocked(card.card_id)
            reply["kort"]["rapporter"] = self.reports.missing(card.hpr)
        if self.simulated:
            reply["arbeidssteder"] = [s.public() for s in self.sim_sites]
        return reply

    def cmd_cards(self, _req, _uid):
        self._require_sim()
        return {"kort": self.reader.list_cards()}

    def cmd_set_site(self, req, _uid):
        """Demo only: pretend this PC stands somewhere else. Not while someone is logged in."""
        self._require_sim()
        if self._session():
            raise PermissionError("Logg ut før du bytter arbeidssted.")
        site = next((s for s in self.sim_sites if s.id == req.get("site_id")), None)
        if site is None:
            raise CardError("Ukjent arbeidssted.")
        self.site = site

    def cmd_insert(self, req, _uid):
        self._require_sim()
        self.reader.insert(str(req.get("card_id", "")))
        card = self.reader.inserted()
        self.audit.record(card.hpr, "card_inserted", {"user": card.username})

    def cmd_remove(self, _req, _uid):
        self._require_sim()
        card = self.reader.inserted()
        self.reader.remove()
        if card:
            self.audit.record(card.hpr, "card_removed", {"user": card.username})
        # Taking the card out ends a normal or IT session. Emergency sessions run until they expire.
        if self.session and self.session["modus"] in ("normal", "it"):
            self.audit.record(self.session["hpr"], "session_ended", {"reason": "card_removed"})
            self.session = None

    def cmd_login(self, req, uid):
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None:
            raise CardError("Sett inn helsepersonellkortet ditt.")
        if card.username != req.get("username"):
            raise CardError("Kortet tilhører en annen bruker.")
        if not self.reader.verify_pin(str(req.get("pin", ""))):
            self.audit.record(card.hpr, "login_failed", {"user": card.username})
            raise CardError(f"Feil PIN. {self.reader.tries_left()} forsøk igjen.")
        mode = "it" if card.rolle == IT_ROLE else "normal"
        if not (self.session and self.session["username"] == card.username and self.session["modus"] == mode):
            self.session = self._new_session(card, mode, None)
            self.audit.record(card.hpr, "login", {"user": card.username, "mode": mode})
        else:
            self.audit.record(card.hpr, "unlock", {"user": card.username})

    def cmd_verify(self, req, uid):
        """An IT person confirms an admin action (sudo) with the card PIN. Logged every time."""
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None or card.username != req.get("username"):
            raise CardError("Sett inn IT-kortet ditt.")
        if card.rolle != IT_ROLE:
            raise PermissionError("Bare IT-personell kan gjøre endringer på systemet.")
        if not self.reader.verify_pin(str(req.get("pin", ""))):
            self.audit.record(card.hpr, "admin_failed", {"user": card.username})
            raise CardError(f"Feil PIN. {self.reader.tries_left()} forsøk igjen.")
        self.audit.record(card.hpr, "admin_confirmed", {"user": card.username, "command": str(req.get("command", ""))[:200]})

    def cmd_emergency(self, req, uid):
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None:
            raise CardError("Nødtilgang krever helsepersonellkort, slik at tilgangen kan spores.")
        if card.rolle == IT_ROLE:
            raise PermissionError("Nødtilgang er bare for helsepersonell.")
        if self.reader.is_blocked(card.card_id):
            raise CardError("Kortet er sperret.")
        # No questions first: in an emergency every second counts. The why comes afterwards.
        situation = str(req.get("situasjon", ""))
        if situation not in SITUATIONS:
            situation = "Ikke oppgitt"
        report = self.reports.open(card.hpr, card.navn, situation)
        self.session = self._new_session(card, "nød", report["id"])
        self.session["situasjon"] = situation
        self.audit.record(card.hpr, "emergency_start",
                          {"user": card.username, "situasjon": situation, "report": report["id"]})

    def cmd_report(self, req, uid):
        """Write the report for an emergency access. Only the person who opened it can."""
        session = self._session()
        if session is None:
            raise PermissionError("Du er ikke logget inn.")
        if not (uid in self.trusted or _uid_of(session["linux_bruker"]) == uid):
            raise PermissionError("Ikke tillatt.")
        try:
            item = self.reports.write(str(req.get("id", "")), session["hpr"], str(req.get("tekst", "")))
        except (ValueError, LookupError) as e:
            raise CardError(str(e)) from e
        self.audit.record(session["hpr"], "emergency_report_written",
                          {"report": item["id"], "tekst": str(req.get("tekst", "")).strip()[:5000]})
        return {"rapport": item}

    def cmd_overdue(self, _req, uid):
        """Late emergency reports, for the Sikkerhetssenter (IT mode)."""
        if not (uid == 0 or uid in self.trusted):
            raise PermissionError("Ikke tillatt.")
        return {"rapporter": self.reports.overdue()}

    def _new_session(self, card, mode, report_id) -> dict:
        start = self.clock()
        person = {k: v for k, v in card.public().items() if k != "stillinger"}
        session = {**person, "modus": mode, "startet": datetime.fromtimestamp(start).isoformat(timespec="seconds"),
                   # Where the person is working right now: this PC's workplace.
                   "virksomhet": self.site.navn, "arbeidssted_id": self.site.id,
                   "stilling": position(card.stillinger, card.rolle, self.site)}
        session["linux_bruker"] = EMERGENCY_USER if mode == "nød" else card.username
        if mode == "nød":
            session["rapport_id"] = report_id
            session["utloper"] = start + timedelta(minutes=EMERGENCY_MINUTES).total_seconds()
        return session

    def cmd_end(self, _req, uid):
        session = self._session()
        if session is None:
            return
        allowed = uid == 0 or uid in self.trusted or _uid_of(session["linux_bruker"]) == uid
        if not allowed:
            raise PermissionError("Ikke tillatt.")
        self.audit.record(session["hpr"], "session_ended", {"reason": "logout", "mode": session["modus"]})
        self.session = None


def _uid_of(username: str) -> int | None:
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return None


def peer_uid(conn: socket.socket) -> int:
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", creds)[1]


def serve(authority: Authority, path: str):
    if os.path.exists(path):
        os.remove(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    os.chmod(path, 0o666)  # anyone may ask; what they may *do* is checked per command
    server.listen(16)
    while True:
        conn, _ = server.accept()
        threading.Thread(target=_handle, args=(authority, conn), daemon=True).start()


def _handle(authority: Authority, conn: socket.socket):
    with conn:
        conn.settimeout(5)
        try:
            data = b""
            while not data.endswith(b"\n") and len(data) < MAX_REQUEST:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                data += chunk
            request = json.loads(data or b"{}")
            reply = authority.handle(request if isinstance(request, dict) else {}, peer_uid(conn))
        except (json.JSONDecodeError, socket.timeout, UnicodeDecodeError):
            reply = {"ok": False, "error": "Ugyldig forespørsel."}
        conn.sendall(json.dumps(reply, ensure_ascii=False).encode() + b"\n")


def main():
    from pathlib import Path

    from . import SOCKET

    state = Path(os.getenv("STATE_DIRECTORY", "/var/lib/medicus-auth"))
    trusted = {_uid_of(name) for name in ("medicus",)} - {None}
    authority = Authority(
        SimulatedReader(Path("/etc/medicus/simkort.json"), state / "pin-forsok.json"),
        AuditLog(state / "audit.jsonl"),
        trusted_service_uids=trusted,
        reports=Reports(state / "nodrapporter.json", time.time),
        simulated=True,
        site=load_site(),
        sim_sites=load_sim_sites(),
    )
    serve(authority, os.getenv("MEDICUS_AUTH_SOCKET", SOCKET))


if __name__ == "__main__":
    main()
