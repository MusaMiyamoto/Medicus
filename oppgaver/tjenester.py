"""The system services IT can see in the Task Manager, and which of them may be restarted from it.

Only the services listed here are shown. A service that hangs (the patient record service, the
health network, the web filter, virus protection) can be restarted with the IT card PIN. The card
login, the card lock and the security services are shown but locked: restarting them would log
everyone out or open a gap in the protection, so that is done by restarting the PC instead.
"""

import subprocess
from dataclasses import dataclass

# (unit, name in the window, why it can't be restarted here, or None if it can)
SECURITY = "Sikkerhetstjeneste: kan ikke startes på nytt herfra. Start PC-en på nytt i stedet."
SERVICES = (
    ("medicus.service", "Pasientjournal (tjeneste)", None),
    ("medicus-helsenett-sim.service", "Helsenett", None),
    ("medicus-journalsystem.service", "Journalsystem", None),
    ("tinyproxy.service", "Nettfilter", None),
    ("clamav-daemon.service", "Virusbeskyttelse", None),
    ("clamav-freshclam.service", "Virusoppdatering", None),
    ("medicus-auth.service", "Kortinnlogging", "Alle blir logget ut. Start PC-en på nytt i stedet."),
    ("medicus-oktvakt.service", "Kortvakt", "Skjermlåsen når kortet tas ut, må alltid kjøre."),
    ("medicus-rydd-hjem.service", "Rydding av hjemmemapper",
     "Kjører bare ved oppstart. Nå ville den tømt mappene til den som er logget inn."),
    ("nftables.service", "Brannmur", SECURITY),
    ("apparmor.service", "Programbeskyttelse", SECURITY),
    ("usbguard.service", "USB-lås", SECURITY),
    ("auditd.service", "Sikkerhetslogg", SECURITY),
)
NAMES = {unit: name for unit, name, _ in SERVICES}

STATES = {"active": "Kjører", "activating": "Starter", "deactivating": "Stopper", "inactive": "Stoppet",
          "failed": "Feilet", "reloading": "Laster inn på nytt"}


@dataclass
class Service:
    unit: str
    name: str
    state: str  # systemd's ActiveState
    locked: str | None

    @property
    def status(self) -> str:
        return STATES.get(self.state, self.state or "Ukjent")


def locked(unit: str) -> str | None:
    """Why this service can't be restarted from the Task Manager; None if it can."""
    for name, _title, reason in SERVICES:
        if name == unit:
            return reason
    return "Ikke en tjeneste Oppgavebehandling kan starte på nytt."


def read(run=subprocess.run) -> list[Service]:
    units = [unit for unit, _, _ in SERVICES]
    try:
        out = run(["systemctl", "show", "--property=Id,ActiveState", *units],
                  capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    state = {}
    for block in out.strip().split("\n\n"):  # one block of Id=… and ActiveState=… per unit
        fields = dict(line.partition("=")[::2] for line in block.splitlines())
        if fields.get("Id"):
            state[fields["Id"]] = fields.get("ActiveState", "")
    return [Service(u, name, state.get(u, ""), reason) for u, name, reason in SERVICES]
