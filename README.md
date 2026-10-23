# Medicus

A hardened, Linux-based operating system for Norwegian healthcare workers, with a local,
privacy-first AI documentation assistant ("journalassistent") and a clinical calculator.

> ⚠️ **Prototype with synthetic data only.** Not approved for real patient data. The simulated
> health network, cards and patients exist only to show how Medicus works.

| Part | Folder | What it is |
|---|---|---|
| **Medicus OS** | [`os/`](os/) | Debian 13 Linux with an XFCE desktop and a Start menu, built as a bootable ISO |
| **Login** | [`tilgang/`](tilgang/) | Card + PIN login, emergency access, and the session rules |
| **Health network** | [`helsenett/`](helsenett/) | One interface to the national services, plus a local simulator |
| **Patient record and journal assistant** | [`medicus/`](medicus/) | The clinician's web app |
| **Medicus Kalkulator** | [`kalkulator/`](kalkulator/) | Calculator plus converters for volume, weight and weight ↔ volume |
| **Branding** | [`branding/`](branding/) | Logo (the Rod of Asclepius), wallpaper, boot screen |

## Medicus OS

A live ISO you can boot in a virtual machine (VirtualBox, VMware, Hyper-V) or from a USB stick.

Medicus is meant **only for machines owned and run by the health trust, municipality or another
public body**, never for private PCs or phones.

- **Start-up:** a centered boot screen (the "I" in MEDICUS is a green cross) that starts by itself
  after 5 seconds, then a pulsing heartbeat (ECG) animation until the login screen appears.
  Both are generated from `branding/` by `branding/make_assets.py`.
- **Own look:** Medicus green, the Medicus logo (Rod of Asclepius, drawn for this project), the
  open-source Arc theme, Papirus icons and Noto fonts. Nothing is taken from Microsoft or Windows.
- **Desktop:** XFCE with one bottom panel and a **Start** button. The Start menu's favorites are the
  patient record, the journal assistant, the Kalkulator, and the simulated citizen portal and disclosure workflow.
- **Norwegian by default:** language `nb_NO`, Norwegian keyboard, Oslo time zone.

### Logging in

There are no passwords. Two ways in:

| | Normal login | Emergency access (*Nødtilgang*) |
|---|---|---|
| How | Health-personnel card + PIN | Card tap + reason, no PIN |
| Sees | Patient record: critical info, visits and notes from every institution, prescriptions | **Only critical information**: allergies, critical conditions, medicines in use, implants, next of kin |
| Time | Until you log out or take the card out | 30 minutes, then it closes |
| Desktop | Full Medicus desktop | Full-screen emergency page only, no desktop or files |
| Logged | Yes, with name and HPR number | Yes, with name, HPR number and reason; always reviewed afterwards |
| Patient told | Yes, on Helsenorge | Yes, marked as emergency access |

- **Log in once:** every Medicus app knows who you are from the card login. No separate logins.
- **Card out = logged out.** A root-level service (`medicus-oktvakt`) ends the desktop session immediately.
- **Three wrong PINs block the card**, like a real chip card.

In this prototype the card reader is **simulated**: use *Simulert kortleser* at the bottom of the
login screen. Demo cards (PIN `1234` for all of them):

| Card | Role |
|---|---|
| Ingrid Berg | Doctor (*lege*): can write prescriptions |
| Jonas Lie | Nurse (*sykepleier*) |
| Amir Haddad | Paramedic (*ambulansearbeider*) |

**The workplace comes from the PC, not the card.** Each machine has its workplace in
`/etc/medicus/arbeidssted.toml` (for example Oslo universitetssykehus, Ullevål). The same card
shows the person's position (*stilling*) at that workplace, so a doctor who logs in at St. Olavs
in Trondheim or at Aker is shown there. In the demo, pick the workplace on the login screen.

### Health network, Helsenorge and authorities

