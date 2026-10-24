# Medicus IT handbook

For the people who keep Medicus running: the IT department and the security team at a health
trust or municipality. You should not need anything else than this handbook and the code to
get started. Inside Medicus it opens from **IT mode → IT-håndbok**.

> Medicus is still a prototype with synthetic data. Real cards, the real health network
> (Norsk helsenett) and real patient data need an agreement and an approval first.

---

## 1. What Medicus is

Medicus is a workstation for health personnel: a hardened Debian 13 Linux with its own login,
its own apps and its own look. It runs **only on machines owned by the health trust,
municipality or another public body**.

There are three ways to log in. They all start with a card in the card reader:

| Mode | Who | How | What they get |
|---|---|---|---|
| **Normal** | Health personnel | Card + PIN | Patient record, Post, journal assistant, browser, tools |
| **Nødtilgang** (emergency) | Health personnel | Card + one tap on the situation, no PIN | Only life-critical information, read-only, 30 minutes |
| **IT mode** | IT staff (cards with role `IT`) | Card + PIN | Sikkerhetssenter, terminal, all settings, task manager, network, this handbook. **Never patient data.** |

The rules behind this:

- **No passwords anywhere.** The card and the PIN are the only way in, also for admin rights.
- **Card out = locked and held.** Taking the card out locks a normal or IT session at once.
  - The session is held for `HOLD_MINUTES` (15) so no work is lost; the same card and PIN resume it.
  - If the card isn't back in time, or someone else logs in, the session ends.
  - Each step is in the audit log: `session_held`, `session_resumed`, and `session_ended` with the
    reason `card_not_returned` or `other_user_logged_in`.
  - Hibernation is masked and RAM encryption is on where the CPU supports it, so a held session never
    reaches the disk.
- **Emergency access must be explained.** The person who opened it must write a short report
  before their shift ends (`REPORT_HOURS`, 12 hours). Late reports show up red in the
  Sikkerhetssenter: tell the data protection officer (personvernombudet).
- **Everything important is logged** with the person's identity, in a hash-chained log that
  shows if someone has edited it.
- **IT staff never see patients.** The web app refuses IT sessions on every patient endpoint.
  IT mode cannot open emergency access.

---

## 2. Where things are

### In the source code (the Git repository)

| Folder | What | Made with |
|---|---|---|
| `tilgang/` | Login: card reader, PIN, sessions, emergency reports, IT mode | Python 3 |
| `tilgang/authd.py` | **medicus-authd**, the one place that decides who is logged in | Python, UNIX socket |
| `tilgang/greeter.py` | The login screen | Python + GTK 4, LightDM |
| `tilgang/pam.py` | The bridge from Linux login (PAM) to medicus-authd | Python |
| `tilgang/sessionguard.py` | **medicus-oktvakt**: ends desktops that have no valid login | Python |
| `tilgang/rydd.py` | Empties home folders when a session closes (PAM) and at boot (`medicus-rydd-hjem.service`) | Python |
| `tilgang/nodrapport.py` | Emergency access reports and their deadline | Python |
| `medicus/` | The web app: patient record, Post, journal assistant, Sikkerhetssenter | Python + FastAPI, plain HTML/CSS/JS |
| `helsenett/` | One interface to the national health services, plus a simulator | Python + FastAPI |
| `epj/` | Journal systems: saving notes, the doctor's patient list, DIPS (FHIR), transfer from Epic | Python |
| `utstyr/` | Medical USB devices approved by IT (`medicus-utstyr`) | Python, USBGuard |
| `wlan/` | Machine certificate in the TPM and approved WLANs (`medicus-wlan`) | Python, tpm2-pkcs11, NetworkManager |
| `journalsystem/` | The hospital's record systems in locked-down windows (`medicus-journalsystem`) | Python, FreeRDP, nftables |
| `nettleser/` | **Nettleser**, the browser (only approved sites) | Python + GTK 4 + WebKitGTK 6 |
| `tekst/`, `kalkulator/` | The Text editor and the calculator | Python + GTK 4 |
| `branding/` | Logo, wallpapers, boot screen; `make_assets.py` builds the images | SVG, Python + Pillow |
| `os/` | Everything that turns Debian into Medicus | Debian live-build, shell, config files |
| `os/build.sh` | Builds the ISO | Shell |
| `os/config/hooks/normal/0100-medicus.hook.chroot` | Runs inside the image while it is built: accounts, groups, locks, services | Shell |
| `os/config/includes.chroot/` | Files copied straight into the system (same paths as on the machine) | Config files |
| `os/config/package-lists/medicus.list.chroot` | Which Debian packages are installed | Text |
| `os/menu.py` | Start menu names and which entries are hidden | Python |
| `tests/` | Automatic tests for all of the above | pytest |

