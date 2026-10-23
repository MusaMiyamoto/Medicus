"""Where this workstation is. Set once per PC by IT in /etc/medicus/arbeidssted.toml:

    id = "ous-ulleval"
    navn = "Oslo universitetssykehus, Ullevål"
    nett = ["10.20.0.0/16"]   # optional: the clinical VLANs. Then normal logins only work there.

The card says who you are; the PC says where you are. So the same doctor shows up as
"Overlege, kardiologi · Oslo universitetssykehus, Ullevål" on a PC at Ullevål, and with the
position she holds at St. Olavs on a PC in Trondheim.
"""

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from .nett import check_subnets

CONFIG = Path("/etc/medicus/arbeidssted.toml")
SIM_SITES = Path("/etc/medicus/arbeidssteder-sim.json")


@dataclass(frozen=True)
class Arbeidssted:
    id: str
    navn: str
    # The site's clinical subnets (VLANs). Normal logins only work from these; see tilgang/nett.py.
    nett: tuple[str, ...] = ()

    def public(self) -> dict:
        return asdict(self)


UNKNOWN = Arbeidssted("ukjent", "Ukjent arbeidssted (kontakt IT)")
# A `nett` list that can't be read must not switch the check off: nothing will match this.
NO_NETWORK = ("0.0.0.0/32",)


def load(path: Path = CONFIG) -> Arbeidssted:
    try:
        with Path(path).open("rb") as f:
            data = tomllib.load(f)
        site = Arbeidssted(str(data["id"]), str(data["navn"]))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return UNKNOWN
    if "nett" not in data:
        return site
    try:
        subnets = check_subnets(data["nett"]) if isinstance(data["nett"], list) else ()
    except ValueError:
        subnets = ()
    return Arbeidssted(site.id, site.navn, subnets or NO_NETWORK)


def load_sim_sites(path: Path = SIM_SITES) -> list[Arbeidssted]:
    """Demo only: the workplaces the simulated login screen can switch between."""
    try:
        return [Arbeidssted(s["id"], s["navn"]) for s in json.loads(Path(path).read_text(encoding="utf-8"))]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


def position(stillinger: dict, rolle: str, site: Arbeidssted) -> str:
    """The person's position at this workplace, or their authorization if they have none here."""
    return stillinger.get(site.id) or rolle