- **Helsenorge-ready:** see [docs/helsenorge-integrasjon.md](docs/helsenorge-integrasjon.md). All
  national services go through one interface. Today it uses a local simulator; switching to Norsk
  helsenett is one setting, once there's an agreement.
- **Patients see every access:** the simulated citizen portal (*Innbyggerportal*) shows who opened
  the record and why, prescriptions, visits and notes from every institution, and disclosures to authorities.
- **Requests from authorities** go through a request workflow, never direct access:
  a legal basis, purpose and the minimum data needed. The institution (the data controller, or the responsible health
  personnel) approves or refuses, with advice from the privacy officer when needed. Only
  the approved data is released, it's logged, and the patient is told unless a legal basis allows
  delaying the notice.
- **Each authority can only use the legal bases that apply to it** ([`helsenett/hjemler.py`](helsenett/hjemler.py)).
  The main rule is confidentiality (*helsepersonelloven* § 21):

  | Authority | Possible legal basis |
  |---|---|
  | Police / prosecution | Patient consent, § 31 (prevent serious harm), § 23 nr. 4 (weighty interests). Investigating a case is not enough on its own: doctors and nurses can't testify about patients (*straffeprosessloven* § 119), and records generally can't be seized (§ 204). |
  | Courts / *barneverns- og helsenemnda* | Patient consent, exemption from the County Governor (*tvisteloven* § 22-5), duty to testify to the board (*barnevernsloven* § 13-4) |
  | Child welfare (*barnevernet*) | Order under *helsepersonelloven* § 33 and *barnevernsloven* § 13-2 (only the information needed, not the whole record) |
  | NAV | Information needed for a benefit claim (*folketrygdloven* § 21-4) |
  | Health supervision (*Helsetilsynet*, *Statsforvalteren*) | Supervision case (§ 30, *helsetilsynsloven* § 7) |
  | Municipal health and care services | Order under § 32 |
  | Infection control (municipal chief medical officer, FHI) | *Smittevernloven* §§ 2-2 and 2-3 |
  | Immigration authorities | Expulsion case under § 29 d |
  | Everyone else (tax office, employers, insurers) | Only with the patient's consent or an explicit law |

  These rules are a careful reading of the law, but they **must be checked by a lawyer** before real use.

### Medicus Post: messages, image sharing and phishing protection

One app for communication between institutions, used instead of ordinary email:

- **Messages inside the health network** are always **verified** (green ✓). The sender is the
  person who logged in with their card, shown with role, institution and HPR number. You choose
  recipients from the address register, so there are no typed email addresses to get wrong.
- **Image sharing:** attach X-ray, CT and MR images (DICOM), photos or PDFs, up to 50 MB each.
  They're shown right in the message, with a viewer that has brightness, contrast and invert.
  Files are checked by their content, not their name, so only real images and PDFs get through.
  If the message is linked to a patient, the patient sees on Helsenorge that images were shared, and with whom.
- **External email gets a plain-language safety check:**
  - **Ekstern** (yellow): from outside, nothing suspicious found.
  - **Mistenkelig** (red): a list of the exact warning signs, for example "the address looks like
    *helsenorge.no* but isn't", "the link shows one address but goes to another", "pressure plus a
    request for BankID or password", "dangerous attachment like *faktura.pdf.exe*", "replies go to a
    different address".
  - Email from outside never shows clickable links or opens attachments. Links are shown as text
    with where they *really* go.
  - One click reports a suspicious email to IT security.

The image sharing uses DICOM, the standard every radiology system uses, so a radiology or lab
provider can be connected later through the same interface (with an agreement).

### Desktop and programs

Medicus OS is a desktop and laptop operating system for ordinary 64-bit PCs (Intel/AMD).

- **Desktop:** Home folder and Trash icons, shortcuts to the Medicus apps, and the **Start** button bottom left.
- **Standard programs, with plain names:** **Files**, **Text**, **Pictures**, **Dokumenter** (PDF reader,
  in an AppArmor sandbox), **Skjermbilde** (screenshots) and **Mouse** (mouse settings). Settings
  that could run commands (settings editor, keyboard shortcuts) are hidden.
