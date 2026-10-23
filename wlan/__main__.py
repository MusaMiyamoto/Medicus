"""medicus-wlan: machine certificate in the TPM and approved WLANs (IT mode). See wlan/__init__.py.

    medicus-wlan                                       status
    medicus-wlan nokkel                                make the key inside the TPM (once per PC)
    medicus-wlan foresporsel [--navn pc01.sykehuset.no]   certificate request for IT's CA
    medicus-wlan sertifikat maskin.crt ca.crt          install the signed certificate
    medicus-wlan legg-til SSID --server radius.sykehuset.no
    medicus-wlan fjern SSID
    medicus-wlan kablet --server radius.sykehuset.no    wired 802.1X with the same certificate (--av removes it)

Changes need root: the command runs itself again through sudo, which asks for the IT card's PIN.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import wlan
from medicus.audit import AuditLog

COMMAND = "/usr/local/bin/medicus-wlan"
AUDIT = Path("/var/lib/medicus-wlan/audit.jsonl")
STORE = wlan.FOLDER / "store"
PIN = wlan.FOLDER / "pin"
CERT, CA, CSR = wlan.CERT, wlan.CA, wlan.FOLDER / "maskin.csr"


def run(*command, **kwargs) -> str:
    env = {**os.environ, "TPM2_PKCS11_STORE": str(STORE), "PKCS11_PROVIDER_MODULE": wlan.module_path()}
    result = subprocess.run(command, capture_output=True, text=True, env=env, **kwargs)
    if result.returncode != 0:
        raise ValueError(f"{command[0]} feilet: {(result.stderr or result.stdout).strip()[:400]}")
    return result.stdout


def log(action, details):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AuditLog(AUDIT).record(os.getenv("SUDO_USER", "root"), action, details)


def certificate_end() -> datetime | None:
    try:
        return wlan.parse_enddate(run("openssl", "x509", "-in", str(CERT), "-noout", "-enddate")) if CERT.exists() else None
    except (ValueError, OSError):
        return None


def status():
    tpm = wlan.TPM_DEVICE.exists()
    print("TPM 2.0:", "ja" if tpm else "nei – maskinen kan ikke bruke maskinsertifikat i TPM")
    if os.geteuid() == 0:  # the key folder is root-only
        print("Nøkkel i TPM:", "ja" if PIN.exists() else "nei (medicus-wlan nokkel)")
    end = certificate_end()
    print("Sertifikat:", f"gjelder til {end:%d.%m.%Y}" if end else "ikke installert")
    print("Kablet 802.1X:", "ja" if wlan.WIRED_FILE.exists() else "nei (medicus-wlan kablet --server …)")
    print("\nGodkjente WLAN:")
    for e in wlan.load() or [{"ssid": "(ingen)", "server": "", "dato": ""}]:
        print(f"  {e['ssid']}  {('RADIUS: ' + e['server']) if e['server'] else ''}  {e['dato']}")


def make_key(args):
    if not wlan.TPM_DEVICE.exists():
        raise ValueError("Maskinen har ingen TPM 2.0 (fant ikke /dev/tpmrm0). Slå på TPM i BIOS/UEFI.")
    if PIN.exists() and not args.ny:
        raise ValueError("Maskinen har allerede en nøkkel. Bruk --ny for å lage en ny (da må sertifikatet lages på nytt).")
    if STORE.exists():
        shutil.rmtree(STORE)
    STORE.mkdir(parents=True, mode=0o700)
    os.chmod(wlan.FOLDER, 0o700)
    output = run("tpm2_ptool", "init", f"--path={STORE}")
    pid = next((line.split(":")[1].strip() for line in output.splitlines() if line.strip().startswith("id:")), "1")
    pin, so_pin = wlan.new_pin(), wlan.new_pin()
    run("tpm2_ptool", "addtoken", f"--pid={pid}", f"--label={wlan.TOKEN}", f"--sopin={so_pin}",
        f"--userpin={pin}", f"--path={STORE}")
    run("tpm2_ptool", "addkey", f"--label={wlan.TOKEN}", f"--key-label={wlan.KEY}", f"--userpin={pin}",
        "--algorithm=ecc256", f"--path={STORE}")
    # The PIN only unlocks the key on this TPM; it is useless anywhere else.
    wlan.write_private(PIN, pin)
    log("tpm_key_created", {"algorithm": "ecc256"})
    print("Nøkkelen er laget i TPM-brikken. Neste steg: medicus-wlan foresporsel")


def make_request(args):
    if not PIN.exists():
        raise ValueError("Lag nøkkelen først: medicus-wlan nokkel")
    name = args.navn or socket.getfqdn()
    if not wlan.DOMAIN.match(name.lower()) and not name.isalnum():
        raise ValueError("Ugyldig maskinnavn.")
    key = f"{wlan.KEY_URI}?pin-value={PIN.read_text().strip()}"
    run("openssl", "req", "-new", "-provider", "pkcs11", "-provider", "default", "-key", key,
        "-subj", f"/CN={name}", "-out", str(CSR))
    log("tpm_csr_created", {"name": name})
    print(f"Forespørselen er i {CSR}. Gi den til den som driver virksomhetens CA, og installer svaret med\n"
          f"  sudo medicus-wlan sertifikat maskin.crt ca.crt\n")
    print(CSR.read_text())


def install_certificate(args):
    if not CSR.exists():
        raise ValueError("Fant ingen forespørsel. Kjør medicus-wlan foresporsel først.")
    cert_key = run("openssl", "x509", "-in", args.sertifikat, "-noout", "-pubkey")
    if cert_key != run("openssl", "req", "-in", str(CSR), "-noout", "-pubkey"):
        raise ValueError("Sertifikatet hører ikke til nøkkelen i denne maskinens TPM.")
    run("openssl", "verify", "-CAfile", args.ca, args.sertifikat)
    end = wlan.parse_enddate(run("openssl", "x509", "-in", args.sertifikat, "-noout", "-enddate"))
    if end <= datetime.now(timezone.utc):
        raise ValueError("Sertifikatet er allerede utløpt.")
    for source, target in ((args.sertifikat, CERT), (args.ca, CA)):
        shutil.copyfile(source, target)
        os.chmod(target, 0o644)
    subject = run("openssl", "x509", "-in", str(CERT), "-noout", "-subject").strip()
    log("tpm_certificate_installed", {"subject": subject, "until": end.isoformat()})
    run("nmcli", "connection", "reload")
    print(f"Installert: {subject}, gjelder til {end:%d.%m.%Y}.")


def add_wlan(args):
    if not CERT.exists():
        raise ValueError("Installer maskinsertifikatet først: medicus-wlan sertifikat")
    identity = f"host/{socket.getfqdn()}"
    text = wlan.keyfile(args.ssid, args.server, identity, PIN.read_text().strip())
    wlan.write_private(wlan.connection_file(args.ssid), text)
    entries = [e for e in wlan.load() if e["ssid"] != args.ssid]
    entries.append({"ssid": args.ssid, "server": wlan.check_domain(args.server), "dato": date.today().isoformat(),
                    "godkjent_av": os.getenv("SUDO_USER", "root")})
    wlan.save(entries)
    log("wlan_approved", {"ssid": args.ssid, "server": args.server})
    run("nmcli", "connection", "reload")
    print(f"«{args.ssid}» er godkjent. Maskinen kobler seg til med sertifikatet når nettet er i nærheten.")


def wired(args):
    """Wired 802.1X with the TPM certificate, or --av to remove it."""
    if args.av:
        wlan.WIRED_FILE.unlink(missing_ok=True)
        log("wired_8021x_removed", {})
        run("nmcli", "connection", "reload")
        print("Kablet 802.1X er fjernet.")
        return
    if not CERT.exists():
        raise ValueError("Installer maskinsertifikatet først: medicus-wlan sertifikat")
    if not args.server:
        raise ValueError("Oppgi RADIUS-serveren: medicus-wlan kablet --server radius.sykehuset.no")
    text = wlan.wired_keyfile(args.server, f"host/{socket.getfqdn()}", PIN.read_text().strip())
    wlan.write_private(wlan.WIRED_FILE, text)
    log("wired_8021x_approved", {"server": args.server})
    run("nmcli", "connection", "reload")
    print("Kablet nett bruker nå maskinsertifikatet (802.1X). Svitsjen plasserer PC-en på riktig VLAN.")


def remove_wlan(args):
    entries = wlan.load()
    if not any(e["ssid"] == args.ssid for e in entries):
        raise ValueError(f"«{args.ssid}» er ikke på listen.")
    wlan.connection_file(args.ssid).unlink(missing_ok=True)
    wlan.save([e for e in entries if e["ssid"] != args.ssid])
    log("wlan_removed", {"ssid": args.ssid})
    run("nmcli", "connection", "reload")
    print(f"«{args.ssid}» er fjernet.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="medicus-wlan", description="Maskinsertifikat i TPM og godkjente WLAN.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("nokkel").add_argument("--ny", action="store_true")
    sub.add_parser("foresporsel").add_argument("--navn")
    p = sub.add_parser("sertifikat")
    p.add_argument("sertifikat")
    p.add_argument("ca")
    p = sub.add_parser("legg-til")
    p.add_argument("ssid")
    p.add_argument("--server", required=True)
    sub.add_parser("fjern").add_argument("ssid")
    p = sub.add_parser("kablet")
    p.add_argument("--server")
    p.add_argument("--av", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd is None:
        status()
        return 0
    if os.geteuid() != 0:
        print("Endringer krever IT-kortet. Skriv PIN-koden når du blir spurt.")
        os.execvp("sudo", ["sudo", COMMAND, *sys.argv[1:]])
    actions = {"nokkel": make_key, "foresporsel": make_request, "sertifikat": install_certificate,
               "legg-til": add_wlan, "fjern": remove_wlan, "kablet": wired}
    try:
        actions[args.cmd](args)
    except (ValueError, OSError) as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
