"""Health-personnel cards.

`SimulatedReader` stands in for a real chip-card reader so the system can be tested without
hardware. The real reader (PC/SC + PKCS#11 through OpenSC) plugs in behind the same interface:
`inserted()` and `verify_pin()`. Like a real card, three wrong PINs block it.
"""

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_TRIES = 3
PBKDF2_ROUNDS = 200_000


@dataclass(frozen=True)
class Card:
    """Who the person is. Where they work comes from the workstation (tilgang/arbeidssted.py)."""

    card_id: str
    navn: str
    rolle: str          # authorization from the health personnel register, e.g. "Lege"
    hpr: str
    username: str
    stillinger: dict = field(default_factory=dict)  # position per workplace id

    def public(self) -> dict:
        return asdict(self)


def hash_pin(pin: str, salt: bytes | None = None) -> dict:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PBKDF2_ROUNDS)
    return {"salt": salt.hex(), "hash": digest.hex()}


def check_pin(pin: str, stored: dict) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(stored["salt"]), PBKDF2_ROUNDS)
    return hmac.compare_digest(digest.hex(), stored["hash"])


class CardError(Exception):
    pass


class SimulatedReader:
    """Cards from a root-owned JSON file. 'Inserting' a card is a command to medicus-authd."""

    def __init__(self, cards_file: Path, state_file: Path):
        self.state_file = Path(state_file)
        raw = json.loads(Path(cards_file).read_text(encoding="utf-8"))
        self.cards = {c["card_id"]: c for c in raw}
        self.current: str | None = None
        self.tries = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}

    def list_cards(self) -> list[dict]:
        return [self._card(c).public() | {"sperret": self.is_blocked(cid)} for cid, c in self.cards.items()]

    def _card(self, raw: dict) -> Card:
        return Card(**{k: raw[k] for k in Card.__dataclass_fields__ if k in raw})

    def insert(self, card_id: str):
        if card_id not in self.cards:
            raise CardError("Ukjent kort.")
        self.current = card_id

    def remove(self):
        self.current = None

    def inserted(self) -> Card | None:
        return self._card(self.cards[self.current]) if self.current else None

    def is_blocked(self, card_id: str) -> bool:
        return self.tries.get(card_id, 0) >= MAX_TRIES

    def verify_pin(self, pin: str) -> bool:
        if self.current is None:
            raise CardError("Ingen kort i leseren.")
        if self.is_blocked(self.current):
            raise CardError("Kortet er sperret etter for mange feil PIN-forsøk.")
        ok = check_pin(pin, self.cards[self.current]["pin"])
        self.tries[self.current] = 0 if ok else self.tries.get(self.current, 0) + 1
        self._save()
        if not ok and self.is_blocked(self.current):
            raise CardError("Feil PIN. Kortet er nå sperret.")
        return ok

    def tries_left(self) -> int:
        return MAX_TRIES - self.tries.get(self.current, 0) if self.current else 0

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.tries))


def build_cards_file(demo_file: Path, out_file: Path):
    """Turn the demo card list (with plain PINs) into the hashed file the reader uses."""
    cards = json.loads(Path(demo_file).read_text(encoding="utf-8"))
    for card in cards:
        card["pin"] = hash_pin(card.pop("demo_pin"))
    Path(out_file).write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
