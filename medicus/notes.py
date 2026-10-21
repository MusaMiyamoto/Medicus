"""Turn a consultation transcript into a structured journal note using a local LLM (Ollama)."""

import json

import httpx

from .config import settings

SECTIONS = [
    ("kontaktarsak", "Kontaktårsak"),
    ("anamnese", "Anamnese"),
    ("funn", "Funn"),
    ("vurdering", "Vurdering"),
    ("plan", "Plan"),
]

MISSING = "Ikke nevnt."

SYSTEM_PROMPT = f"""Du er en assistent som skriver journalnotat for norsk helsepersonell.
Du får en transkripsjon av en konsultasjon mellom lege og pasient.
Skriv et kort, saklig journalnotat på bokmål, i medisinsk fagspråk.

Regler:
- Bruk KUN informasjon som faktisk står i transkripsjonen.
- Ikke finn på funn, diagnoser, legemidler, doser eller tall.
- Hvis noe ikke er nevnt, skriv "{MISSING}"
- Ikke ta med småprat som ikke er medisinsk relevant.

Svar KUN med JSON med disse nøklene: {", ".join(key for key, _ in SECTIONS)}."""


class NoteError(Exception):
    pass


def parse_note(raw: str) -> dict[str, str]:
    """Parse the model's JSON reply into exactly our sections, filling gaps."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise NoteError("Språkmodellen returnerte ikke gyldig JSON.") from e
    if not isinstance(data, dict):
        raise NoteError("Språkmodellen returnerte et uventet format.")

    note = {}
    for key, _ in SECTIONS:
        value = data.get(key)
        if isinstance(value, list):
            value = "\n".join(f"- {item}" for item in value)
        elif value is not None and not isinstance(value, str):
            value = str(value)
        note[key] = value.strip() if value and value.strip() else MISSING
    return note


def format_note(note: dict[str, str]) -> str:
    """Plain text, ready to paste into a patient record system."""
    return "\n\n".join(f"{label}:\n{note.get(key, MISSING)}" for key, label in SECTIONS)


def generate_note(transcript: str, post=httpx.post) -> dict[str, str]:
    if not transcript.strip():
        raise NoteError("Transkripsjonen er tom.")
    try:
        response = post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": transcript},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=600,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise NoteError(
            f"Fikk ikke kontakt med språkmodellen ({settings.llm_model}). Kjører Ollama?"
        ) from e
    return parse_note(response.json()["message"]["content"])
