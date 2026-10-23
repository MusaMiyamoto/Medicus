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
- **Card out = logged out.** Taking the card out ends a normal or IT session at once.
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
| `tilgang/nodrapport.py` | Emergency access reports and their deadline | Python |
| `medicus/` | The web app: patient record, Post, journal assistant, Sikkerhetssenter | Python + FastAPI, plain HTML/CSS/JS |
| `helsenett/` | One interface to the national health services, plus a simulator | Python + FastAPI |
| `nettleser/` | **Medicus Nettleser**, the browser (only approved sites) | Python + GTK 4 + WebKitGTK 6 |
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

### Services (systemd)

| Service | What it does | If it stops |
|---|---|---|
| `medicus-auth` | Card, PIN, sessions, reports | Nobody can log in |
| `medicus-oktvakt` | Logs out desktops without a valid card login | Card out no longer logs out |
| `medicus` | The web app on 127.0.0.1:8000 | Patient record, Post etc. show an error |
| `medicus-helsenett-sim` | The simulated health network on 127.0.0.1:8100 | No patients (demo only) |
| `nftables`, `usbguard`, `auditd`, `clamav-daemon`, `tinyproxy` | Firewall, USB lock, system log, virus scan, web filter | Sikkerhetssenter turns red |

---

## 3. IT mode

1. Put the IT card in the reader. The login screen says **IT-modus** and has no emergency button.
2. Type the PIN. The desktop starts with an **amber taskbar**, so you can see at once that this is IT mode.
3. The Start menu and desktop have the IT tools: Sikkerhetssenter, Terminal, Oppgavebehandling,
   Nettverk, Alle innstillinger and this handbook.

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
| *Kortet er sperret* (card blocked) | Three wrong PINs. In IT mode: `sudo nano /var/lib/medicus-auth/pin-forsok.json` and remove the card's line, after checking it is really the owner. |
| *Får ikke kontakt med innloggingstjenesten* | `sudo systemctl status medicus-auth`, then `sudo journalctl -u medicus-auth -n 50`. |
| *Kortet tilhører en annen bruker* | The card in the reader isn't the one the screen shows. Take it out and put it back in. |
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
4. Check that the security log is untouched: `curl -s 127.0.0.1:8000/api/audit/verify` should say `"ok": true`.
5. Follow the health trust's incident routine (and Normen). Phishing reports from users come from
   Medicus Post's **Rapporter** button.

### A website is blocked that should work

Medicus Nettleser and the web filter use the same list: `medicus/nettsteder.py`. Add the site there
with a comment saying why, run the tests, rebuild. Only Norwegian health, public and Norwegian-owned
news sites belong there.

### A USB device doesn't work

The USB lock only allows keyboard, mouse, headset and card reader. To allow one more kind:
`sudo usbguard list-devices`, then add a rule to `os/config/includes.chroot/etc/usbguard/rules.conf`
and rebuild. Never allow storage devices (memory sticks).

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
