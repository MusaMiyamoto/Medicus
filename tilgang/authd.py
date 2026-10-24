"""medicus-authd: the single source of truth for "who is logged in, and how".

Protocol: one JSON request per connection on a UNIX socket, one JSON reply.
The caller's user id comes from the kernel (SO_PEERCRED), so it can't be faked.

    status          anyone        card in reader + active session
    cards           anyone        simulated cards (simulation mode only)
    insert/remove   anyone        simulated card reader (simulation mode only)
    login           root (PAM)    card + PIN → normal session (IT cards: IT session)
    unlock          the session's user (lock screen): own card + PIN. Also resumes a session held
                    after the card was taken out (HOLD_MINUTES).
    tap             root (medicus-oktvakt) or the session's user: own card back in, no PIN, resumes a
                    held normal session if this PC allows it (kort_uten_pin_minutter) and the PIN is recent
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
from datetime import date, datetime, timedelta

from medicus.audit import AuditLog

from . import EMERGENCY_MINUTES, EMERGENCY_USER, HOLD_MINUTES, IT_ROLE, SITUATIONS, nett
from .arbeidssted import MISMATCH, UNKNOWN, Arbeidssted, certificate_site, confirmation, load_sim_sites, position
from .arbeidssted import load as load_site
from .cards import REVOKE_REASONS, CardError, SimulatedReader
from .nodrapport import Reports

MAX_REQUEST = 8192


class Authority:
    """All decisions, without any socket code, so it can be tested directly."""

    def __init__(self, reader: SimulatedReader, audit: AuditLog, trusted_service_uids: set[int],
                 simulated: bool = True, clock=time.time, site: Arbeidssted = UNKNOWN,
                 sim_sites: list[Arbeidssted] = (), reports: Reports | None = None, network=nett.read,
                 signed_site=lambda: None):
        self.reader = reader
        self.audit = audit
        self.trusted = trusted_service_uids
        self.simulated = simulated
        self.clock = clock
        self.site = site
        self.sim_sites = list(sim_sites)
        self.session: dict | None = None
        self.reports = reports or Reports(None, clock)
        self.network = network
        self.signed_site = signed_site  # the workplace in the machine certificate (arbeidssted.certificate_site)
        self.lock = threading.Lock()

    def _site_confirmation(self) -> str:
        return confirmation(self.site.id, self.signed_site())

    def _require_signed_site(self, card, action):
        """The workplace in arbeidssted.toml must be the one IT's CA signed into the machine certificate.
        Otherwise notes and access logs would name the wrong hospital."""
        if self._site_confirmation() == MISMATCH:
            self.audit.record(card.hpr, f"{action}_refused_site", {"user": card.username, "site": self.site.id})
            raise PermissionError("Arbeidsstedet på denne PC-en stemmer ikke med maskinsertifikatet, så "
                                  "pasientjournaler er stengt. Nødtilgang virker fortsatt. Kontakt IT.")

    def _on_clinical_network(self) -> bool:
        """Read by authd itself, never taken from the caller."""
        return nett.on_clinical_network(self.network(), self.site.nett, self.site.mobile) if self.site.nett else True

    def _require_clinical_network(self, card, action):
        if not self._on_clinical_network():
            self.audit.record(card.hpr, f"{action}_refused_network", {"user": card.username})
            if self.site.mobile:
                raise PermissionError("PC-en er ikke koblet til helsenettet med VPN, så pasientjournaler er stengt. "
                                      "Koble til mobilnett eller Wi-Fi, og vent til VPN-en er på. Nødtilgang virker "
                                      "fortsatt. Kontakt IT hvis det ikke går.")
            raise PermissionError("PC-en er ikke koblet til sykehusets kliniske nett, så pasientjournaler er stengt. "
                                  "Nødtilgang virker fortsatt. Kontakt IT.")

    def _session(self) -> dict | None:
        s = self.session
        if s and s.get("utloper") and self.clock() > s["utloper"]:
            self.audit.record(s["hpr"], "emergency_expired", {"user": s["username"]})
            self.session = None
        elif s and s.get("holdt_til") and self.clock() > s["holdt_til"]:
            self.audit.record(s["hpr"], "session_ended", {"reason": "card_not_returned", "mode": s["modus"]})
            self.session = None
        return self.session

    def _release(self, card, pin=True):
        """The same card (and PIN) came back: the held session continues where it was."""
        held = self.session.pop("holdt_til")
        details = {"user": card.username, "held_seconds": int(self.clock() - (held - HOLD_MINUTES * 60))}
        if pin:
            self.session["pin_tid"] = self.clock()
        else:
            details["uten_pin"] = True
        self.audit.record(card.hpr, "session_resumed", details)

    def _check_card(self, card, action, emergency=False):
        """A lost or stolen card is refused everywhere: someone else may be holding it. An expired card is
        refused for normal use, but still opens emergency access (the person is known; lives first)."""
        reason = self.reader.revoked_reason(card.card_id)
        if reason:
            self.audit.record(card.hpr, "revoked_card_used", {"card": card.card_id, "grunn": reason, "action": action})
            raise CardError(f"Dette kortet er {REVOKE_REASONS[reason]} og virker ikke lenger. Kontakt IT.")
        if card.expired(date.fromtimestamp(self.clock())):
            if not emergency:
                self.audit.record(card.hpr, f"{action}_refused_expired", {"user": card.username})
                raise CardError(f"Kortet gikk ut {card.gyldig_til}. Hent nytt kort. Nødtilgang virker fortsatt.")
            return {"utlopt_kort": True}
        return {}

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
            if session.get("holdt_til"):
                public["holdt_sekunder_igjen"] = max(0, int(session["holdt_til"] - self.clock()))
            public["rapporter"] = self.reports.missing(session["hpr"])
        reply = {"kort": card.public() if card else None, "okt": public, "simulert": self.simulated,
                 "arbeidssted": {**self.site.public(), "bekreftet": self._site_confirmation()}}
        if card:
            reply["kort"]["stilling"] = position(card.stillinger, card.rolle, self.site)
            reply["kort"]["sperret"] = self.reader.is_blocked(card.card_id)
            reply["kort"]["tilbakekalt"] = self.reader.revoked_reason(card.card_id)
            reply["kort"]["utlopt"] = card.expired(date.fromtimestamp(self.clock()))
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
        # Taking the card out locks a normal or IT session and holds it for HOLD_MINUTES, so open work
        # isn't lost. Nothing can use it meanwhile. Emergency sessions run until they expire.
        session = self._session()
        if session and session["modus"] in ("normal", "it") and not session.get("holdt_til"):
            session["holdt_til"] = self.clock() + HOLD_MINUTES * 60
            self.audit.record(session["hpr"], "session_held", {"user": session["username"], "minutes": HOLD_MINUTES})

    def cmd_login(self, req, uid):
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None:
            raise CardError("Sett inn helsepersonellkortet ditt.")
        if card.username != req.get("username"):
            raise CardError("Kortet tilhører en annen bruker.")
        self._check_card(card, "login")
        if not self.reader.verify_pin(str(req.get("pin", ""))):
            self.audit.record(card.hpr, "login_failed", {"user": card.username})
            raise CardError(f"Feil PIN. {self.reader.tries_left()} forsøk igjen.")
        mode = "it" if card.rolle == IT_ROLE else "normal"
        # Patient records only on the clinical network. IT mode has no patient data, and IT must be
        # able to log in to repair the network, so it is allowed elsewhere but marked.
        if mode == "normal":
            self._require_signed_site(card, "login")
            self._require_clinical_network(card, "login")
        current = self._session()
        if not (current and current["username"] == card.username and current["modus"] == mode):
            if current and current.get("holdt_til"):
                # Someone else logs in on this PC: the held session is given up (its desktop is closed).
                self.audit.record(current["hpr"], "session_ended",
                                  {"reason": "other_user_logged_in", "mode": current["modus"], "by": card.hpr})
            self.session = self._new_session(card, mode, None)
            details = {"user": card.username, "mode": mode}
            if not self._on_clinical_network():
                details["utenfor_klinisk_nett"] = True
            self.audit.record(card.hpr, "login", details)
        elif current.get("holdt_til"):
            self._release(card)
        else:
            current["pin_tid"] = self.clock()
            self.audit.record(card.hpr, "unlock", {"user": card.username})

    def cmd_unlock(self, req, uid):
        """Unlock the locked screen. The lock screen runs as the user, not root, so the user may
        ask, but only for their own running session and only with their own card and PIN."""
        session = self._session()
        if session is None or session["modus"] not in ("normal", "it"):
            raise PermissionError("Ingen økt å låse opp. Logg inn på nytt.")
        if not (uid == 0 or _uid_of(session["linux_bruker"]) == uid):
            raise PermissionError("Ikke tillatt.")
        card = self.reader.inserted()
        if card is None or card.username != session["username"] or req.get("username") != card.username:
            raise CardError("Sett inn kortet ditt.")
        self._check_card(card, "unlock")
        if not self.reader.verify_pin(str(req.get("pin", ""))):
            self.audit.record(card.hpr, "unlock_failed", {"user": card.username})
            raise CardError(f"Feil PIN. {self.reader.tries_left()} forsøk igjen.")
        if session["modus"] == "normal":
            self._require_signed_site(card, "unlock")
            self._require_clinical_network(card, "unlock")  # a laptop carried off the ward stays locked
        if session.get("holdt_til"):
            self._release(card)
        else:
            session["pin_tid"] = self.clock()
            self.audit.record(card.hpr, "unlock", {"user": card.username})

    def cmd_tap(self, _req, uid):
        """Tap-in: the card that was taken out goes back in, and the held session resumes without the PIN.
        Only if IT allows it on this PC, only within kort_uten_pin_minutter of the last PIN, only normal
        mode (IT mode has admin rights), and only a held session: a screen locked while the card stayed
        in the reader still needs the PIN, so a forgotten card doesn't open the PC for the next person."""
        session = self._session()
        if session is None or not session.get("holdt_til"):
            raise PermissionError("Ingen økt venter på kortet.")
        if not (uid == 0 or _uid_of(session["linux_bruker"]) == uid):
            raise PermissionError("Ikke tillatt.")
        card = self.reader.inserted()
        if card is None or card.username != session["username"]:
            raise CardError("Sett inn kortet ditt.")
        self._check_card(card, "unlock")
        limit = self.site.kort_uten_pin_minutter
        if (session["modus"] != "normal" or limit <= 0 or self.reader.is_blocked(card.card_id)
                or self.clock() - session.get("pin_tid", 0) > limit * 60):
            raise PermissionError("Skriv PIN-koden din.")
        self._require_signed_site(card, "unlock")
        self._require_clinical_network(card, "unlock")
        self._release(card, pin=False)

    def cmd_verify(self, req, uid):
        """An IT person confirms an admin action (sudo) with the card PIN. Logged every time."""
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None or card.username != req.get("username"):
            raise CardError("Sett inn IT-kortet ditt.")
        if card.rolle != IT_ROLE:
            raise PermissionError("Bare IT-personell kan gjøre endringer på systemet.")
        self._check_card(card, "admin")
        if not self.reader.verify_pin(str(req.get("pin", ""))):
            self.audit.record(card.hpr, "admin_failed", {"user": card.username})
            raise CardError(f"Feil PIN. {self.reader.tries_left()} forsøk igjen.")
        self.audit.record(card.hpr, "admin_confirmed", {"user": card.username, "command": str(req.get("command", ""))[:200]})

    def cmd_unblock(self, req, uid):
        """IT lifts a PIN block after checking the person's ID (medicus-kort opphev-sperre, via sudo, so the
        IT card PIN was confirmed first). Logged with who did it."""
        self._require_root(uid)
        card_id = str(req.get("card_id", ""))
        if not self.reader.is_blocked(card_id):
            raise CardError("Kortet er ikke sperret (eller finnes ikke).")
        self.reader.unblock(card_id)
        self.audit.record(str(req.get("it_bruker", "root"))[:64], "card_unblocked", {"card": card_id[:64]})

    def cmd_revoke(self, req, uid):
        """IT revokes a lost, stolen or replaced card (medicus-kort tilbakekall, via sudo). A session open on
        that card ends at once (medicus-oktvakt closes its desktop)."""
        self._require_root(uid)
        card_id, reason = str(req.get("card_id", "")), str(req.get("grunn", ""))
        by = str(req.get("it_bruker", "root"))[:64]
        self.reader.revoke(card_id, reason, datetime.fromtimestamp(self.clock()).isoformat(timespec="seconds"), by)
        self.audit.record(by, "card_revoked", {"card": card_id[:64], "grunn": reason})
        owner = self.reader.cards[card_id]["username"]
        session = self._session()
        if session and session["username"] == owner:
            self.audit.record(session["hpr"], "session_ended", {"reason": "card_revoked", "mode": session["modus"]})
            self.session = None

    def cmd_restore(self, req, uid):
        """A card reported lost turned up again, and IT has checked the person's ID."""
        self._require_root(uid)
        card_id = str(req.get("card_id", ""))
        self.reader.restore(card_id)
        self.audit.record(str(req.get("it_bruker", "root"))[:64], "card_restored", {"card": card_id[:64]})

    def cmd_emergency(self, req, uid):
        self._require_root(uid)
        card = self.reader.inserted()
        if card is None:
            raise CardError("Nødtilgang krever helsepersonellkort, slik at tilgangen kan spores.")
        if card.rolle == IT_ROLE:
            raise PermissionError("Nødtilgang er bare for helsepersonell.")
        if self.reader.is_blocked(card.card_id):
            raise CardError("Kortet er sperret.")
        marks = self._check_card(card, "emergency", emergency=True)
        # No questions first: in an emergency every second counts. The why comes afterwards.
        situation = str(req.get("situasjon", ""))
        if situation not in SITUATIONS:
            situation = "Ikke oppgitt"
        report = self.reports.open(card.hpr, card.navn, situation)
        self.session = self._new_session(card, "nød", report["id"])
        self.session["situasjon"] = situation
        details = {"user": card.username, "situasjon": situation, "report": report["id"], **marks}
        if not self._on_clinical_network():
            details["utenfor_klinisk_nett"] = True  # never blocked: lives first, but the report will show it
        self.audit.record(card.hpr, "emergency_start", details)

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
                   "stilling": position(card.stillinger, card.rolle, self.site), "pin_tid": start}
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
        signed_site=certificate_site,
    )
    serve(authority, os.getenv("MEDICUS_AUTH_SOCKET", SOCKET))


if __name__ == "__main__":
    main()
