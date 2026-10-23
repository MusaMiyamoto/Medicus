"""Reads /etc/medicus/integrasjon.toml (or MEDICUS_INTEGRASJON) to decide where to connect."""

import os
import tomllib
from pathlib import Path

DEFAULT_PATH = Path("/etc/medicus/integrasjon.toml")
DEFAULTS = {"modus": "simulert", "simulert": {"url": "http://127.0.0.1:8100"}, "nhn": {}}


def load(path: Path | None = None) -> dict:
    path = Path(os.getenv("MEDICUS_INTEGRASJON", path or DEFAULT_PATH))
    if not path.exists():
        return DEFAULTS
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {**DEFAULTS, **data}
