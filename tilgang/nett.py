"""Is this PC on the hospital's clinical network? Checked by medicus-authd itself at login.

The card proves who you are. This proves where the PC is, so a stolen laptop, or a PC moved to a
café or a guest network, can't open patient records even if someone gets past the card:

  1. The PC must be connected through one of Medicus' own 802.1X profiles ("Medicus: …", made by
     medicus-wlan). Those log in to the network with the machine certificate whose key is inside
     the TPM, so the network itself has checked this exact PC. The site's RADIUS server then puts it
     on the clinical VLAN; a PC without the certificate lands on a guest VLAN, or nowhere.
  2. The PC must have an address in one of the site's clinical subnets (arbeidssted.toml, `nett`).
     That is the VLAN the RADIUS server gave it, so a look-alike network with the same name doesn't count.

Sites with no `nett` in arbeidssted.toml are not checked (the simulated demo, and PCs IT hasn't set up yet).

Mobile PCs (`profil = "mobil"`: home nursing, ambulance, on-call) are never on the ward network. For them
the always-on VPN to the health network counts instead of step 1: the WireGuard tunnel `helsenett` is up
AND its kill switch blocks every other way out (medicus-vpn). Step 2 still applies: the tunnel's address
must be in the site's `nett` list (the hospital's VPN range), which only a configured tunnel gets.
"""

import ipaddress
import json
import subprocess
from dataclasses import dataclass

PROFILE_PREFIX = "Medicus: "
VPN_INTERFACE = "helsenett"
KILL_SWITCH = ("inet", "medicus_killswitch")


@dataclass(frozen=True)
class Network:
    addresses: tuple[str, ...] = ()
    certified: bool = False  # connected through a Medicus 802.1X profile (TPM machine certificate)
    vpn: bool = False  # the VPN tunnel to the health network is up, with the kill switch on


def read(run=subprocess.run) -> Network:
    """Read the current state from the kernel and NetworkManager. Anything unreadable counts as 'not on'."""
    addresses = []
    out = run(["ip", "-j", "address", "show", "scope", "global"], capture_output=True, text=True, check=False)
    try:
        for link in json.loads(out.stdout or "[]"):
            addresses += [a["local"] for a in link.get("addr_info", []) if "local" in a]
    except (json.JSONDecodeError, TypeError, AttributeError):
        addresses = []
    out = run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"], capture_output=True, text=True,
              check=False)
    names = [line.replace("\\:", ":") for line in (out.stdout or "").splitlines()]
    return Network(tuple(addresses), any(name.startswith(PROFILE_PREFIX) for name in names), vpn_up(run))


def vpn_up(run=subprocess.run) -> bool:
    out = run(["ip", "-j", "link", "show", VPN_INTERFACE], capture_output=True, text=True, check=False)
    try:
        links = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return False
    # A WireGuard link says UP in its flags (its operstate is UNKNOWN by design).
    if not (links and "UP" in links[0].get("flags", [])):
        return False
    out = run(["nft", "list", "table", *KILL_SWITCH], capture_output=True, text=True, check=False)
    return out.returncode == 0


def check_subnets(values) -> tuple[str, ...]:
    """IT's list of clinical subnets, e.g. ["10.20.0.0/16", "2001:db8:20::/48"]. Raises ValueError."""
    return tuple(str(ipaddress.ip_network(str(v), strict=True)) for v in values)


def on_clinical_network(net: Network, subnets: tuple[str, ...], mobile: bool = False) -> bool:
    if not subnets:
        return True
    if not (net.certified or (mobile and net.vpn)):
        return False
    networks = [ipaddress.ip_network(s) for s in subnets]
    for address in net.addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if any(ip.version == n.version and ip in n for n in networks):
            return True
    return False