- **Files** is kept clean: big icons, folders first, no menu bar, and a sidebar with just
  *Hjem*, *Skrivebord*, *Dokumenter*, *Bilder*, *Nedlastinger* and *Papirkurv*. Music, video,
  template and public folders aren't created, and there's no network or file-system clutter or
  "open terminal here".
- **Wallpapers:** four Norwegian nature scenes drawn for Medicus, so we own them fully with no
  licensing risk: *Nordlys* (default), *Fjord*, *Skog* and *Fjell*, plus the Medicus wallpaper.
  Choose under Settings → Desktop.

### Medicus Nettleser

Our own browser ([`nettleser/`](nettleser/)), built on the open-source WebKit engine with a
Medicus toolbar and the heartbeat loader. No other brand is visible anywhere.

- Opens only **approved websites**: health sites (Helsenorge, Felleskatalogen, Legemiddelhåndboka,
  Helsedirektoratet, FHI and others) and **government sites** (NAV, Skatteetaten, Altinn, ID-porten,
  Regjeringen, Politiet, every *kommune.no* and more) and **Norwegian news** (NRK, NTB, VG, Aftenposten,
  regional papers, and health news like Tidsskriftet and Sykepleien; only Norwegian-owned sites), listed in
  [`medicus/nettsteder.py`](medicus/nettsteder.py). Ads and trackers from other companies stay blocked.
  A web filter (tinyproxy) enforces the same list, so the browser can't get around it.
- **Nothing points back to Medicus:** the plain engine user agent, no referrer, no proxy headers,
  WebGL and WebRTC off (fingerprinting and IP leaks), and a neutral "not allowed" page.
- Nothing is saved: no history, cookies or cache survive closing the browser. HTTPS only for the
  internet, no extensions, no developer tools, and only Medicus apps can use the microphone.

### Cyber defense

- **Virus scanning (ClamAV):** every attachment in Medicus Post is scanned before it's accepted.
  Infected files are stopped. The virus database is updated automatically.
- **Security log (auditd):** records changes to logins, Medicus settings, the firewall, USB and VPN
  rules, kernel modules, and anything run as administrator.
- **Sikkerhetssenter:** a page that shows *live* whether the firewall, USB lock, virus scanner,
  session guard, security log, updates, kernel lockdown, AppArmor and VPN are working, in plain Norwegian.
- **Lynis** is installed for IT to run full security audits.

### Protection against malware

No system can be guaranteed against all malware. Medicus OS stacks several layers so most of it
has nothing to work with:

- Windows programs (most of what malware-scanning services like VirusTotal see) can't run on Linux at all.
- **Nothing can be run as a program from home folders, downloads or temporary folders**
  (mounted `noexec`), which is how most downloaded malware starts.
- Users have **no terminal and no "run command" box**. Programs start from the Start menu only.
- Attachments are virus-scanned, USB memory sticks are blocked, and the browser only reaches approved sites.
- The PDF reader runs in an AppArmor sandbox, and every service runs with minimal rights.

### Network: VPN, Wi-Fi and attacks

- **Always-on VPN to the health network (WireGuard) with a kill switch:** when it's on, the
  machine can't send anything except through the tunnel. Fill in
  `/etc/wireguard/helsenett.conf` from the template, then `systemctl enable --now medicus-vpn`.
  The real endpoint and keys come from Norsk helsenett or the IT department.
- **Wi-Fi:** random hardware address while scanning, private IPv6, no network discovery (mDNS/LLMNR).
  Health personnel can't add new networks (like open café Wi-Fi). IT sets them up.
- **Attack traffic:** malformed packets are dropped and ping is rate-limited. A single PC can't
  stop a large DDoS attack; that has to be handled by the network operator or Norsk helsenett.
  What Medicus does is have nothing open to attack and stay cheap to flood.

### Hardening

