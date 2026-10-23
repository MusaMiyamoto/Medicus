"""Where this workstation is. Set once per PC by IT in /etc/medicus/arbeidssted.toml:

    id = "ous-ulleval"
    navn = "Oslo universitetssykehus, Ullevål"

The card says who you are; the PC says where you are. So the same doctor shows up as
"Overlege, kardiologi · Oslo universitetssykehus, Ullevål" on a PC at Ullevål, and with the
position she holds at St. Olavs on a PC in Trondheim.
"""

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG = Path("/etc/medicus/arbeidssted.toml")
SIM_SITES = Path("/etc/medicus/arbeidssteder-sim.json")


@dataclass(frozen=True)
class Arbeidssted:
    id: str
    navn: str

    def public(self) -> dict:
        return asdict(self)


UNKNOWN = Arbeidssted("ukjent", "Ukjent arbeidssted (kontakt IT)")


def load(path: Path = CONFIG) -> Arbeidssted:
    try:
        with Path(path).open("rb") as f:
            data = tomllib.load(f)
        return Arbeidssted(str(data["id"]), str(data["navn"]))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return UNKNOWN


def load_sim_sites(path: Path = SIM_SITES) -> list[Arbeidssted]:
    """Demo only: the workplaces the simulated login screen can switch between."""
    try:
        return [Arbeidssted(s["id"], s["navn"]) for s in json.loads(Path(path).read_text(encoding="utf-8"))]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


def position(stillinger: dict, rolle: str, site: Arbeidssted) -> str:
    """The person's position at this workplace, or their authorization if they have none here."""
    return stillinger.get(site.id) or rolle
