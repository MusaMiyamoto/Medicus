"""Medical USB devices approved by IT: dictation microphones, spirometers, ECG, dermatoscopes and so on.

The USB lock (USBGuard) only lets in keyboards, mice, headsets, hubs and card readers. Anything
else is blocked until IT approves it here, by its IDs:

    unit     vendor:product + serial number   "this one SpeechMike"           (the default)
    model    vendor:product                   "every SpeechMike of this model"
    vendor   vendor:*                         "everything from this maker"    (use sparingly)

A unit or model may only use the interfaces it had when it was approved (USBGuard "match-all"),
so it can't later turn into something else. Nothing approved may ever be storage (a memory stick),
a network adapter or a wireless adapter: such devices are refused, and vendor rules exclude them.

The approved list is /etc/medicus/medisinsk-utstyr.json. The USBGuard rules are made from it,
never written by hand. The `medicus-utstyr` command (utstyr/__main__.py) is how IT uses this.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

APPROVED = Path("/etc/medicus/medisinsk-utstyr.json")
RULES = Path("/etc/usbguard/rules.d/50-medisinsk-utstyr.conf")
SYSFS = Path("/sys/bus/usb/devices")

# USB interface classes that are never allowed, whatever IT approves.
FORBIDDEN = {"08": "lagring (minnepinne eller disk)", "02": "nettverk eller modem", "0a": "nettverk eller modem",
             "e0": "trådløst (Bluetooth)"}
# Allowed for everyone by rules.conf: headset, keyboard/mouse, hub, card reader.
BASE_POLICY = {"01", "03", "09", "0b"}

HEX4 = re.compile(r"^[0-9a-f]{4}$")
SERIAL = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
INTERFACE = re.compile(r"^[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}$")


@dataclass
class Device:
    port: str                 # where it is plugged in, e.g. "1-2"
    vendor: str               # idVendor, 4 hex digits
    product: str              # idProduct
    name: str = ""
    serial: str = ""
    interfaces: list[str] = field(default_factory=list)  # "class:subclass:protocol"
    authorized: bool = False


def interfaces_from(descriptors: bytes) -> list[str]:
    """The interface types in a device's raw USB descriptors (sysfs "descriptors").
    Read from the descriptors because a blocked device has no interface folders in sysfs."""
    found, i = [], 0
    while i + 1 < len(descriptors):
        length, kind = descriptors[i], descriptors[i + 1]
        if length < 2:
            break
        if kind == 4 and length >= 9 and i + 8 <= len(descriptors):  # interface descriptor
            found.append(f"{descriptors[i + 5]:02x}:{descriptors[i + 6]:02x}:{descriptors[i + 7]:02x}")
        i += length
    return sorted(set(found))


def connected(sysfs: Path = SYSFS) -> list[Device]:
    def read(folder, name):
        try:
            return (folder / name).read_text(errors="replace").strip()
        except OSError:
            return ""

    devices = []
    for folder in sorted(sysfs.glob("*")):
        if not re.fullmatch(r"\d+-[\d.]+", folder.name):  # skip root hubs and interfaces
            continue
        try:
            raw = (folder / "descriptors").read_bytes()
        except OSError:
            raw = b""
        name = " ".join(x for x in (read(folder, "manufacturer"), read(folder, "product")) if x)
        devices.append(Device(folder.name, read(folder, "idVendor").lower(), read(folder, "idProduct").lower(),
                              name, read(folder, "serial"), interfaces_from(raw), read(folder, "authorized") == "1"))
    return devices


def forbidden(interfaces: list[str]) -> list[str]:
    """What is wrong with these interfaces, in words. Empty if nothing is."""
    return sorted({FORBIDDEN[i[:2]] for i in interfaces if i[:2] in FORBIDDEN})


def load(path: Path = APPROVED) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def save(entries: list[dict], path: Path = APPROVED):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o644)
    tmp.replace(path)


def _one_line(text: str) -> str:
    return " ".join(str(text).split())[:80]  # it goes into a comment in the rules file


def _clean_name(name: str) -> str:
    name = _one_line(name)
    if len(name) < 3:
        raise ValueError("Gi utstyret et navn, for eksempel «Diktermikrofon, kontor 3».")
    return name


def _next_number(entries):
    return max((e["nr"] for e in entries), default=0) + 1


def approve(entries: list[dict], device: Device, name: str, who: str, today: str, whole_model: bool = False) -> dict:
    """Approve a connected device (this unit, or with whole_model every unit of the model)."""
    if not (HEX4.match(device.vendor) and HEX4.match(device.product)):
        raise ValueError("Enheten har ugyldige ID-er.")
    if not device.interfaces:
        raise ValueError("Fant ikke enhetens grensesnitt. Koble den fra og til igjen, og prøv på nytt.")
    if problems := forbidden(device.interfaces):
        raise ValueError(f"Kan ikke godkjennes: enheten er også {', '.join(problems)}.")
    serial = ""
    if not whole_model:
        if not SERIAL.match(device.serial):
            raise ValueError("Enheten har ikke et brukbart serienummer. Godkjenn hele modellen i stedet (--hele-modellen).")
        serial = device.serial
    entry = {"nr": _next_number(entries), "navn": _clean_name(name), "leverandor": device.vendor,
             "produkt": device.product, "serienummer": serial, "grensesnitt": device.interfaces,
             "godkjent_av": who, "dato": today}
    entries.append(entry)
    return entry


def approve_vendor(entries: list[dict], vendor: str, name: str, who: str, today: str) -> dict:
    """Approve everything from one maker. Storage, network and wireless are still never allowed."""
    vendor = vendor.lower()
    if not HEX4.match(vendor):
        raise ValueError("Leverandør-ID er fire tegn, 0-9 og a-f, for eksempel 0911.")
    entry = {"nr": _next_number(entries), "navn": _clean_name(name), "leverandor": vendor, "produkt": "*",
             "serienummer": "", "grensesnitt": [], "godkjent_av": who, "dato": today}
    entries.append(entry)
    return entry


def remove(entries: list[dict], number: int) -> dict:
    for entry in entries:
        if entry["nr"] == number:
            entries.remove(entry)
            return entry
    raise ValueError(f"Fant ingen godkjenning med nummer {number}.")


def rule(entry: dict) -> str:
    """One USBGuard rule. Every value is checked again here, so a hand-edited list can't inject rules."""
    vendor, product, serial = entry["leverandor"], entry["produkt"], entry["serienummer"]
    if not HEX4.match(vendor) or not (product == "*" or HEX4.match(product)):
        raise ValueError(f"Ugyldig ID i godkjenning {entry['nr']}.")
    if product == "*":
        blocked = " ".join(f"{c}:*:*" for c in sorted(FORBIDDEN))
        return f"allow id {vendor}:* with-interface none-of {{ {blocked} }}"
    interfaces = entry["grensesnitt"]
    if not interfaces or not all(INTERFACE.match(i) for i in interfaces) or forbidden(interfaces):
        raise ValueError(f"Ugyldige grensesnitt i godkjenning {entry['nr']}.")
    if serial and not SERIAL.match(serial):
        raise ValueError(f"Ugyldig serienummer i godkjenning {entry['nr']}.")
    serial_part = f' serial "{serial}"' if serial else ""
    return f"allow id {vendor}:{product}{serial_part} with-interface match-all {{ {' '.join(interfaces)} }}"