- **Login:** card only, no passwords, no automatic login, no admin (`sudo`) access, text consoles switched off.
- **Network:** firewall blocks everything incoming. Users and apps can only reach this machine. Only
  the system itself can go online, for security updates.
- **Browser:** only approved sites can be opened. No extensions, developer tools or saved passwords,
  and nothing is kept after closing.
- **USB:** only keyboards, mice, headsets, hubs and card readers. Memory sticks, cameras and
  network adapters are blocked, including devices that combine them.
- **Kernel:** hardening boot settings (memory zeroing, lockdown, no vsyscall) and `/etc/sysctl.d/90-medicus.conf`.
- **Services:** each Medicus service runs as its own locked-down user with only the access it needs.
  The login service has no network at all.
- **Less to attack:** Bluetooth, network discovery (Avahi), Ctrl+Alt+Del reboot and core dumps are switched off.
- **Other:** screen locks after 5 minutes (unlock with card + PIN), automatic daily security updates.
- AppArmor is on. (Debian skips loading AppArmor profiles in the *live* session; they load once the OS is installed.)

No system can be made 100% secure. Before any real use, Medicus needs an external penetration test,
a Normen and GDPR assessment, and a medical-device classification (EU MDR).

### Building the ISO

You need Debian, either on a real machine or in WSL on Windows (`wsl --install -d Debian`).

```bash
sudo apt install live-build rsync librsvg2-bin python3-pil
```
```bash
sudo sh os/build.sh /path/to/output-folder
```

The first build downloads 1–2 GB and takes a while. Later builds reuse the download cache in `/var/tmp/medicus-os`.

### Open source and selling Medicus

Medicus is built on free software (Debian, Xfce, WebKitGTK and more). *Om Medicus* in the Start
menu lists the components and their licenses; the full license text for each package is in
`/usr/share/doc/<package>/copyright`. Anyone who gets Medicus must be able to get the source code
of the GPL parts. Before selling it for real patient use, Medicus also needs CE marking under
EU MDR (if classified as a medical device), a Normen/GDPR assessment and an agreement with Norsk helsenett.

## Medicus Kalkulator

A GTK 4 desktop app in the Start menu:

- **Kalkulator:** + − × ÷ and parentheses, with a decimal comma (`2,5 × 4`).
- **Volum:** µl, ml, cl, dl, liter, plus teaspoon (5 ml) and tablespoon (15 ml) as used on
  medicine labels. Type an amount and see it in every unit at once.
- **Vekt:** µg, mg, gram, hektogram, kilo.
- **Vekt ↔ volum:** any weight unit to every volume unit and back (for example liter → kg,
  ml → g, mg → µl), using the substance's **density**. Water (1 g/ml) is the default, with presets
  for blood, saline 0.9 %, glucose 5 %, breast milk, hand disinfectant (ethanol 70 %), pure
  ethanol and olive oil, or you can type your own density. The result shows which density was used.

> ⚠️ The Kalkulator is **not** for medication dosing. Always use the official product information (SPC)
> and local procedures.

All arithmetic uses exact decimals, so 0,1 + 0,2 is exactly 0,3. The calculator parses
input safely and never runs it as code.

Run it on any Linux desktop with GTK 4 (`sudo apt install python3-gi gir1.2-gtk-4.0`):

```bash
python3 -m kalkulator
```

## Medicus Journalassistent

A clinician records a consultation. Medicus transcribes it and drafts a structured
journal note in Norwegian. The clinician reviews, edits and approves it, then pastes
it into the patient record system (DIPS, Epic, a GP system, etc.).

**Everything runs on the local machine.** No audio or text is sent to any cloud service.

> ⚠️ **Prototype.** Use only made-up data, never real patient information.
> Medicus is not a certified medical device, and every note must be checked by a clinician.

## How it works

```
Microphone / audio file ──► faster-whisper (local speech-to-text)
                                   │
                                   ▼
                        Editable transcript
                                   │
                                   ▼
                    Ollama (local language model)
                                   │
                                   ▼
   Structured note: Kontaktårsak · Anamnese · Funn · Vurdering · Plan
                                   │
                                   ▼
          Clinician edits and approves ──► copy into the patient record
```

