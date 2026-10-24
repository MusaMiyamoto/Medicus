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
| **Kalkulator** | [`kalkulator/`](kalkulator/) | Calculator, converters for volume and weight, and clinical scores (BMI, eGFR, CHA₂DS₂-VASc) |
| **Journal systems** | [`epj/`](epj/), [`journalsystem/`](journalsystem/) | DIPS / Epic over FHIR, and the hospital's own system in a locked-down window |
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
- **Norwegian by default:** language `nb_NO`, Norwegian keyboard, Oslo time zone. **Northern Sámi**
  (davvisámegiella: á č đ ŋ š ŧ ž) is the second keyboard layout: Alt+Shift switches, and the taskbar
  shows which one is on (*nor* / *sme*).

### Logging in

There are no passwords. Three ways in, all with a card:

| | Normal login | Emergency access (*Nødtilgang*) | IT mode (*IT-modus*) |
|---|---|---|---|
| Who | Health personnel | Health personnel | IT staff (cards with role `IT`) |
| How | Card + PIN | Card + one tap on the situation (cardiac arrest, unconscious, …), no PIN | Card + PIN |
| Sees | Patient record: critical info, visits and notes from every institution, prescriptions | **Only life-critical information**: allergies, critical conditions, medicines in use, implants, next of kin | **No patient data.** Sikkerhetssenter, terminal, all settings, task manager, network, IT handbook |
| Time | Until you log out. Card out locks it; not back within 15 minutes ends it | 30 minutes, then it closes | Same as normal |
| Desktop | Full Medicus desktop | Full-screen emergency page only | Medicus desktop with an amber taskbar and the IT tools |
| Afterwards | | The person **writes a report before the shift ends** (12 h). Late reports turn the Sikkerhetssenter red | Admin commands (`sudo`) ask for the IT card PIN every time |
| Logged | Yes, with name and HPR number | Yes, with name, HPR number, situation and report | Yes, every admin command |
| Patient told | Yes, on Helsenorge | Yes, marked as emergency access | (no access) |

- **Log in once:** every Medicus app knows who you are from the card login. No separate logins.
- **Card out = locked, nothing lost.** The screen locks at once and the session is **held for 15 minutes**.
  - **Same card and PIN back:** work continues exactly where it was, with open notes and unsaved text intact.
  - **Tap-in (if IT allows it on that PC):** the same card back is enough, without the PIN, for a set time
    after the PIN was last typed (`kort_uten_pin_minutter`, at most one shift). Never in IT mode, and never
    when the screen locked with the card still in the reader.
  - **Card not back in time:** the session ends.
  - **Another person logs in:** the held session ends.
  - **While held:** no app can use the session; the journal service refuses it.
  - **Enforcement:** a root-level service (`medicus-oktvakt`) does the locking and ending, so the user can't stop it.
  - **Memory:** RAM is encrypted where the CPU supports it (`mem_encrypt=on`, AMD SME; Intel TME is set in
    firmware). Hibernation is switched off, so a held session is never written to disk.
- **Three wrong PINs block the card**, like a real chip card.
- **A reason for patients outside your list.** Your own patients (your fastlege list, or people you
  have seen) open straight away. Anyone else asks *why* first: «Pasienten er hos meg nå», «Tilsyn eller
  konsultasjon», «Vakt», «Henvisning eller epikrise», or «Annet» with a short explanation. The reason goes
  into the access log the patient sees on Helsenorge, and into the audit log. If the patient list can't be
  fetched, you are asked for a reason instead of being locked out.
- **Nothing cached:** patient data from the API is sent with `Cache-Control: no-store`, so it is never
  written to the browser's disk cache.

In this prototype the card reader is **simulated**: use *Simulert kortleser* at the bottom of the
login screen. Demo cards (PIN `1234` for all of them):

| Card | Role |
|---|---|
| Ingrid Berg | Doctor (*lege*): can write prescriptions |
| Jonas Lie | Nurse (*sykepleier*) |
| Amir Haddad | Paramedic (*ambulansearbeider*) |
| Eirik Strand | IT staff: logs in to IT mode |

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

### Post: messages, image sharing and phishing protection

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
  Next to Start, the taskbar has pinned shortcuts to **Nettleser** (its logo is a light-blue
  Earth with a rocket in orbit) and **Files** (documents, pictures and downloads).
- **Standard programs, with plain names:** **Files**, **Text**, **Pictures**, **Dokumenter** (PDF reader,
  in an AppArmor sandbox), **Skjermbilde** (screenshots) and **Mouse** (mouse settings). Settings
  that could run commands (settings editor, keyboard shortcuts) are hidden.
- **Text** is Medicus' own small editor (`tekst/`): open, save, undo, and a question before closing
  with unsaved changes. Its own editor, so no other product's name shows in the window title.
- **Files** is kept clean: big icons, folders first, no menu bar, and a sidebar with just
  *Hjem*, *Skrivebord*, *Dokumenter*, *Bilder*, *Nedlastinger* and *Papirkurv*. Music, video,
  template and public folders aren't created, and there's no network or file-system clutter or
  "open terminal here".