### On a running Medicus machine

| Path | What |
|---|---|
| `/opt/medicus/` | The Python code (the folders above) |
| `/etc/medicus/` | Settings: this PC's workplace, the card file (hashed PINs) |
| `/var/lib/medicus-auth/audit.jsonl` | Security log for logins, emergency access and admin actions |
| `/var/lib/medicus-auth/nodrapporter.json` | Emergency access reports |
| `/var/lib/medicus-auth/pin-forsok.json` | Wrong-PIN counters (blocked cards) |
| `/var/lib/medicus/` | The web app's own log and data |
| `/usr/share/medicus-it/applications/` | The IT tools shown in IT mode |
| `/etc/pam.d/lightdm`, `/etc/pam.d/sudo`, `/etc/pam.d/xfce4-screensaver` | Who may log in, and how |
| `/etc/sudoers.d/medicus-it` | Admin rights for IT staff |
| `/etc/nftables.conf`, `/etc/usbguard/`, `/etc/tinyproxy/filter` | Firewall, USB lock, web filter |
| `/etc/medicus/medisinsk-utstyr.json` | Approved medical USB devices |
| `/etc/medicus/integrasjon.toml` | Health network, journal system (DIPS) and Epic settings |

### Services (systemd)

| Service | What it does | If it stops |
|---|---|---|
| `medicus-auth` | Card, PIN, sessions, reports | Nobody can log in |
| `medicus-oktvakt` | Locks desktops when the card is out; logs out desktops without a valid card login | Card out no longer locks or logs out |
| `medicus` | The web app on 127.0.0.1:8000 | Patient record, Post etc. show an error |
| `medicus-helsenett-sim` | The simulated health network on 127.0.0.1:8100 | No patients (demo only) |
| `medicus-journalsystem.timer` | Refreshes the record systems' addresses and firewall openings every 30 minutes | The record system windows can't connect after an address change |
| `nftables`, `usbguard`, `auditd`, `clamav-daemon`, `tinyproxy` | Firewall, USB lock, system log, virus scan, web filter | Sikkerhetssenter turns red |

---

## 3. IT mode

1. Put the IT card in the reader. The login screen says **IT-modus** and has no emergency button.
2. Type the PIN. The desktop starts with an **amber taskbar**, so you can see at once that this is IT mode.
3. The Start menu and desktop have the IT tools: Sikkerhetssenter, Terminal, Oppgavebehandling,
   Nettverk, Alle innstillinger, Medisinsk utstyr (USB) and this handbook.

**Admin commands:** in the terminal, put `sudo` in front. It asks for the **PIN of your IT card**,
every time, and the command is logged in the security log (`admin_confirmed`). Without the IT card
in the reader, `sudo` does not work.

**How the lock works** (so you can change it safely):

- The tools are owned by the group `medicus-it` with mode 0750 (`dpkg-statoverride` in the build hook).
  Even if a normal user found the program, they could not start it.
- `sudo` itself is 4750 `root:medicus-it`, and `/etc/pam.d/sudo` sends the PIN to medicus-authd.
- The IT session (`medicus-it-session`) only adds `/usr/share/medicus-it` to what the menu shows.

**Adding an IT person:** give their card the role `IT` in the card file. The build hook puts them
in `medicus-it` instead of `medicus-personell`. (With real cards this comes from the employer's
card register, not a file.)

**Adding an IT tool:** add the package to `medicus.list.chroot`, lock its program in the build hook
(the `dpkg-statoverride` loop), add a `.desktop` file to `usr/share/medicus-it/applications/`, and
hide the package's own menu entry in `os/menu.py` (`HIDE`).

---

## 4. When something happens

### "I can't log in"

| What the screen says | What to do |
|---|---|
| *Kortet er sperret* (card blocked) | Three wrong PINs. **Check the person's ID first**, then in IT mode: `medicus-kort opphev-sperre <kort-id>` (asks for your IT card PIN, logged as `card_unblocked`). A real health personnel card that blocks itself is reset by the card issuer with the PUK code. |
| *Får ikke kontakt med innloggingstjenesten* | `sudo systemctl status medicus-auth`, then `sudo journalctl -u medicus-auth -n 50`. |
| *Kortet tilhører en annen bruker* | The card in the reader isn't the one the screen shows. Take it out and put it back in. |
| *PC-en er ikke koblet til sykehusets kliniske nett* | Check the cable / Wi-Fi and `medicus-wlan` (certificate valid?). See "Network ports and the clinical VLAN". |
| Nothing happens after the PIN | Look in `sudo journalctl -b | grep -i pam`. |

