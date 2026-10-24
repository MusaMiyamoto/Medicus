"""Older patient record systems (DIPS Arena, Epic, …) in locked-down windows next to Medicus.

The hospital keeps running its record system on its own servers. Medicus only shows it, two ways:

  rdp  A RemoteApp window from the hospital's Remote Desktop servers (FreeRDP). The health worker's
       own card logs in (smart-card logon), so there is no second login. Nothing from this PC is
       shared with the server: no disks, no clipboard, no USB, no printers. So patient data can't be
       copied out through the window, and nothing on the server can reach this PC's files.
  web  A web version of the system, opened in Nettleser. Only the address IT approved is allowed.

IT approves systems in /etc/medicus/journalsystemer.toml (see os/config/includes.chroot/etc/medicus/).
`medicus-journalsystem oppdater` (root, also at boot and every 30 minutes) then:
  - writes the RDP servers' addresses into /etc/hosts, because users have no DNS of their own;
  - opens the firewall for exactly those addresses and ports (nftables sets), nothing else;
  - adds the web systems to the web filter;
  - makes one Start-menu icon per system.
"""

import re
import socket
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

CONFIG = Path("/etc/medicus/journalsystemer.toml")
HOSTS = Path("/etc/hosts")
APPLICATIONS = Path("/usr/local/share/applications")
CLIENT = "xfreerdp3"
HOSTS_START = "# --- medicus-journalsystem: start (endres av medicus-journalsystem oppdater) ---"
HOSTS_END = "# --- medicus-journalsystem: slutt ---"

DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PROGRAM = re.compile(r"^\|\|[A-Za-z0-9_.-]{1,64}$")  # a published RemoteApp alias, e.g. ||DIPSArena
NAME = re.compile(r"^[A-Za-zÆØÅæøå0-9 .()/-]{2,40}$")


@dataclass(frozen=True)
class System:
    navn: str
    type: str                  # "rdp" or "web"
    server: str = ""           # rdp: the Remote Desktop server (or farm) name
    port: int = 3389
    program: str = ""          # rdp: RemoteApp alias; empty = the whole remote desktop
    gateway: str = ""          # rdp: Remote Desktop Gateway, if the hospital uses one (port 443)
    mikrofon: bool = False     # rdp: send the microphone (dictation in the record system)
    url: str = ""              # web

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.navn.lower().translate(str.maketrans("æøå", "eoa"))).strip("-")

    def endpoints(self) -> list[tuple[str, int]]:
        """Where this PC must be allowed to connect for this system."""
        if self.type != "rdp":
            return []
        return [(self.gateway, 443)] if self.gateway else [(self.server, self.port)]


class ConfigError(ValueError):
    pass


def _host(value, what) -> str:
    value = str(value).strip().lower()
    if not DOMAIN.match(value):
        raise ConfigError(f"{what}: skriv et fullt vertsnavn, for eksempel rds.sykehuset.no.")
    return value


def parse(data: dict) -> list[System]:
    """Validate IT's list. One bad entry stops the whole update, so nothing half-checked goes live."""
    systems, names = [], set()
    for i, entry in enumerate(data.get("system", []), start=1):
        if not isinstance(entry, dict):
            raise ConfigError(f"System {i}: ugyldig oppføring.")
        name = str(entry.get("navn", "")).strip()
        if not NAME.match(name):
            raise ConfigError(f"System {i}: navn må være 2–40 vanlige tegn.")
        if name.lower() in names:
            raise ConfigError(f"«{name}» står to ganger.")
        names.add(name.lower())
        kind = entry.get("type")
        if kind == "rdp":
            port = entry.get("port", 3389)
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise ConfigError(f"«{name}»: ugyldig port.")
            program = str(entry.get("program", ""))
            if program and not PROGRAM.match(program):
                raise ConfigError(f"«{name}»: program må være et RemoteApp-navn som ||DIPSArena.")
            gateway = _host(entry["gateway"], f"«{name}» gateway") if entry.get("gateway") else ""
            systems.append(System(name, "rdp", _host(entry.get("server", ""), f"«{name}» server"), port, program,
                                  gateway, bool(entry.get("mikrofon", False))))
        elif kind == "web":
            url = str(entry.get("url", "")).strip()
            parts = urlparse(url)
            if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
                raise ConfigError(f"«{name}»: adressen må være https:// uten brukernavn eller egen port.")
            _host(parts.hostname or "", f"«{name}» adresse")
            systems.append(System(name, "web", url=url))
        else:
            raise ConfigError(f"«{name}»: type må være \"rdp\" eller \"web\".")
    return systems


