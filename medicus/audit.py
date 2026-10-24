"""Tamper-evident audit log.

Entries hold metadata only (who, what, when, sizes) and never patient content.

Two protections:

1. A hash chain: each entry stores the hash of the previous one, so editing or deleting a line breaks
   the chain and `verify()` reports where. On its own this only catches clumsy changes: someone who
   controls the machine can rewrite the whole file and compute a new, valid chain.

2. Forward-secure keys: each entry also gets an HMAC with a key that is replaced by its own hash right
   after use (key i+1 = SHA-256 of key i) and the old key overwritten. So someone who takes over the
   machine at 14:00 only gets the 14:00 key, and can't make entries from before 14:00 that check out.
   The very first key is saved as the *anchor* (`<log>.anker`). IT moves it off the machine (the
   Sikkerhetssenter warns while it is still here). With the anchor, `verify(anchor)` recomputes every
   key and finds a rebuilt chain, forged entries, and entries cut off the end.

The real fix is to ship every entry off the machine as it is written (central log server, see
docs/design.md). Until then, this makes forging the past impossible without the anchor.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows development: one process, the thread lock is enough
    fcntl = None

GENESIS = "0" * 64
TAIL_BYTES = 64 * 1024  # an entry is never near this long, so the last line is always inside it


def _digest(entry: dict) -> str:
    payload = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mac(key: bytes, entry_hash: str) -> str:
    return hmac.new(key, entry_hash.encode(), hashlib.sha256).hexdigest()


def next_key(key: bytes) -> bytes:
    return hashlib.sha256(b"medicus-revisjonslogg" + key).digest()


class AuditLog:
    def __init__(self, path: Path, sink=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path = self.path.with_name(self.path.name + ".nokkel")
        self.anchor_path = self.path.with_name(self.path.name + ".anker")
        # Optional callable(entry) run after every entry is written: ships it off the machine (central log
        # server), so a break-in can't erase the trail by deleting the file. It can never block the
        # clinician: a failure is noted in the log itself and the entry stays here to be sent later.
        self.sink = sink
        self._lock = threading.Lock()

    # --- Writing -----------------------------------------------------------

    def _last_hash(self, f) -> str:
        """The hash in the last line, read from the end of the file: the same speed for any log length."""
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return GENESIS
        f.seek(max(0, size - TAIL_BYTES))
        lines = [line for line in f.read().splitlines() if line.strip()]
        return json.loads(lines[-1])["hash"] if lines else GENESIS

    def _write_secret(self, path: Path, data: dict) -> None:
        tmp = path.with_name(path.name + ".ny")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _take_key(self, f) -> tuple[bytes, int, int | None]:
        """The current key, its number, and (only when a new key series starts) the line it starts on.

        A new log gets a random first key, saved as the anchor. So does a log whose key file is gone
        (an older Medicus, or someone deleted it): logging must never stop, so a new series starts on
        the next line, says so in the log, and leaves a new anchor that the Sikkerhetssenter shows."""
        try:
            data = json.loads(self.key_path.read_text(encoding="utf-8"))
            return bytes.fromhex(data["nokkel"]), int(data["nr"]), None
        except (OSError, ValueError, KeyError):
            pass
        f.seek(0)
        start_line = sum(1 for line in f if line.strip()) + 1
        key = os.urandom(32)
        self._write_secret(self.anchor_path, {"logg": self.path.name, "nokkel": key.hex(), "fra_linje": start_line,
                                              "laget": datetime.now(timezone.utc).isoformat()})
        return key, 0, start_line

    def record(self, user: str, action: str, details: dict | None = None) -> dict:
        with self._lock, self.path.open("a+", encoding="utf-8") as f:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_EX)  # several processes may write the same log
            key, number, new_series = self._take_key(f)
            if new_series is not None and new_series > 1:
                key, number, _ = self._append(f, key, number, "system", "audit_key_series_started",
                                           {"fra_linje": new_series})
            entry = self._append(f, key, number, user, action, details)[2]
        if self.sink is not None:
            try:
                self.sink(entry)
            except Exception as error:  # noqa: BLE001 - never block the clinician
                if action != "audit_sink_failed":
                    self.record("system", "audit_sink_failed", {"feil": str(error)[:200], "nr": entry["nr"]})
        return entry

    def _append(self, f, key: bytes, number: int, user: str, action: str, details: dict | None):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "action": action,
            "details": details or {},
            "prev": self._last_hash(f),
            "nr": number,
        }
        entry["hash"] = _digest(entry)
        entry["mac"] = _mac(key, entry["hash"])
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        # The key that signed this entry is gone from here on.
        key, number = next_key(key), number + 1
        self._write_secret(self.key_path, {"nokkel": key.hex(), "nr": number})
        return key, number, entry

    # --- Checking ----------------------------------------------------------

    def anchor_on_machine(self) -> bool:
        return self.anchor_path.exists()

    def verify(self, anchor: bytes | None = None, from_line: int = 1) -> tuple[bool, int | None]:
        """Return (ok, first_broken_line_number). With the anchor (and the line its series starts on, from
        the anchor file), every entry's key from that line on is checked too, and the key now on the
        machine must be the one after the last entry (nothing cut off the end)."""
        if not self.path.exists():
            return True, None
        prev, key, n, number = GENESIS, anchor, 0, 0
        with self.path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return False, n
                stored, mac = entry.pop("hash", None), entry.pop("mac", None)
                if entry.get("prev") != prev or _digest(entry) != stored:
                    return False, n
                if key is not None and n >= from_line:
                    if entry.get("nr") != number or mac is None or not hmac.compare_digest(mac, _mac(key, stored)):
                        return False, n
                    key, number = next_key(key), number + 1
                prev = stored
        if key is not None:
            try:
                current = json.loads(self.key_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False, n + 1
            if current.get("nr") != number or current.get("nokkel") != key.hex():
                return False, n + 1  # entries were removed from the end
        return True, None
