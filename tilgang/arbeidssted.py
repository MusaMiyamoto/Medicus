"""Where this workstation is. Set once per PC by IT in /etc/medicus/arbeidssted.toml:

    id = "ous-ulleval"
    navn = "Oslo universitetssykehus, Ullevål"
    nett = ["10.20.0.0/16"]   # optional: the clinical VLANs. Then normal logins only work there.
    kort_uten_pin_minutter = 240   # optional: card back in resumes a held session without the PIN,
                                   # up to this long after the PIN was last typed. 0 (default) = off.

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
    # Tap-in: minutes after the last PIN in which putting the card back resumes a held session. 0 = off.
    kort_uten_pin_minutter: int = 0

    def public(self) -> dict:
        return asdict(self)


UNKNOWN = Arbeidssted("ukjent", "Ukjent arbeidssted (kontakt IT)")
# Never longer than one shift. Anything that isn't a whole number in 0..TAP_MAX switches tap-in off.
TAP_MAX = 720
# A `nett` list that can't be read must not switch the check off: nothing will match this.
NO_NETWORK = ("0.0.0.0/32",)


def load(path: Path = CONFIG) -> Arbeidssted:
    try:
        with Path(path).open("rb") as f:
            data = tomllib.load(f)
        site = Arbeidssted(str(data["id"]), str(data["navn"]))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return UNKNOWN
    tap = data.get("kort_uten_pin_minutter", 0)
    tap = tap if type(tap) is int and 0 <= tap <= TAP_MAX else 0
    if "nett" not in data:
        return Arbeidssted(site.id, site.navn, (), tap)
    try:
        subnets = check_subnets(data["nett"]) if isinstance(data["nett"], list) else ()
    except ValueError:
        subnets = ()
    return Arbeidssted(site.id, site.navn, subnets or NO_NETWORK, tap)


def load_sim_sites(path: Path = SIM_SITES) -> list[Arbeidssted]:
    """Demo only: the workplaces the simulated login screen can switch between."""
    try:
        return [Arbeidssted(s["id"], s["navn"]) for s in json.loads(Path(path).read_text(encoding="utf-8"))]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


def position(stillinger: dict, rolle: str, site: Arbeidssted) -> str:
    """The person's position at this workplace, or their authorization if they have none here."""
    return stillinger.get(site.id) or rolle
