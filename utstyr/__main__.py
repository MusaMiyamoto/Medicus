"""medicus-utstyr: approve medical USB devices (IT mode). See utstyr/__init__.py for the rules.

    medicus-utstyr                                    show connected devices and the approved list
    medicus-utstyr godkjenn PORT --navn "..."         approve this unit (by serial number)
    medicus-utstyr godkjenn PORT --navn "..." --hele-modellen
    medicus-utstyr leverandor VVVV --navn "..."       approve everything from one maker
    medicus-utstyr fjern NR                           remove an approval
    medicus-utstyr meny                               step by step (from the IT menu)

Changes need root: the command runs itself again through sudo, which asks for the IT card's PIN.
"""

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import utstyr
from medicus.audit import AuditLog

COMMAND = "/usr/local/bin/medicus-utstyr"
AUDIT = Path("/var/lib/medicus-utstyr/audit.jsonl")


def show(devices, entries):
    print("Tilkoblet USB-utstyr:")
    if not devices:
        print("  (ingenting)")
    for d in devices:
        print(f"  [{d.port}] {d.name or 'Ukjent enhet'}  {d.vendor}:{d.product}"
              f"{'  serienr. ' + d.serial if d.serial else ''}")
        print(f"         {utstyr.status(d, entries)}   grensesnitt: {' '.join(d.interfaces) or 'ukjent'}")
    print("\nGodkjent medisinsk utstyr:")
    if not entries:
        print("  (ingenting)")
    for e in entries:
        scope = ("alt fra leverandøren" if e["produkt"] == "*" else
                 f"serienr. {e['serienummer']}" if e["serienummer"] else "hele modellen")
        print(f"  {e['nr']}. {e['navn']}  {e['leverandor']}:{e['produkt']}  ({scope}; {e['godkjent_av']}, {e['dato']})")


def apply(entries, action, details):
    """Save the list, write the USBGuard rules and restart USBGuard so they take effect now."""
    utstyr.save(entries)
    utstyr.write_rules(entries)
    who = os.getenv("SUDO_USER", "root")
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AuditLog(AUDIT).record(who, action, details)
    result = subprocess.run(["systemctl", "restart", "usbguard"], capture_output=True, text=True)
    if result.returncode != 0:
        print("ADVARSEL: USB-låsen startet ikke igjen. Sjekk: sudo journalctl -u usbguard -n 30")
        return 1
    print("Lagret. USB-låsen bruker de nye reglene nå.")
    return 0


def as_root():
    if os.geteuid() != 0:
        print("Endringer krever IT-kortet. Skriv PIN-koden når du blir spurt.")
        os.execvp("sudo", ["sudo", COMMAND, *sys.argv[1:]])


def menu():
    while True:
        devices, entries = utstyr.connected(), utstyr.load()
        print()
        show(devices, entries)
        choice = input("\nSkriv porten (for eksempel 1-2) for å godkjenne en enhet, f for å fjerne en "
                       "godkjenning, eller Enter for å avslutte: ").strip()
        if not choice:
            return 0
        if choice.lower() == "f":
            number = input("Nummeret på godkjenningen som skal fjernes: ").strip()
            subprocess.run(["sudo", COMMAND, "fjern", number])
            continue
        if not any(d.port == choice for d in devices):
            print("Fant ingen enhet i den porten.")
            continue
        name = input("Navn på utstyret (for eksempel «Spirometer, legekontor 2»): ").strip()
        model = input("Godkjenne bare denne enheten (serienummeret)? [J/n]: ").strip().lower() in ("n", "nei")
        subprocess.run(["sudo", COMMAND, "godkjenn", choice, "--navn", name, *(["--hele-modellen"] if model else [])])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="medicus-utstyr", description="Godkjenn medisinsk USB-utstyr.")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("godkjenn")
    p.add_argument("port")
    p.add_argument("--navn", required=True)
    p.add_argument("--hele-modellen", action="store_true")
    p = sub.add_parser("leverandor")
    p.add_argument("leverandor")
    p.add_argument("--navn", required=True)
    p = sub.add_parser("fjern")
    p.add_argument("nr", type=int)
    sub.add_parser("meny")
    args = parser.parse_args(argv)

    if args.cmd is None:
        show(utstyr.connected(), utstyr.load())
        return 0
    if args.cmd == "meny":
        return menu()
    as_root()
    entries, who, today = utstyr.load(), os.getenv("SUDO_USER", "root"), date.today().isoformat()
    try:
        if args.cmd == "godkjenn":
            device = next((d for d in utstyr.connected() if d.port == args.port), None)
            if device is None:
                raise ValueError(f"Fant ingen enhet i port {args.port}. Kjør medicus-utstyr for å se portene.")
            entry = utstyr.approve(entries, device, args.navn, who, today, args.hele_modellen)
            return apply(entries, "usb_device_approved", entry)
        if args.cmd == "leverandor":
            entry = utstyr.approve_vendor(entries, args.leverandor, args.navn, who, today)
            return apply(entries, "usb_vendor_approved", entry)
        entry = utstyr.remove(entries, args.nr)
        return apply(entries, "usb_approval_removed", entry)
    except ValueError as e:
        print(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
