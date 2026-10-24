"""medicus-oppgaver: the Task Manager (IT mode).

    medicus-oppgaver                         the window (oppgaver/app.py)
    medicus-oppgaver liste                   running processes as text
    medicus-oppgaver stopp PID START         ask the program to close (SIGTERM)
    medicus-oppgaver stopp PID START --tving stop it at once (SIGKILL); unsaved work is lost
    medicus-lukk-program                     "Lukk program som henger" for health personnel (close_own)

`stopp` only runs as root: the window runs it through sudo, which asks for the IT card's PIN, so
every stop is confirmed with the card. It checks the protection rules again here (the window is
not trusted to have done it), refuses if PID START is no longer the same process (PIDs are reused),
and writes every stop and every refusal to the audit log. The log holds the program's name, PID
and user, never its command line, which can contain file names.
"""

import argparse
import json
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path

from medicus.audit import AuditLog
from oppgaver import prosesser

AUDIT = Path("/var/lib/medicus-oppgaver/audit.jsonl")
REPORT_URL = "http://127.0.0.1:8000/api/program-lukket"

# Exit codes the window turns into messages. sudo itself exits 1 when the PIN is wrong.
OK, NOT_ROOT, PROTECTED, GONE, STILL_RUNNING = 0, 2, 3, 4, 5


def listing(out=print, proc=prosesser.PROC) -> int:
    snap = prosesser.Snapshot(proc)
    snap.read()
    time.sleep(0.5)
    for p in sorted((p for p in snap.read() if not p.kernel), key=lambda p: (-p.cpu, -p.rss)):
        lock = "  [beskyttet]" if prosesser.protected(p) else ""
        out(f"{p.pid:>7}  {p.user:<12} {p.status:<18} {p.cpu:5.1f} %  {p.rss // 2**20:>6} MB  {p.name}{lock}")
    return OK


def _gone(pid: int, start: int, proc) -> bool:
    p = prosesser.read(pid, proc)
    return p is None or p.start != start or p.state in ("Z", "X")


def stop(pid: int, start: int, force: bool, proc=prosesser.PROC, kill=os.kill, audit=None,
         who=None, wait=5.0, out=print) -> int:
    audit = audit or AuditLog(AUDIT)
    who = who or os.getenv("SUDO_USER", "root")
    p = prosesser.read(pid, proc)
    if p is None or p.start != start:
        out("Programmet er allerede avsluttet.")
        return GONE
    details = {"pid": pid, "program": p.name, "bruker": p.user, "tvungen": force}
    reason = prosesser.protected(p)
    if reason:
        audit.record(who, "prosess_stopp_avvist", {**details, "grunn": reason})
        out(f"Beskyttet: {reason}")
        return PROTECTED
    kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    deadline = time.monotonic() + wait
    while not _gone(pid, start, proc) and time.monotonic() < deadline:
        time.sleep(0.1)
    ended = _gone(pid, start, proc)
    audit.record(who, "prosess_stoppet" if ended else "prosess_svarer_ikke", details)
    if ended:
        out(f"{p.name} er avsluttet.")
        return OK
    out(f"{p.name} svarer ikke. Du kan tvinge den til å avslutte.")
    return STILL_RUNNING


def report(program: str, force: bool, ended: bool) -> None:
    """Tell the Medicus service, which writes it to the audit log under the logged-in card. Never in
    the way: if the service doesn't answer, the program has still been closed."""
    body = json.dumps({"program": program, "tvungen": force, "avsluttet": ended}).encode()
    request = urllib.request.Request(REPORT_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=3).close()
    except OSError:
        pass


def close_own(pid: int, start: int, force: bool, proc=prosesser.PROC, kill=os.kill, uid=None,
              tell=report, wait=5.0) -> int:
    """'Lukk program som henger': a health worker closes one of their own work programs. No root and
    no PIN (they are logged in with their card and it is their own program), but the same checks."""
    uid = os.getuid() if uid is None else uid
    p = prosesser.read(pid, proc)
    if p is None or p.start != start:
        return GONE
    if not prosesser.user_may_close(p, uid):
        return PROTECTED
    try:
        kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        return GONE
    deadline = time.monotonic() + wait
    while not _gone(pid, start, proc) and time.monotonic() < deadline:
        time.sleep(0.1)
    ended = _gone(pid, start, proc)
    tell(p.name, force, ended)
    return OK if ended else STILL_RUNNING


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from oppgaver.app import main as window
        return window()
    parser = argparse.ArgumentParser(prog="medicus-oppgaver")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("liste")
    s = sub.add_parser("stopp")
    s.add_argument("pid", type=int)
    s.add_argument("start", type=int)
    s.add_argument("--tving", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "liste":
        return listing()
    if os.geteuid() != 0:
        print("Å stoppe programmer krever IT-kortet: kjør med sudo.")
        return NOT_ROOT
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    return stop(args.pid, args.start, args.tving)


if __name__ == "__main__":
    sys.exit(main())