### Someone used emergency access

Normal: they write the report at their next login (it opens by itself, and every Medicus page
shows a red reminder). The situation they tapped is already filled in. If the Sikkerhetssenter shows
**Nødtilgangsrapporter** in red, the deadline has passed: tell the data protection officer, who
follows it up with the person. The full trail is in the security log: `emergency_start`,
`emergency_patient_opened`, `emergency_report_written` / `emergency_report_overdue`.

### Sikkerhetssenter shows red

Each line says which protection is down. Restart it and look at the log:

```bash
sudo systemctl restart nftables          # or usbguard, auditd, clamav-daemon, ...
sudo journalctl -u nftables -n 50
```

If it won't start, don't leave the machine in use: a missing firewall or USB lock is a security incident.

### Suspected attack or phishing

1. Take the machine off the network (unplug the cable) and keep it running, so memory is not lost.
2. Note the time and what you saw. Don't "clean up" first.
3. Copy the logs: `/var/lib/medicus-auth/audit.jsonl`, `/var/lib/medicus/`, `sudo journalctl -b > journal.txt`.
4. Check that the logs are untouched, with the anchors from IT security's key vault:
   `sudo medicus-revisjon sjekk ankre.jsonl`. Every log should say *i orden (med anker)*. Without the
   anchors only the hash chain is checked, and someone in control of the machine can rebuild that.
5. Follow the health trust's incident routine (and Normen). Phishing reports from users come from
   Post's **Rapporter** button.

### The audit logs and their anchors

Each Medicus log (`/var/lib/medicus-auth/`, `/var/lib/medicus/`, `-utstyr/`, `-wlan/`, `-journalsystem/`)
has two protections:

- **A hash chain:** every line contains the hash of the line before it.
- **A key that changes on every line:** every line is also signed with a key that is replaced by its
  own hash the moment it is used. Someone who breaks in at 14:00 only finds the 14:00 key, and can't
  sign anything from before 14:00.

The first key of each log is its **anchor** (`audit.jsonl.anker`). While it is on the PC,
Sikkerhetssenter shows **Revisjonslogg: Bør sjekkes**. When a PC is set up:

```bash
sudo medicus-revisjon ankre
```

1. Store the lines it prints in IT security's key vault, under the PC's name. Never on the PC itself.
2. Answer `ja`, and the anchors are deleted from the PC.

A **new anchor showing up later** means a log's key file was lost or deleted: by an old Medicus version,
or by someone covering their tracks. The log says `audit_key_series_started` on that line. Find out why
before you store the new anchor.

Logs on the machine can still be deleted by someone who controls it. That is why the logs are meant
to be shipped to a central log server as they are written (see `docs/design.md`).

### A website is blocked that should work

Nettleser and the web filter use the same list: `medicus/nettsteder.py`. Add the site there
with a comment saying why, run the tests, rebuild. Only Norwegian health, public and Norwegian-owned
news sites belong there.

### A medical USB device doesn't work

The USB lock only allows keyboards, mice, headsets, hubs and card readers. Anything else is blocked
until IT approves it: dictation microphones (SpeechMike), spirometers, ECG dongles, dermatoscopes and so on.

1. Plug the device in. The Sikkerhetssenter lists it under **Medisinsk USB-utstyr** as blocked.
2. Open **Medisinsk utstyr (USB)** from the IT menu (or `medicus-utstyr meny` in the terminal).
3. Type the port shown for the device, give it a name ("Spirometer, legekontor 2"), and confirm
   with the IT card PIN.

| Approve | Command | When |
|---|---|---|
| This unit | `sudo medicus-utstyr godkjenn 1-2 --navn "..."` | The default. Only this serial number. |
| The whole model | `... --hele-modellen` | Many identical devices, or a device without a serial number |
| Everything from a maker | `sudo medicus-utstyr leverandor 0911 --navn "..."` | Rarely. Only for makers of medical devices. |
| Remove | `sudo medicus-utstyr fjern 3` | The device is gone or replaced |

**The safety rules** (in `utstyr/__init__.py`, and tested):

- An approved unit or model may only use the interfaces it had when it was approved (USBGuard
  `match-all`). If it later shows up with something extra, it is blocked again.
- Storage (memory sticks), network/modem and wireless can **never** be approved, also not with a
  maker rule. A device that has any of them is refused.
- Only approve equipment your organisation has bought, and that the clinic says it needs.

