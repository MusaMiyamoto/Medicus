"""medicus-authd: the single source of truth for "who is logged in, and how".

Protocol: one JSON request per connection on a UNIX socket, one JSON reply.
The caller's user id comes from the kernel (SO_PEERCRED), so it can't be faked.

    status          anyone        card in reader + active session
    cards           anyone        simulated cards (simulation mode only)
    insert/remove   anyone        simulated card reader (simulation mode only)
    login           root (PAM)    card + PIN → normal session
    emergency       root (PAM)    card + reason → 30-minute emergency session
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

from . import EMERGENCY_MINUTES, EMERGENCY_USER
from .cards import CardError, SimulatedReader

MAX_REQUEST = 8192


class Authority:
    """All decisions, without any socket code, so it can be tested directly."""

    def __init__(self, reader: SimulatedReader, audit: AuditLog, trusted_service_uids: set[int],
                 simulated: bool = True, clock=time.time):
        self.reader = reader
        self.audit = audit
        self.trusted = trusted_service_uids
        self.simulated = simulated
        self.clock = clock
        self.session: dict | None = None
        self.lock = threading.Lock()

    def _session(self) -> dict | None:
        s = self.session
        if s and s.get("utloper") and self.clock() > s["utloper"]:
            self.audit.record(s["hpr"], "emergency_expired", {"user": s["username"]})
            self.session = None
        return self.session

    def handle(self, request: dict, uid: int) -> dict:
        with self.lock:
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
        return {"kort": card.public() if card else None, "okt": public, "simulert": self.simulated}

    def cmd_cards(self, _req, _uid):
        self._require_sim()
        return {"kort": self.reader.list_cards()}

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
        # Taking the card out ends a normal session. Emergency sessions run until they expire.
        if self.session and self.session["modus"] == "normal":
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
        if not (self.session and self.session["username"] == card.username and self.session["modus"] == "normal"):
            self.session = self._new_session(card, "normal", None)
            self.audit.record(card.hpr, "login", {"user": card.username})
        else:
            self.audit.record(card.hpr, "unlock", {"user": card.username})

    def cmd_emergency(self, req, uid):
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None:
            raise CardError("Nødtilgang krever helsepersonellkort, slik at tilgangen kan spores.")
        if self.reader.is_blocked(card.card_id):
            raise CardError("Kortet er sperret.")
        reason = str(req.get("reason", "")).strip()
        if len(reason) < 5:
            raise CardError("Skriv en kort begrunnelse for nødtilgangen.")
        self.session = self._new_session(card, "nød", reason)
        self.audit.record(card.hpr, "emergency_start", {"user": card.username, "reason": reason})

    def _new_session(self, card, mode, reason) -> dict:
        start = self.clock()
        session = {**card.public(), "modus": mode, "startet": datetime.fromtimestamp(start).isoformat(timespec="seconds")}
        session["linux_bruker"] = EMERGENCY_USER if mode == "nød" else card.username
        if mode == "nød":
            session["begrunnelse"] = reason
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
        simulated=True,
    )
    serve(authority, os.getenv("MEDICUS_AUTH_SOCKET", SOCKET))


if __name__ == "__main__":
    main()
