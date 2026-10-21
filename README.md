# Medicus

A local, privacy-first AI documentation assistant ("journalassistent") for Norwegian healthcare.

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
- [ ] Hardened Linux image (based on Debian) that boots straight into Medicus
- [ ] Clinician testing and time-saving measurements
- [ ] Assess medical-device classification (EU MDR) and compliance with Normen and GDPR
