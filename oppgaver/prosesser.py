"""Read running processes from /proc and decide which of them may be stopped.

Pure Python with no GTK, so it can be tested against a fake /proc. The rules here are used twice:
the window greys out protected processes, and the root helper (oppgaver/__main__.py) checks them
again before it sends a signal, so the window is not what keeps essential processes alive.
"""

from __future__ import annotations

import os
import pwd
import re
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")

# The desktop itself: stopping one of these logs the user out or leaves a black screen.
DESKTOP = {"Xorg", "Xwayland", "lightdm", "xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop",
           "xfsettingsd", "xfconfd", "dbus-daemon", "dbus-broker", "systemd", "at-spi-bus-laun",
           "at-spi2-registr", "polkit-gnome-au", "medicus-greeter"}

# Medicus' own programs. They all run as "python3", so they are recognised by the module they start
# (python3 -m MODULE, or python3 -c "... from MODULE..."). Name shown in the list, and whether the
# program can hold patient work that is not saved yet. More specific modules first.
PROGRAMS = (
    ("tilgang.authd", "Kortinnlogging", False),
    ("tilgang.sessionguard", "Kortvakt", False),
    ("tilgang", "Kortinnlogging", False),
    ("medicus.forhent", "Forhåndshenting", False),
    ("medicus", "Pasientjournal (tjeneste)", False),
    ("helsenett", "Helsenett", False),
    ("oppgaver", "Oppgavebehandling", False),
    ("nettleser", "Nettleser", True),
    ("journalsystem", "Journalsystem", True),
    ("tekst", "Text", True),
    ("kalkulator", "Kalkulator", False),
)


def _module(cmdline: str, comm: str) -> str | None:
    """The Medicus module a Python process runs, or None."""
    if not comm.startswith("python"):
        return None
    m = re.search(r"(?:-m |from )([a-z_.]+)", cmdline)
    if not m:
        return None
    started = m.group(1)
    for module, _, _ in PROGRAMS:
        if started == module or started.startswith(module + "."):
            return module
    return None


# What health personnel may close themselves ("Lukk program som henger"): the programs they work in,
# under the names the Start menu gives them. Nothing else of theirs (the desktop, the taskbar, the
# card lock) is even listed, so closing one can't break the PC. Medicus' web apps each run in their
# own Nettleser window, recognised by the address it was opened with.
PAGES = {"": "Journalassistent", "/pasient": "Pasientjournal", "/post": "Post", "/om": "Om Medicus",
         "/nod": "Nødtilgang", "/rapport": "Rapport om nødtilgang", "/helsenorge": "Innbyggerportal",
         "/utlevering": "Utleveringsforespørsler"}
OTHER_WORK = {"thunar": "Files", "ristretto": "Pictures", "evince": "Dokumenter"}
RECORD_SYSTEM = "xfreerdp3"  # the hospital's record systems (DIPS, Epic) in their locked-down window


def work_program(p: "Process") -> str | None:
    """The name of the work program this is, if health personnel may close it themselves."""
    module = _module(p.cmdline, p.comm)
    if module == "nettleser":
        page = re.search(r"http://127\.0\.0\.1:(?:8000|8100)(/[a-z]*)?/?(?:\s|$)", p.cmdline)
        return PAGES.get(page.group(1) or "", "Nettleser") if page else "Nettleser"
    if module == "tekst":
        return "Text"
    if module == "kalkulator":
        return "Kalkulator"
    if p.comm == RECORD_SYSTEM:
        named = re.search(r"name:(.+?)(?= [/+-]|$)", p.cmdline)
        return named.group(1).strip() if named else "Journalsystem"
    return OTHER_WORK.get(p.comm)


STATES = {"R": "Kjører", "S": "Venter", "D": "Venter på disk", "I": "Inaktiv", "T": "Stoppet",
          "t": "Stoppet", "Z": "Avsluttet (zombie)", "X": "Avsluttet"}

FIRST_USER_UID = 1000
PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


