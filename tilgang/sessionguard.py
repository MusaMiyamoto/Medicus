"""medicus-oktvakt: makes the desktop follow the card login, enforced by the system.

Runs as root, outside the user's session, so a user can't stop it. Every second:
  - a desktop session for a Medicus user without a matching login (card not returned in time,
    emergency time is up, or logged out elsewhere) is terminated at once;
  - a login held because the card was taken out has its desktop locked (the lock screen needs
    the same card and PIN back, or only the card if this PC allows tap-in: then it is unlocked here);
  - a login with no desktop session left (the user logged out) is ended after a grace period.
"""

import grp
import json
import subprocess
import sys
import time

from . import EMERGENCY_USER
from .client import AuthError, call

GROUPS = ("medicus-personell", "medicus-nod", "medicus-it")
GRACE_SECONDS = 15
REMOTE_CLIENT = "xfreerdp3"  # journalsystem/: the hospital's record systems in remote windows


def medicus_users() -> set[str]:
    users = set()
    for name in GROUPS:
        try:
            users.update(grp.getgrnam(name).gr_mem)
        except KeyError:
            pass
    return users | {EMERGENCY_USER}


def desktop_sessions(run=subprocess.run) -> list[dict] | None:
    """Open login sessions, or None if they can't be read (then this round is skipped, not guessed)."""
    out = run(["loginctl", "list-sessions", "--json=short"], capture_output=True, text=True, check=False)
    try:
        sessions = json.loads(out.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return sessions if isinstance(sessions, list) else None


def decide(login: dict | None, sessions: list[dict], users: set[str]) -> tuple[list[str], bool]:
    """Return (session ids to terminate, whether the login has a desktop)."""
    allowed_user = login["linux_bruker"] if login else None
    terminate = [s["session"] for s in sessions if s.get("user") in users and s.get("user") != allowed_user]
    has_desktop = any(s.get("user") == allowed_user for s in sessions) if login else False
    return terminate, has_desktop


def to_lock(login: dict | None, sessions: list[dict]) -> list[str]:
    """The held login's desktop sessions: locked while its card is out."""
    if not login or "holdt_sekunder_igjen" not in login:
        return []
    return [s["session"] for s in sessions if s.get("user") == login["linux_bruker"]]


def should_tap(status: dict) -> bool:
    """The held login's own card is back and this PC allows tap-in. authd checks everything again."""
    login, card = status.get("okt"), status.get("kort")
    return bool(login and card and "holdt_sekunder_igjen" in login and login["modus"] == "normal"
                and card["username"] == login["username"] and not card.get("sperret")
                and status.get("arbeidssted", {}).get("kort_uten_pin_minutter", 0) > 0)


def main() -> int:
    alone_since = None
    locked: set[str] = set()
    tap_tried = False  # once per time the card goes in, so a refusal isn't repeated every second
    while True:
        time.sleep(1)
        try:
            status = call("status")
        except AuthError:
            continue
        login = status["okt"]
        sessions = desktop_sessions()
        if sessions is None:
            continue
        if not status.get("kort"):
            tap_tried = False
        elif should_tap(status) and not tap_tried:
            tap_tried = True
            try:
                call("tap")
                for session_id in to_lock(login, sessions):
                    subprocess.run(["loginctl", "unlock-session", session_id], check=False)
                continue
            except AuthError:
                pass
        terminate, has_desktop = decide(login, sessions, medicus_users())
        for session_id in terminate:
            subprocess.run(["loginctl", "terminate-session", session_id], check=False)
        # Lock once per hold: the lock screen stays until the card + PIN come back.
        held = to_lock(login, sessions)
        for session_id in set(held) - locked:
            subprocess.run(["loginctl", "lock-session", session_id], check=False)
            # The hospital's record systems too: disconnect the remote windows. The server keeps the
            # remote session, so the same card reconnects to it; nobody can use it from this screen.
            subprocess.run(["pkill", "-TERM", "-u", login["linux_bruker"], "-x", REMOTE_CLIENT], check=False)
        locked = set(held)
        if login and not has_desktop:
            alone_since = alone_since or time.monotonic()
            if time.monotonic() - alone_since > GRACE_SECONDS:
                try:
                    call("end")
                except AuthError:
                    pass
                alone_since = None
        else:
            alone_since = None


if __name__ == "__main__":
    sys.exit(main())
