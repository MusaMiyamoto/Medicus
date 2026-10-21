"""Tamper-evident audit log.

Each entry stores the hash of the previous entry, so editing or deleting any
line breaks the chain and `verify()` reports where. Entries hold metadata only
(who, what, when, sizes) and never patient content.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    payload = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _entries(self):
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def _last_hash(self) -> str:
        last = GENESIS
        for entry in self._entries():
            last = entry["hash"]
        return last

    def record(self, user: str, action: str, details: dict | None = None) -> dict:
        with self._lock:
            entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "user": user,
                "action": action,
                "details": details or {},
                "prev": self._last_hash(),
            }
            entry["hash"] = _digest(entry)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return entry

    def verify(self) -> tuple[bool, int | None]:
        """Return (ok, first_broken_line_number)."""
        if not self.path.exists():
            return True, None
        prev = GENESIS
        with self.path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return False, n
                stored = entry.pop("hash", None)
                if entry.get("prev") != prev or _digest(entry) != stored:
                    return False, n
                prev = stored
        return True, None