## Privacy and security

- **Local only:** speech recognition and the language model both run on this machine.
- **Recordings are deleted** as soon as they've been transcribed.
- **Tamper-evident audit log:** every action is logged in a hash chain (`data/audit.jsonl`),
  so editing or deleting a line is detected. Check it at `/api/audit/verify`.
  The log stores metadata only (who, what, when, sizes), never patient content.
- **Listens on 127.0.0.1 only** by default, so other machines can't reach it.
- **Hardened Linux service:** [`deploy/medicus.service`](deploy/medicus.service) locks the
  service down with systemd: no network access beyond this machine, a read-only system,
  and no extra privileges.
- **The model only drafts:** it's told never to invent findings, diagnoses or doses,
  and a clinician must approve every note.

## Getting started (Windows)

1. Install the tools:
   ```bash
   winget install Python.Python.3.12 Ollama.Ollama
   ```
2. Download a local language model (about 3 GB):
   ```bash
   ollama pull gemma3:4b
   ```
3. Install Medicus (from the project folder):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
4. Start it:
   ```bash
   python -m medicus
   ```
5. Open <http://127.0.0.1:8000> and click **Bruk eksempelsamtale** to try it with a made-up consultation.

The speech model (about 1.5 GB) downloads the first time you transcribe audio.
On a machine without a graphics card, expect a few minutes per 10 minutes of audio.

## Settings

All settings are environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `MEDICUS_LLM_MODEL` | `gemma3:4b` | Ollama model used to write the note. Bigger models (e.g. `gemma3:12b`) give better notes but run slower. |
| `MEDICUS_WHISPER_MODEL` | `medium` | Speech model. `large-v3` is more accurate but slower. |
| `MEDICUS_WHISPER_LANGUAGE` | `no` | Language of the consultation. |
| `MEDICUS_OLLAMA_URL` | `http://127.0.0.1:11434` | Where Ollama runs. |
| `MEDICUS_AUDIT_LOG` | `data/audit.jsonl` | Audit log location. |
| `MEDICUS_HOST` / `MEDICUS_PORT` | `127.0.0.1` / `8000` | Address the web server listens on. |

## Tests

```bash
pytest
```

## Roadmap

- [x] Local transcription, note drafting, review and approval
- [x] Tamper-evident audit log
- [x] Hardened systemd service
- [ ] Better Norwegian speech: NB-Whisper from the National Library (Nasjonalbiblioteket), converted for faster-whisper
- [x] Card + PIN login and emergency access (simulated card reader)
- [x] Helsenorge-ready integration layer with a simulator
- [x] Request workflow for authorities
- [x] Medicus Post: verified messages, DICOM image sharing, phishing warnings
- [x] VPN with kill switch, Wi-Fi hardening, firewall rate limits
- [ ] Connect a radiology/lab provider's image archive (needs an agreement)
- [x] Medicus Nettleser, virus scanning, security log, Sikkerhetssenter, no-exec home folders
- [ ] Installation to disk: a separate, protected installer mode for IT (with full-disk encryption)
- [ ] Real chip cards (PKCS#11) and login with HelseID
- [ ] Security scanning of each build (Lynis, OpenSCAP)
- [ ] Pick different note templates (GP, emergency room, home care, psychiatry)
- [ ] Send notes to patient record systems via FHIR instead of copy and paste
- [x] Hardened Linux OS image (Debian + XFCE) with a Start menu
- [x] Calculator with volume, weight and weight ↔ volume converters
- [ ] Download the AI models (Ollama and Whisper) during OS setup, so the journal assistant works offline out of the box
- [x] Medicus branding: wallpaper, boot screen, login
- [ ] Installer branding
- [ ] Clinician testing and time-saving measurements
- [ ] Assess medical-device classification (EU MDR) and compliance with Normen and GDPR
