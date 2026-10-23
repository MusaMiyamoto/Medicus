"""medicus-oktvakt: makes the desktop follow the card login, enforced by the system.

Runs as root, outside the user's session, so a user can't stop it. Every second:
  - a desktop session for a Medicus user without a matching login (card not returned in time,
    emergency time is up, or logged out elsewhere) is terminated at once;
  - a login held because the card was taken out has its desktop locked (the lock screen needs
    the same card and PIN back);
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


def main() -> int:
    alone_since = None
    locked: set[str] = set()
    while True:
        time.sleep(1)
        try:
            login = call("status")["okt"]
        except AuthError:
            continue
        sessions = desktop_sessions()
        if sessions is None:
            continue
        terminate, has_desktop = decide(login, sessions, medicus_users())
        for session_id in terminate:
            subprocess.run(["loginctl", "terminate-session", session_id], check=False)
        # Lock once per hold: the lock screen stays until the card + PIN come back.
        held = to_lock(login, sessions)
        for session_id in set(held) - locked:
            subprocess.run(["loginctl", "lock-session", session_id], check=False)
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