Where it is: the list is `/etc/medicus/medisinsk-utstyr.json`, the rules are generated into
`/etc/usbguard/rules.d/50-medisinsk-utstyr.conf` (don't edit that file by hand), and every change is
logged in `/var/lib/medicus-utstyr/audit.jsonl` with who did it.

### Wi-Fi with a machine certificate (TPM)

Medicus PCs join Wi-Fi with 802.1X EAP-TLS: a certificate instead of a password. The private key is
made **inside the TPM chip** and can't be copied out, so a cloned disk can't get on the network. The
PC only joins the WLANs on IT's list, and only if the RADIUS server proves its name with a certificate
from your own CA (so a fake access point with the same name gets nothing).

Once per PC, in IT mode (each step asks for the IT card PIN):

```bash
sudo medicus-wlan nokkel                                   # key inside the TPM
sudo medicus-wlan foresporsel                              # request → sign it in your CA
sudo medicus-wlan sertifikat maskin.crt ca.crt             # install the signed certificate
sudo medicus-wlan legg-til Sykehus-Ansatt --server radius.sykehuset.no
```

`medicus-wlan` shows the status, and `sudo medicus-wlan fjern SSID` removes a network. The
Sikkerhetssenter warns 30 days before the certificate runs out. Needs TPM 2.0 switched on in
BIOS/UEFI and a RADIUS server set up for EAP-TLS. **Test on real hardware first:** the TPM path
(tpm2-pkcs11 → NetworkManager → wpa_supplicant) can't be tried in a VM without a virtual TPM.

**The workplace is signed into the certificate.** `foresporsel` puts the PC's workplace id from
`/etc/medicus/arbeidssted.toml` into the request as `OU` (for example `CN=pc-0042, OU=ous-ulleval`).
Sign it only if the PC really belongs there. At every login, `medicus-authd` compares the two:

| Certificate says | Result |
|---|---|
| The same workplace as the file | Sikkerhetssenter: *Bekreftet av maskinsertifikatet* |
| Nothing (no certificate, or one from before this) | Allowed; Sikkerhetssenter shows *Ikke bekreftet ennå* |
| Another workplace, or can't be read | **Patient records closed** (`login_refused_site`). Emergency access and IT mode still work |

So moving a PC to another hospital takes a new certificate from IT, not only a changed file. Notes
and Helsenorge access logs name the workplace, and this keeps that name honest. A home-made
certificate doesn't help an intruder either: the network's RADIUS server only accepts the hospital's CA.

### Network ports and the clinical VLAN

The same TPM certificate also works on the network cable:

```bash
sudo medicus-wlan kablet --server radius.sykehuset.no      # wired 802.1X (--av removes it)
```

How each part works:
- **The switch:** it asks the RADIUS server about the PC, and RADIUS puts PCs with a valid certificate
  on the **clinical VLAN** (dynamic VLAN assignment). Anything else lands on the guest VLAN or nowhere:
  a private laptop, a cloned disk, a PC that was stolen and had its certificate revoked. That part is set
  up in the switch and RADIUS server, not on the PC.
- **Medicus checks too:** list the clinical subnets in `/etc/medicus/arbeidssted.toml`:

  ```toml
  nett = ["10.20.0.0/16"]
  ```

  Then `medicus-authd` only lets health personnel log in, or unlock the screen, while **both** are true:
  - the PC is connected through a Medicus 802.1X profile (*Medicus: …*, so with the TPM certificate);
  - the PC has an address in one of those subnets.

  authd reads this itself from the kernel and NetworkManager, so nothing the user runs can fake it.

| Who | Outside the clinical network |
|---|---|
| Health personnel | Refused: *PC-en er ikke koblet til sykehusets kliniske nett*. Logged as `login_refused_network` / `unlock_refused_network`. |
| Emergency access | Always works: lives first. Marked `utenfor_klinisk_nett` in the log. |
| IT mode | Works, so IT can repair the network. No patient data anyway. Marked `utenfor_klinisk_nett`. |

### Mobile PCs: home nursing, ambulance, on-call

A PC that leaves the building is never on the ward's network, so the rule above would lock it. Mark it
as mobile in `/etc/medicus/arbeidssted.toml`, with the hospital's **VPN address range** as `nett`:

```toml
profil = "mobil"
nett = ["10.99.0.0/16"]
```

Then health personnel can log in on 4G or any Wi-Fi when **all** of these hold (read by `medicus-authd`):

- the WireGuard tunnel `helsenett` is up (`medicus-vpn`, enabled with `systemctl enable --now medicus-vpn`);
- its **kill switch** is on, so nothing can leave the PC except through the tunnel;
- the PC has an address in the VPN range, which only a correctly set-up tunnel gets.

Without the VPN they get a plain message: *Koble til mobilnett eller Wi-Fi, og vent til VPN-en er på*.
Emergency access works anyway.

| Fixed PC | Mobile PC |
|---|---|
| Ward network through 802.1X with the TPM certificate | VPN with kill switch |
| Tap-in if IT allows it | **Never tap-in**: the PC is in cars and patients' homes |
| | Card out locks at once, same 15-minute hold |

Be aware: the WireGuard key is in `/etc/wireguard` (root only), not in the TPM like the Wi-Fi certificate.
Mobile PCs must have **full-disk encryption** (LUKS) so a stolen PC can't give away the key. Revoke a lost
PC's VPN key on the VPN server at once.

Not solved yet: working with **no network at all** (a basement, a mountain road). That needs downtime mode,
see `docs/design.md`.

### Tap-in: card back without the PIN

Typing the PIN every time the card comes back is one of the biggest annoyances on shared ward PCs. Each
PC can allow **tap-in** in `/etc/medicus/arbeidssted.toml`:

```toml
kort_uten_pin_minutter = 240   # 0 or unset = off (the default)
```

Then, when someone takes the card out and puts **the same card** back, `medicus-oktvakt` resumes the
held session and unlocks the screen without the PIN, if the PIN was typed less than 240 minutes ago.
After that the PIN is asked for again, and typing it starts the 240 minutes over. Pressing Enter on the
lock screen with an empty PIN field does the same thing, as a fallback.

| Rule | Why |
|---|---|
| Off unless IT sets it; maximum 720 (one shift); anything invalid means off | A typo never weakens a PC |
| Only after card-out (a held session) | A screen locked with the card still in the reader always needs the PIN, so a forgotten card doesn't open the PC |
| Only normal mode, never IT mode | IT mode has admin rights |
| Only the same card, not blocked, on the clinical network | Same rules as the PIN unlock |
| Logged as `session_resumed` with `"uten_pin": true` | You can see how often it is used |

Suggested: allow it on ward PCs in locked staff areas, not on PCs in reception or patient rooms.

A `nett` line IT mistyped closes access; it never opens it. Leave `nett` out on PCs that aren't on a
clinical VLAN yet.

### DIPS, Epic and the patient list

Set up in `/etc/medicus/integrasjon.toml`. See [journalsystemer.md](journalsystemer.md). If doctors see
"Medicus er ikke koblet til DIPS ennå", the DIPS address or the token is missing.

### The hospital's record systems

The hospital's own system (DIPS Arena, Epic, …) can run in a locked-down window next to Medicus.
- **Set up:** list the systems in `/etc/medicus/journalsystemer.toml`, then run
  `sudo medicus-journalsystem oppdater`.
- **Check:** `medicus-journalsystem` shows what is set up.
- **Remote windows log in with the health worker's card.** Nothing is shared with the server: no
  disks, clipboard, USB or printers.

Details are in [journalsystemer.md](journalsystemer.md#the-hospitals-own-record-system-next-to-medicus).
Every change is logged in `/var/lib/medicus-journalsystem/audit.jsonl`.

---

## 5. Building, testing and changing Medicus

You need a Linux machine (or WSL with Debian) with `live-build`, `librsvg2-bin`, `rsync` and `python3-pil`.

```bash
python3 -m pytest -q                 # run all tests (takes seconds)
sudo os/build.sh                     # build the ISO (about 20–40 minutes)
```

Try the ISO in a virtual machine (QEMU, VirtualBox, Hyper-V) before it goes near a real PC. The demo
cards are in `os/config/includes.chroot/etc/medicus/simkort-demo.json` (PIN 1234 for all).

**How to make a change:**

1. Find the place in the table in section 2. Each file starts with a comment saying what it does.
2. Change it, and add or fix a test in `tests/`.
3. `python3 -m pytest -q` must be green.
4. Rebuild and try it in a virtual machine.
5. Commit with a message that says *why*.

**House rules for the code:** small files that do one thing, plain Python without frameworks where
we can, comments that explain *why*, Norwegian text on screen and English in the code. Keep it simple
enough that the next person understands it from reading it.

---

## 6. Words

| Word | Meaning |
|---|---|
| HPR number | The health personnel register number on the card. IT cards carry the employee number instead. |
| Nødtilgang | Emergency access ("break the glass"). |
| Personvernombud | Data protection officer. Reviews emergency access and the security log. |
| Normen | The Norwegian code of conduct for information security in health care. |
| Helsenett | The national health network run by Norsk helsenett. |
| PAM | The part of Linux that decides how login works. Medicus plugs into it with `pam_exec`. |
| live-build | Debian's tool for building a bootable ISO. |
