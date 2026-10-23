"""Machine certificate in the TPM, and the WLANs IT has approved (802.1X EAP-TLS).

Each Medicus PC proves who it is to the Wi-Fi with a certificate, not a password:

1. `nokkel`      makes a private key *inside* the TPM chip. It can be used, but never copied out,
                 so a cloned disk or a copied file is useless on another machine.
2. `foresporsel` makes a certificate request (CSR) for that key. IT signs it in the organisation's
                 own certificate authority (CA).
3. `sertifikat`  installs the signed certificate and the CA, after checking it belongs to the TPM key.
4. `legg-til`    approves one WLAN: the PC joins it with EAP-TLS, and only if the network's RADIUS
                 server has a certificate from the same CA with the expected name. So the PC won't
                 talk to a fake access point with the same network name.

Health personnel can't add or change networks (polkit, etc/polkit-1/rules.d/90-medicus.rules), so
these are the only Wi-Fi networks the PC uses. The key is reached through PKCS#11 (tpm2-pkcs11);
NetworkManager hands wpa_supplicant a pkcs11: address, never the key itself.

This needs real hardware with TPM 2.0 and a RADIUS server set up for EAP-TLS; test there first.
"""

import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

TPM_DEVICE = Path("/dev/tpmrm0")
FOLDER = Path("/etc/medicus/tpm")          # root only: the TPM token store and its PIN
CERT = Path("/etc/medicus/maskinsertifikat.crt")  # public, so the Sikkerhetssenter can read the expiry date
CA = Path("/etc/medicus/wlan-ca.crt")
APPROVED = Path("/etc/medicus/wlan.json")
CONNECTIONS = Path("/etc/NetworkManager/system-connections")
TOKEN, KEY = "medicus", "maskin"
KEY_URI = f"pkcs11:token={TOKEN};object={KEY};type=private"
WARN_DAYS = 30

DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def module_path() -> str:
    """Where Debian puts the tpm2-pkcs11 module (the folder name depends on the CPU type)."""
    found = sorted(Path("/usr/lib").glob("*/pkcs11/libtpm2_pkcs11.so*"))
    return str(found[0]) if found else "/usr/lib/x86_64-linux-gnu/pkcs11/libtpm2_pkcs11.so.1"


def check_ssid(ssid: str) -> str:
    if not 1 <= len(ssid.encode("utf-8")) <= 32 or any(ord(c) < 32 or c in "\\;" for c in ssid):
        raise ValueError("Ugyldig nettverksnavn (SSID): 1–32 tegn, uten kontrolltegn.")
    return ssid


def check_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if not DOMAIN.match(domain):
        raise ValueError("Skriv navnet på RADIUS-serveren, for eksempel radius.sykehuset.no.")
    return domain


def connection_file(ssid: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", ssid)
    return CONNECTIONS / f"medicus-wlan-{safe}.nmconnection"


WIRED_FILE = CONNECTIONS / "medicus-kablet.nmconnection"
WIRED_NAME = "Medicus: kablet nett"


def _eap_tls(server: str, identity: str, pin: str) -> list[str]:
    """The 802.1X part: the PC proves itself with the TPM key, and checks the network's RADIUS server."""
    server = check_domain(server)
    if not re.fullmatch(r"[A-Za-z0-9._/@-]{1,128}", identity) or not re.fullmatch(r"[A-Za-z0-9]{8,64}", pin):
        raise ValueError("Ugyldig identitet eller PIN.")
    return ["", "[802-1x]", "eap=tls;", f"identity={identity}",
            f"ca-cert={CA}", f"domain-suffix-match={server}",
            f"client-cert={CERT}", f"private-key={KEY_URI}",
            f"private-key-password={pin}", "private-key-password-flags=0",
            "", "[ipv4]", "method=auto", "", "[ipv6]", "method=auto", ""]


def keyfile(ssid: str, server: str, identity: str, pin: str, uid: str | None = None) -> str:
    """A NetworkManager connection for one approved WLAN, with the key in the TPM."""
    ssid = check_ssid(ssid)
    return "\n".join([
        "# Laget av medicus-wlan. Endres med medicus-wlan, ikke for hånd.",
        "[connection]", f"id=Medicus: {ssid}", f"uuid={uid or uuid.uuid4()}", "type=wifi", "autoconnect=true",
        "", "[wifi]", "mode=infrastructure", f"ssid={ssid}",
        "", "[wifi-security]", "key-mgmt=wpa-eap", "pmf=3",  # protected management frames required
        *_eap_tls(server, identity, pin),
    ])


def wired_keyfile(server: str, identity: str, pin: str, uid: str | None = None) -> str:
    """Wired 802.1X on every network port, with the key in the TPM. The switch asks the RADIUS server,
    which puts this PC on the clinical VLAN because of its certificate (a PC without one gets the guest
    VLAN or nothing). Higher priority than NetworkManager's automatic wired profile."""
    return "\n".join([
        "# Laget av medicus-wlan. Endres med medicus-wlan, ikke for hånd.",
        "[connection]", f"id={WIRED_NAME}", f"uuid={uid or uuid.uuid4()}", "type=ethernet", "autoconnect=true",
        "autoconnect-priority=100",
        "", "[ethernet]",
        *_eap_tls(server, identity, pin),
    ])


def load(path: Path = APPROVED) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def save(entries: list[dict], path: Path = APPROVED):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o644)
    tmp.replace(path)


def write_private(path: Path, text: str):
    """Root-only file (NetworkManager refuses connection files others can read)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(path)


def new_pin() -> str:
    return secrets.token_hex(16)


def parse_enddate(openssl_output: str) -> datetime:
    """`openssl x509 -noout -enddate` prints e.g. notAfter=Oct 24 12:00:00 2027 GMT."""
    value = openssl_output.strip().split("=", 1)[-1]
    return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def certificate_status(tpm: bool, end: datetime | None, wlans: int, now: datetime | None = None) -> dict:
    """The Sikkerhetssenter line."""
    name = "Maskinsertifikat (TPM) og WLAN"
    now = now or datetime.now(timezone.utc)
    if not tpm:
        return {"navn": name, "status": "info", "forklaring": "Maskinen har ingen TPM 2.0. Bruk kablet nett eller VPN."}
    if end is None:
        return {"navn": name, "status": "info",
                "forklaring": "Ikke satt opp. IT lager nøkkel og sertifikat med medicus-wlan (se IT-håndboken)."}
    days = (end - now).days
    if days < 0:
        return {"navn": name, "status": "feil", "forklaring": "Sertifikatet er utløpt: maskinen kommer ikke på WLAN. Lag et nytt."}
    if days < WARN_DAYS:
        return {"navn": name, "status": "advarsel", "forklaring": f"Sertifikatet utløper om {days} dager. Lag et nytt."}
    return {"navn": name, "status": "ok",
            "forklaring": f"Nøkkelen er i TPM-brikken. Sertifikatet gjelder til {end:%d.%m.%Y}. {wlans} godkjent(e) WLAN."}
