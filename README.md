# Medicus

A hardened, Linux-based operating system for Norwegian healthcare workers, with a local,
privacy-first AI documentation assistant ("journalassistent") and a clinical calculator.

The project has three parts:

| Part | Folder | What it is |
|---|---|---|
| **Medicus OS** | [`os/`](os/) | Debian 13 Linux with an XFCE desktop and a Start menu, built as a bootable ISO |
| **Medicus Kalkulator** | [`kalkulator/`](kalkulator/) | Calculator plus converters for volume, weight and gram ↔ milliliter |
| **Medicus Journalassistent** | [`medicus/`](medicus/) | Turns a recorded consultation into a draft journal note |

## Medicus OS

A live ISO you can boot in a virtual machine (VirtualBox, VMware, Hyper-V) or from a USB stick.

- **Desktop:** XFCE with one bottom panel and a **Start** button. The Start menu's favorites are
  Medicus Journalassistent, Medicus Kalkulator, Firefox, the file manager and the terminal.
- **Norwegian by default:** language `nb_NO`, Norwegian keyboard, Oslo time zone.
- **Hardened:**
  - Firewall (nftables) blocks all incoming connections.
  - Screen locks after 5 minutes without activity.
  - AppArmor on, kernel hardening settings in `/etc/sysctl.d/90-medicus.conf`.
    (Debian skips loading AppArmor profiles in the *live* session; they load once the OS is installed.)
  - Automatic daily security updates.
  - No remote-login (SSH) server.
  - The journal assistant runs as its own locked-down service user that can't reach the network.
- **Installer:** the desktop includes the Calamares installer, which can install to disk with full-disk encryption.

Live session login: user `bruker`, password `live` (the live-build default). Change it after installing.

### Building the ISO

You need Debian, either on a real machine or in WSL on Windows (`wsl --install -d Debian`).

```bash
sudo apt install live-build rsync
```
```bash
sudo sh os/build.sh /path/to/output-folder
```

The first build downloads 1–2 GB and takes a while. Later builds reuse the download cache in `/var/tmp/medicus-os`.

## Medicus Kalkulator

A GTK 4 desktop app in the Start menu:

- **Kalkulator:** + − × ÷ and parentheses, with a decimal comma (`2,5 × 4`).
- **Volum:** ml, dl, liter. Type an amount and see it in every unit at once.
- **Vekt:** mg, gram, hektogram, kilo.
- **Gram ↔ milliliter:** uses the substance's **density**. Water (1 g/ml) is the default,
  there are presets for milk, olive oil, honey and ethanol, or you can type your own density.
  The result always shows which density was used.

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
- [ ] Login with HelseID
- [ ] Pick different note templates (GP, emergency room, home care, psychiatry)
- [ ] Send notes to patient record systems via FHIR instead of copy and paste
- [x] Hardened Linux OS image (Debian + XFCE) with a Start menu
- [x] Calculator with volume, weight and gram ↔ milliliter converters
- [ ] Download the AI models (Ollama and Whisper) during OS setup, so the journal assistant works offline out of the box
- [ ] Medicus branding: wallpaper, boot screen, installer
- [ ] Clinician testing and time-saving measurements
- [ ] Assess medical-device classification (EU MDR) and compliance with Normen and GDPR
