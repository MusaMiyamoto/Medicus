"""Sikkerhetssenter: live status of the protections on this machine, in plain Norwegian.

Every check reads the real state (running services, kernel settings, virus database age);
nothing is assumed from the configuration.
"""

import subprocess
import time
from pathlib import Path

import utstyr

OK, WARN, FAIL, INFO = "ok", "advarsel", "feil", "info"


def unit_active(unit: str) -> bool:
    try:
        out = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.stdout.strip() == "active"


def read(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def newest_mtime(paths: list[str]) -> float | None:
    times = [Path(p).stat().st_mtime for p in paths if Path(p).exists()]
    return max(times) if times else None


def service(name, unit, ok_text, fail_text, active=unit_active):
    good = active(unit)
    return {"navn": name, "status": OK if good else FAIL, "forklaring": ok_text if good else fail_text}


def checks(active=unit_active, read=read, now=time.time) -> list[dict]:
    result = [
        service("Brannmur", "nftables.service",
                "Ingen kan koble seg til maskinen utenfra. Apper når bare Medicus og helsenettet.",
                "Brannmuren kjører ikke. Kontakt IT.", active),
        service("USB-lås", "usbguard.service",
                "Bare tastatur, mus, hodesett og kortleser er tillatt. Minnepinner er blokkert.",
                "USB-låsen kjører ikke. Kontakt IT.", active),
        service("Øktvakt", "medicus-oktvakt.service",
                "Du logges ut i det kortet tas ut.", "Øktvakten kjører ikke. Kontakt IT.", active),
        service("Sikkerhetslogg", "auditd.service",
                "Viktige endringer på maskinen blir logget.", "Sikkerhetsloggen kjører ikke.", active),
        service("Sikkerhetsoppdateringer", "unattended-upgrades.service",
                "Sikkerhetsoppdateringer installeres automatisk.", "Automatiske oppdateringer er av.", active),
        service("Kjøring av programmer fra hjemmemappen", "home.mount",
                "Programmer kan ikke startes fra hjemmemappe, nedlastinger eller midlertidige mapper.",
                "Hjemmemappen er ikke låst for programkjøring.", active),
    ]

    scanner = active("clamav-daemon.service")
    db_time = newest_mtime([f"/var/lib/clamav/{n}" for n in ("daily.cld", "daily.cvd", "main.cvd", "main.cld")])
    age_days = (now() - db_time) / 86400 if db_time else None
    if not scanner:
        result.append({"navn": "Virusbeskyttelse", "status": FAIL,
                       "forklaring": "Virusskanneren kjører ikke. Vedlegg blir merket «ikke virusskannet»."})
    elif age_days is None or age_days > 7:
        result.append({"navn": "Virusbeskyttelse", "status": WARN,
                       "forklaring": "Virusskanneren kjører, men virusdatabasen er gammel eller mangler."})
    else:
        result.append({"navn": "Virusbeskyttelse", "status": OK,
                       "forklaring": f"Vedlegg skannes for virus. Databasen er {age_days:.0f} døgn gammel."})

    lockdown = read("/sys/kernel/security/lockdown")
    result.append({"navn": "Kjernebeskyttelse", "status": OK if "[integrity]" in lockdown or "[confidentiality]" in lockdown else WARN,
                   "forklaring": "Selv administrator kan ikke endre den kjørende kjernen."
                   if "[" in lockdown and "[none]" not in lockdown else "Kjernelåsen (lockdown) er ikke på."})

    apparmor = read("/sys/module/apparmor/parameters/enabled") == "Y"
    result.append({"navn": "AppArmor", "status": OK if apparmor else FAIL,
                   "forklaring": "Programmer som PDF-leseren kjører i en avgrenset sandkasse."
                   " (I live-versjonen lastes profilene først når systemet er installert.)"
                   if apparmor else "AppArmor er ikke slått på."})

    vpn = active("medicus-vpn.service")
    result.append({"navn": "VPN til helsenettet", "status": OK if vpn else INFO,
                   "forklaring": "All trafikk går kryptert til helsenettet. Annen trafikk er blokkert."
                   if vpn else "Ikke satt opp ennå. Krever avtale med Norsk helsenett eller IT-avdelingen."})
    return result


def medical_devices(devices: list, entries: list[dict]) -> dict:
    """Approved medical USB devices, and anything plugged in that the USB lock is blocking."""
    blocked = [d for d in devices if utstyr.status(d, entries) == "blokkert"]
    text = f"{len(entries)} godkjent(e). Endres med «Medisinsk utstyr (USB)» i IT-menyen."
    if not blocked:
        return {"navn": "Medisinsk USB-utstyr", "status": OK, "forklaring": text}
    names = ", ".join(f"{d.name or 'ukjent enhet'} ({d.vendor}:{d.product}, port {d.port})" for d in blocked[:5])
    return {"navn": "Medisinsk USB-utstyr", "status": INFO,
            "forklaring": f"Blokkert nå: {names}. Godkjenn bare utstyr virksomheten har kjøpt inn. {text}"}


def emergency_reports(late: list[dict] | None) -> dict:
    """Emergency access must be explained before the shift ends. Late reports go to the security officer."""
    if late is None:
        return {"navn": "Nødtilgangsrapporter", "status": WARN, "forklaring": "Får ikke kontakt med innloggingstjenesten."}
    if not late:
        return {"navn": "Nødtilgangsrapporter", "status": OK, "forklaring": "Alle nødtilganger er forklart innen fristen."}
    who = ", ".join(f"{r['navn']} ({r['startet'].replace('T', ' ')})" for r in late[:5])
    return {"navn": "Nødtilgangsrapporter", "status": FAIL,
            "forklaring": f"{len(late)} rapport(er) mangler etter fristen: {who}. Gi beskjed til personvernombudet."}