- **Wallpapers:** four Norwegian nature scenes drawn for Medicus, so we own them fully with no
  licensing risk: *Nordlys* (default), *Fjord*, *Skog* and *Fjell*, plus the Medicus wallpaper.
  Choose under Settings → Desktop.

### Nettleser

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

- **Virus scanning (ClamAV):** every attachment in Post is scanned before it's accepted.
  Infected files are stopped. The virus database is updated automatically.
- **Security log (auditd):** records changes to logins, Medicus settings, the firewall, USB and VPN
  rules, kernel modules, and anything run as administrator.
- **Sikkerhetssenter (IT mode only):** a page that shows *live* whether the firewall, USB lock, virus scanner,
  session guard, security log, updates, kernel lockdown, AppArmor and VPN are working, and whether any
  emergency access reports are late, in plain Norwegian.
- **IT tools are locked, not just hidden:** the terminal, settings, task manager, network editor and
  `sudo` belong to the `medicus-it` group. See [docs/IT-handbok.md](docs/IT-handbok.md), the handbook for IT staff.
- **Lynis** is installed for IT to run full security audits.

### Protection against malware

No system can be guaranteed against all malware. Medicus OS stacks several layers so most of it
has nothing to work with:

- Windows programs (most of what malware-scanning services like VirusTotal see) can't run on Linux at all.
- **Nothing can be run as a program from home folders, downloads or temporary folders**
  (mounted `noexec`), which is how most downloaded malware starts.
- **Home folders are emptied when a session ends** (logout, a hold that ran out, or someone else logging
  in) and again at every boot. Downloads, browser history and copied files are never left for the next
  person, also on the shared emergency account. Coming back with your card within 15 minutes is not an
  end, so nothing is lost then. Unsaved journal notes are kept by the Medicus service, not in the home folder.
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
- **Machine certificate in the TPM:** each PC joins the WLANs IT approves with 802.1X EAP-TLS. The
  private key is made inside the TPM chip and can never be copied out, and the PC checks the
  network's RADIUS certificate, so a fake access point gets nothing (`medicus-wlan`, see the IT handbook).
  The same certificate works on the network cable (wired 802.1X), so the switch puts only real Medicus
  PCs on the clinical VLAN.
- **Patient records only on the clinical network:** when IT lists the site's clinical subnets, health
  personnel can only log in while the PC is on them **through its TPM certificate**. A PC carried off
  the ward, or onto a guest network, stays locked even if someone got past the card. Emergency access
  and IT mode still work everywhere, marked in the security log.
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
- **Medical USB devices** (dictation microphones, spirometers, ECG, dermatoscopes) are approved by
  IT, one unit (serial number) or one model at a time, with `medicus-utstyr` in IT mode. An approved
  device may only use the functions it had when it was approved, and **nothing approved can ever be
  a memory stick, network or wireless adapter**.
- **Kernel:** hardening boot settings (memory zeroing, lockdown, no vsyscall) and `/etc/sysctl.d/90-medicus.conf`.
- **Services:** each Medicus service runs as its own locked-down user with only the access it needs.
  The login service has no network at all.
- **Less to attack:** Bluetooth, network discovery (Avahi), Ctrl+Alt+Del reboot and core dumps are switched off.
  Drivers for floppy, FireWire, webcams and Bluetooth, and rarely used network protocols, can't be
  loaded (`/etc/modprobe.d/medicus.conf`). Switching to another screen with Ctrl+Alt+F1–F12 and
  killing the desktop with Ctrl+Alt+Backspace are turned off.
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

## Kalkulator

A GTK 4 desktop app in the Start menu:

- **Kalkulator:** + − × ÷ and parentheses, with a decimal comma (`2,5 × 4`).
- **Volum:** µl, ml, cl, dl, liter, plus teaspoon (5 ml) and tablespoon (15 ml) as used on
  medicine labels. Type an amount and see it in every unit at once.
- **Vekt:** µg, mg, gram, hektogram, kilo.
- **Vekt ↔ volum:** any weight unit to every volume unit and back (for example liter → kg,
  ml → g, mg → µl), using the substance's **density**. Water (1 g/ml) is the default, with presets
  for blood, saline 0.9 %, glucose 5 %, breast milk, hand disinfectant (ethanol 70 %), pure
  ethanol and olive oil, or you can type your own density. The result shows which density was used.
- **Kliniske skårer** ([`kalkulator/klinisk.py`](kalkulator/klinisk.py)): age and sex are typed once and
  used by every score.
  - **BMI** with the WHO class.
  - **eGFR**: CKD-EPI 2021 without race, from creatinine in µmol/L, adults only, with the G1–G5 stage.
  - **CHA₂DS₂-VASc** and **CHA₂DS₂-VA**: the sex-free version used in the ESC 2024 guidelines.
    The result only shows once the user has ticked that every point was reviewed.
  - **Felleskatalogen**: look up a medicine in Nettleser.