@dataclass
class Process:
    pid: int
    ppid: int
    comm: str        # the kernel's short name, at most 15 characters
    cmdline: str     # used to recognise programs; never shown in full or written to the audit log
    uid: int
    user: str
    state: str
    cpu_ticks: int   # utime + stime
    start: int       # start time in ticks since boot: (pid, start) names one process, even if the PID is reused
    rss: int         # resident memory in bytes
    cpu: float = 0.0  # share of the whole machine since the last reading, 0-100

    @property
    def kernel(self) -> bool:
        return self.pid == 2 or self.ppid == 2

    @property
    def name(self) -> str:
        """A readable name: the work program or Medicus program it is, or the kernel's name for it."""
        work = work_program(self)
        if work:
            return work
        module = _module(self.cmdline, self.comm)
        return next(title for m, title, _ in PROGRAMS if m == module) if module else self.comm

    @property
    def status(self) -> str:
        return STATES.get(self.state, self.state)

    @property
    def holds_patient_work(self) -> bool:
        if self.comm == RECORD_SYSTEM:
            return True
        module = _module(self.cmdline, self.comm)
        return any(m == module and unsaved for m, _, unsaved in PROGRAMS)


def protected(p: Process, own_pid: int | None = None) -> str | None:
    """Why this process must not be stopped from the Task Manager, or None if it may be."""
    if p.pid == 1 or p.kernel:
        return "Del av operativsystemets kjerne."
    if p.pid == (os.getpid() if own_pid is None else own_pid):
        return "Dette er Oppgavebehandling selv."
    if p.uid < FIRST_USER_UID:
        # Logins, card watch, audit, firewall, virus protection, the record service: stopping them
        # would weaken security or the record. IT restarts services with systemctl in the terminal.
        return "Systemtjeneste. Start den på nytt med systemctl i terminalen i stedet."
    if p.comm in DESKTOP:
        return "Skrivebordet trenger denne. Logg ut i stedet."
    return None


def user_may_close(p: Process, uid: int, own_pid: int | None = None) -> bool:
    """Whether a health worker with this uid may close this process from "Lukk program som henger".
    Only their own work programs. (The kernel only lets them signal their own processes anyway; this
    keeps them from closing their own desktop by mistake.)"""
    return p.uid == uid and work_program(p) is not None and protected(p, own_pid) is None


def _user(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def read(pid: int, proc: Path = PROC) -> Process | None:
    """One process, or None if it has gone (it can end while we read it)."""
    base = proc / str(pid)
    try:
        stat = (base / "stat").read_text()
        cmdline = (base / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        uid = next(int(line.split()[1]) for line in (base / "status").read_text().splitlines()
                   if line.startswith("Uid:"))
    except (OSError, StopIteration, ValueError, IndexError):
        return None
    # The name is in brackets and can itself contain spaces and brackets, so split at the last ")".
    comm = stat[stat.index("(") + 1:stat.rindex(")")]
    rest = stat[stat.rindex(")") + 2:].split()
    return Process(pid=pid, ppid=int(rest[1]), comm=comm, cmdline=cmdline, uid=uid, user=_user(uid),
                   state=rest[0], cpu_ticks=int(rest[11]) + int(rest[12]), start=int(rest[19]),
                   rss=int(rest[21]) * PAGE)



def total_ticks(proc: Path = PROC) -> int:
    """All CPU time spent on the machine so far, from the first line of /proc/stat."""
    first = (proc / "stat").read_text().splitlines()[0].split()
    return sum(int(x) for x in first[1:])


class Snapshot:
    """Reads every process; CPU use is the change since the previous reading."""

    def __init__(self, proc: Path = PROC):
        self.proc = proc
        self.before: dict[tuple[int, int], int] = {}
        self.before_total = 0

    def read(self) -> list[Process]:
        total = total_ticks(self.proc)
        found = []
        for entry in self.proc.iterdir():
            if entry.name.isdigit() and (p := read(int(entry.name), self.proc)):
                found.append(p)
        spent = total - self.before_total
        now = {}
        for p in found:
            key = (p.pid, p.start)
            if key in self.before and spent > 0:
                p.cpu = round(100 * (p.cpu_ticks - self.before[key]) / spent, 1)
            now[key] = p.cpu_ticks
        self.before, self.before_total = now, total
        return found


def memory(proc: Path = PROC) -> tuple[int, int]:
    """(used, total) memory in bytes. Used = total minus what programs could still get."""
    info = {}
    for line in (proc / "meminfo").read_text().splitlines():
        name, _, value = line.partition(":")
        info[name] = int(value.split()[0]) * 1024
    return info["MemTotal"] - info.get("MemAvailable", info.get("MemFree", 0)), info["MemTotal"]
