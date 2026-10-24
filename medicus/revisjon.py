"""medicus-revisjon: the audit logs' anchors and checks, for IT (IT mode, with sudo).

    medicus-revisjon status           which logs exist, and whether their anchor is still on this PC
    medicus-revisjon ankre            show every anchor so IT can store it elsewhere, then delete it here
    medicus-revisjon sjekk [FIL]      check every log; with FIL (the anchors as `ankre` showed them,
                                      one JSON object per line) also the keys, so a rebuilt log is found

Why: see medicus/audit.py. An anchor left on the machine helps an intruder rewrite the past.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .audit import AuditLog

LOGS = (
    Path("/var/lib/medicus-auth/audit.jsonl"),          # logins, emergency access, admin actions
    Path("/var/lib/medicus/audit.jsonl"),               # the web app: records opened, notes, Post
    Path("/var/lib/medicus-utstyr/audit.jsonl"),        # medical USB devices
    Path("/var/lib/medicus-wlan/audit.jsonl"),          # Wi-Fi and machine certificate
    Path("/var/lib/medicus-journalsystem/audit.jsonl"),  # the hospital's record systems
    Path("/var/lib/medicus-oppgaver/audit.jsonl"),      # programs stopped in the Task Manager
)


def anchors_left(logs=LOGS) -> tuple[list[Path], int]:
    """(logs whose anchor is still on this PC, how many logs couldn't be looked at)."""
    left, unknown = [], 0
    for path in logs:
        try:
            os.stat(path.with_name(path.name + ".anker"))
            left.append(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            unknown += 1
    return left, unknown


def status_check(logs=LOGS) -> dict:
    """For the Sikkerhetssenter."""
    name = "Revisjonslogg"
    left, unknown = anchors_left(logs)
    if left:
        where = ", ".join(str(p.parent) for p in left)
        return {"navn": name, "status": "advarsel",
                "forklaring": f"Startnøkkelen (ankeret) ligger fortsatt på maskinen ({where}). Med den kan en "
                              "innbruddstyv skrive om loggen uten at det synes. Kjør «sudo medicus-revisjon ankre»."}
    text = "Loggene er beskyttet med nøkler som byttes for hver linje. Ankrene er flyttet bort fra maskinen."
    if unknown:
        return {"navn": name, "status": "info",
                "forklaring": f"{text} ({unknown} logg(er) kan bare sjekkes av IT: «sudo medicus-revisjon status».)"}
    return {"navn": name, "status": "ok", "forklaring": text}


def _anchors(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            data = json.loads(line)
            result[data["logg_sti"]] = data
    return result


def main(argv=None, logs=LOGS, out=print, ask=input) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "status"
    if command == "status":
        left, unknown = anchors_left(logs)
        for path in logs:
            state = "anker på maskinen" if path in left else ("finnes ikke" if not path.exists() else "ok")
            out(f"{path}: {state}")
        if unknown:
            out(f"{unknown} logg(er) kunne ikke leses. Kjør med sudo.")
        return 0
    if command == "ankre":
        found = []
        for path in logs:
            anchor = path.with_name(path.name + ".anker")
            if anchor.exists():
                data = json.loads(anchor.read_text(encoding="utf-8"))
                found.append(anchor)
                out(json.dumps({"logg_sti": str(path), "nokkel": data["nokkel"],
                                "fra_linje": data.get("fra_linje", 1), "laget": data.get("laget", "")}))
        if not found:
            out("Ingen ankre på maskinen.")
            return 0
        out("Lagre linjene over i IT-sikkerhets nøkkelhvelv (ikke på denne PC-en).")
        if ask("Er de lagret et annet sted? Skriv ja for å slette dem her: ").strip().lower() != "ja":
            out("Ingenting er slettet.")
            return 1
        for anchor in found:
            anchor.unlink()
        out(f"{len(found)} anker/ankre slettet fra maskinen.")
        return 0
    if command == "sjekk":
        anchors = _anchors(Path(argv[1])) if len(argv) > 1 else {}
        bad = 0
        for path in logs:
            if not path.exists():
                continue
            a = anchors.get(str(path))
            ok, line = AuditLog(path).verify(bytes.fromhex(a["nokkel"]) if a else None, a["fra_linje"] if a else 1)
            how = "med anker" if a else "bare kjeden (uten anker)"
            out(f"{path}: {'i orden' if ok else f'ENDRET ved linje {line}'} ({how})")
            bad += not ok
        return 1 if bad else 0
    out(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