- **Akutt:** **NEWS2** (with SpO₂ scale 1 or 2, and every sub-score shown), **GCS** (E + V + M) and
  **CURB-65**.
- **Lab og EKG:** **Cockcroft-Gault** creatinine clearance (not adjusted to 1.73 m²), **corrected
  calcium** (Ca + 0.02 × (40 − albumin)) and **QTc** with both Bazett and Fridericia. The limit for
  prolonged QTc is judged on Fridericia, because Bazett overcorrects at high heart rates.

  Every score shows its formula and source under the result. **No silent defaults:** sex, SpO₂ scale,
  oxygen and consciousness all start as «Velg …», and a score stays empty until every field is filled
  in. The scores only calculate. They never suggest a medicine or a dose. They are decision support,
  and before clinical use they must be assessed under EU MDR (most likely class IIa).

> ⚠️ The Kalkulator is **not** for medication dosing. Always use the official product information (SPC)
> and local procedures.

All arithmetic uses exact decimals, so 0,1 + 0,2 is exactly 0,3. The calculator parses
input safely and never runs it as code.

Run it on any Linux desktop with GTK 4 (`sudo apt install python3-gi gir1.2-gtk-4.0`):

```bash
python3 -m kalkulator
```

## Journalassistent

A clinician records a consultation. Medicus transcribes it and drafts a structured
journal note in Norwegian. The clinician reviews, edits and approves it.

**Source check (kildesjekk):** under each field of the draft, every sentence is shown with where it
comes from in the conversation. Click a sentence to highlight those lines.
- **Statuses:** *✓ Sagt* (said), *◐ Delvis* (partly said), *✗ Ikke funnet* (not found), *– Ikke nevnt*
  (not mentioned). Each has a symbol and a word as well as a colour.
- **Numbers are always checked:** any number in the draft (doses, values, days) that wasn't said in the
  conversation is flagged red. "Fire dager" counts as 4.
- **No language model:** the check is plain word matching ([`medicus/kilder.py`](medicus/kilder.py)), so it
  can't invent sources.
- **Re-checked as you edit.** Approving a note with red sentences asks for confirmation first.

**Nothing lost when a session ends:** the unfinished note (conversation, draft and chosen patient) is
saved in the local service's memory as you type. If the session ends before it is approved (card not
back within 15 minutes, or a colleague logged in), it is offered back at your next login. Only to
you, for at most 12 hours, never on disk, and gone once approved or discarded.

**Wrong-patient guard:** switching patient while a note is open asks first, and empties the clipboard,
so a note can't be pasted into the wrong record.

**Less waiting:** the patient list is fetched in the background at login, so the picker is ready when
the assistant opens. If the record system is slow, the page says what it is waiting for and how long it took.
The Sikkerhetssenter shows the record system's response time (median, and what 9 of 10 calls stay under).
Only durations are stored: no people, no patients.

**Pick the patient first.** A search field at the top drops down the doctor's own patients
(search by name, birth date or fødselsnummer). With a patient chosen, the approved note is saved
straight into their record: through the health network, or into **DIPS Arena** over FHIR R4.
Without one, the note can still be copied into any other system.

**Moving from Epic:** under *Overføring*, a patient's Epic export (FHIR R4) is shown for checking and
then imported into their record. Allergies and medicines come in marked "must be checked". See
[docs/journalsystemer.md](docs/journalsystemer.md) for DIPS and Epic.

**The hospital's own system next to Medicus:** IT can add the record system the hospital already uses
(DIPS Arena, Epic, …) as an icon in the Start menu. It opens either as a locked-down remote window or
as its web version in Nettleser.
- **Login:** the remote window logs in with the same card, so there is no second login.
- **Nothing shared:** no disks, clipboard, USB or printers are shared with the server.
- **Network:** the firewall opens only the servers IT listed.

**Everything runs on the local machine.** No audio or text is sent to any cloud service.

**The patient decides.** Before a recording starts, Medicus shows the clinician what to tell the
patient and asks for their answer. Without a "yes" the server refuses to transcribe, and the answer
is logged. If the patient changes their mind, one button throws the recording away unsent. The audio
is deleted as soon as it has been transcribed, and the approved note says that the patient agreed.

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

## Trying the web app on a developer PC (Windows)

This runs **only the web app** (patient record, Post, journal assistant) with the simulator, for
development and demos. None of the lockdown is there: no card login, firewall, USB lock or session
rules. Those are part of **Medicus OS**, the hardened Debian system that boots straight into Medicus;
see [Building the ISO](#building-the-iso).

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
- [x] Post: verified messages, DICOM image sharing, phishing warnings
- [x] VPN with kill switch, Wi-Fi hardening, firewall rate limits
- [ ] Connect a radiology/lab provider's image archive (needs an agreement)
- [x] Nettleser, virus scanning, security log, Sikkerhetssenter, no-exec home folders
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
