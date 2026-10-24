"""medicus-journalsystem: the hospital's own record systems next to Medicus. See journalsystem/__init__.py.

    medicus-journalsystem                 list the approved systems
    medicus-journalsystem start NAVN      open one (health personnel, normal login only)
    medicus-journalsystem oppdater        apply /etc/medicus/journalsystemer.toml (IT mode, or at boot)
"""

import os
import subprocess
import sys
from pathlib import Path

import journalsystem as js
from medicus import nettsteder

COMMAND = "/usr/local/bin/medicus-journalsystem"
AUDIT = Path("/var/lib/medicus-journalsystem/audit.jsonl")
PROXY_FILTER = Path("/etc/tinyproxy/filter")


def show():
    systems = js.load()
    if not systems:
        print("Ingen journalsystemer er satt opp. IT legger dem inn i", js.CONFIG)
    for s in systems:
        where = f"{s.server}:{s.port}{' via ' + s.gateway if s.gateway else ''}" if s.type == "rdp" else s.url
        print(f"  {s.slug:<20} {s.navn:<24} {s.type:<4} {where}")


def start(slug: str) -> int:
    from tilgang.client import AuthError, call

    system = next((s for s in js.load() if s.slug == slug), None)
    if system is None:
        print(f"«{slug}» er ikke et godkjent journalsystem.", file=sys.stderr)
        return 1
    try:
        session = call("status")["okt"]
    except AuthError as e:
        print(e, file=sys.stderr)
        return 1
    # The same rule as Medicus' own patient record: a normal card login, not held, not emergency or IT.
    if not session or session["modus"] != "normal" or "holdt_sekunder_igjen" in session:
        print("Journalsystemet krever vanlig innlogging med helsepersonellkort.", file=sys.stderr)
        return 1
    command = js.rdp_command(system) if system.type == "rdp" else ["medicus-nettleser", system.url]
    os.execvp(command[0], command)


def apply() -> int:
    from medicus.audit import AuditLog

    try:
        systems = js.load()
    except js.ConfigError as e:
        print(f"Endringen er ikke tatt i bruk: {e}")
        return 1
    hosts = {host for s in systems for host, _ in s.endpoints()}
    addresses = {host: js.resolve(host, 443) for host in hosts}
    for host, ips in addresses.items():
        if not ips:
            print(f"Advarsel: fant ingen adresse for {host} (DNS). Prøver igjen om 30 minutter.")
    hosts_text = js.hosts_file(js.HOSTS.read_text(encoding="utf-8"), addresses)
    tmp = js.HOSTS.with_suffix(".medicus-tmp")
    tmp.write_text(hosts_text, encoding="utf-8")
    os.chmod(tmp, 0o644)
    tmp.replace(js.HOSTS)
    subprocess.run(["nft", "-f", "-"], input=js.nft_script(addresses, systems), text=True, check=True)

    # Web systems: the web filter allows exactly their host names, in addition to the approved websites.
    PROXY_FILTER.write_text(nettsteder.proxy_filter() + js.proxy_filter(systems), encoding="utf-8")
    subprocess.run(["systemctl", "try-restart", "tinyproxy.service"], check=False)

    js.APPLICATIONS.mkdir(parents=True, exist_ok=True)
    wanted = {f"medicus-journalsystem-{s.slug}.desktop": js.desktop_entry(s) for s in systems}
    for old in js.APPLICATIONS.glob("medicus-journalsystem-*.desktop"):
        if old.name not in wanted:
            old.unlink()
    for name, text in wanted.items():
        (js.APPLICATIONS / name).write_text(text, encoding="utf-8")
        os.chmod(js.APPLICATIONS / name, 0o755)  # like the other Medicus launchers

    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AuditLog(AUDIT).record(os.getenv("SUDO_USER", "system"), "journalsystems_applied",
                           {"systems": [s.navn for s in systems], "addresses": addresses})
    print(f"{len(systems)} journalsystem(er) i bruk.")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        try:
            show()
        except js.ConfigError as e:
            print(e)
            return 1
        return 0
    if argv[0] == "start" and len(argv) == 2:
        try:
            return start(argv[1])
        except js.ConfigError as e:
            print(e, file=sys.stderr)
            return 1
    if argv == ["oppdater"]:
        if os.geteuid() != 0:
            print("Endringer krever IT-kortet. Skriv PIN-koden når du blir spurt.")
            os.execvp("sudo", ["sudo", COMMAND, "oppdater"])
        return apply()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