def load(path: Path = CONFIG) -> list[System]:
    try:
        with Path(path).open("rb") as f:
            return parse(tomllib.load(f))
    except FileNotFoundError:
        return []
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e


_web_cache: dict = {}


def web_hosts(path: Path = CONFIG) -> frozenset[str]:
    """The approved web systems' host names, for Nettleser (asked on every page load, so cached until
    the file changes). A missing or broken file approves nothing."""
    try:
        key = (str(path), Path(path).stat().st_mtime_ns)
    except OSError:
        return frozenset()
    if key not in _web_cache:
        try:
            hosts = frozenset(urlparse(s.url).hostname for s in load(path) if s.type == "web")
        except (ConfigError, OSError):
            hosts = frozenset()
        _web_cache.clear()
        _web_cache[key] = hosts
    return _web_cache[key]


def proxy_filter(systems: list[System]) -> str:
    """Web filter lines for the web systems: exactly their host name, not its subdomains."""
    hosts = sorted({urlparse(s.url).hostname for s in systems if s.type == "web"})
    return "".join(f"^{re.escape(host)}$\n" for host in hosts)


def rdp_command(system: System) -> list[str]:
    """FreeRDP, locked down. No /drive, /usb, /printer, /serial or /parallel: none are shared."""
    command = [CLIENT, f"/v:{system.server}:{system.port}",
               "/cert:deny",        # the server must have a certificate this PC trusts; no "accept anyway"
               "/smartcard-logon",  # log in with the health worker's card: no second password
               "/smartcard",        # and let the record system use the card to sign (e.g. prescriptions)
               "-clipboard",        # patient data can't be copied out through the window
               "+auto-reconnect", "/dynamic-resolution"]
    if system.program:
        command.append(f"/app:program:{system.program},name:{system.navn}")
    if system.gateway:
        command.append(f"/gateway:g:{system.gateway}:443,type:auto")
    if system.mikrofon:
        command.append("/microphone")
    return command


def resolve(host: str, port: int, lookup=socket.getaddrinfo) -> list[str]:
    try:
        found = lookup(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return []
    return sorted({info[4][0] for info in found})


def hosts_file(current: str, addresses: dict[str, list[str]]) -> str:
    """/etc/hosts with our block replaced (users can reach these names without DNS)."""
    lines, inside = [], False
    for line in current.splitlines():
        if line == HOSTS_START:
            inside = True
        elif line == HOSTS_END:
            inside = False
        elif not inside:
            lines.append(line)
    block = [f"{ip}\t{host}" for host, ips in sorted(addresses.items()) for ip in ips]
    if block:
        lines += [HOSTS_START, *block, HOSTS_END]
    return "\n".join(lines) + "\n"


def nft_script(addresses: dict[str, list[str]], systems: list[System]) -> str:
    """Fill the firewall sets with exactly the approved address + port pairs."""
    v4, v6 = [], []
    for system in systems:
        for host, port in system.endpoints():
            for ip in addresses.get(host, []):
                (v6 if ":" in ip else v4).append(f"{ip} . {port}")
    script = ["flush set inet filter journalsystem4", "flush set inet filter journalsystem6"]
    if v4:
        script.append(f"add element inet filter journalsystem4 {{ {', '.join(sorted(set(v4)))} }}")
    if v6:
        script.append(f"add element inet filter journalsystem6 {{ {', '.join(sorted(set(v6)))} }}")
    return "\n".join(script) + "\n"


def desktop_entry(system: System) -> str:
    kind = "fjernvindu, logges inn med kortet" if system.type == "rdp" else "webversjon i Nettleser"
    return "\n".join([
        "[Desktop Entry]", "Type=Application", f"Name={system.navn}",
        f"Comment=Sykehusets journalsystem ({kind})",
        f"Exec=medicus-journalsystem start {system.slug}", "Icon=medicus-pasient", "Terminal=false",
        "Categories=Office;", "Keywords=journal;pasient;", "",
    ])