def rules_text(entries: list[dict]) -> str:
    lines = ["# Laget av medicus-utstyr fra /etc/medicus/medisinsk-utstyr.json. Ikke rediger for hånd.", ""]
    for entry in entries:
        lines += [f"# {entry['nr']}. {_one_line(entry['navn'])} – godkjent av {_one_line(entry['godkjent_av'])} "
                  f"{entry['dato']}", rule(entry)]
    return "\n".join(lines) + "\n"


def write_rules(entries: list[dict], path: Path = RULES):
    """USBGuard refuses rule files that others can read or write, so 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(rules_text(entries), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def approval_for(device: Device, entries: list[dict]) -> dict | None:
    for e in entries:
        if e["leverandor"] != device.vendor or e["produkt"] not in ("*", device.product):
            continue
        if e["serienummer"] and e["serienummer"] != device.serial:
            continue
        if e["produkt"] == "*" and not forbidden(device.interfaces):
            return e
        if e["produkt"] != "*" and set(device.interfaces) <= set(e["grensesnitt"]):
            return e
    return None


def status(device: Device, entries: list[dict]) -> str:
    if approval := approval_for(device, entries):
        return f"godkjent (nr. {approval['nr']}: {approval['navn']})"
    if device.interfaces and {i[:2] for i in device.interfaces} <= BASE_POLICY:
        return "tillatt (tastatur, mus, hodesett eller kortleser)"
    return "blokkert"
