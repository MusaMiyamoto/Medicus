import json

import httpx
import pytest

from medicus import notes


def test_parse_fills_missing_sections():
    note = notes.parse_note(json.dumps({"kontaktarsak": "Sår hals", "plan": ""}))
    assert note["kontaktarsak"] == "Sår hals"
    assert note["plan"] == notes.MISSING
    assert note["funn"] == notes.MISSING
    assert list(note) == [key for key, _ in notes.SECTIONS]


def test_parse_turns_lists_into_bullets():
    note = notes.parse_note(json.dumps({"plan": ["Klaritromycin", "Kontroll ved behov"]}))
    assert note["plan"] == "- Klaritromycin\n- Kontroll ved behov"


@pytest.mark.parametrize("raw", ["not json", "[1, 2]"])
def test_parse_rejects_bad_output(raw):
    with pytest.raises(notes.NoteError):
        notes.parse_note(raw)


def test_format_note_uses_labels():
    text = notes.format_note(notes.parse_note(json.dumps({"funn": "Belegg på tonsiller"})))
    assert "Funn:\nBelegg på tonsiller" in text
    assert text.startswith("Kontaktårsak:")


def test_generate_note_calls_local_model():
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, body=json)
        reply = {"message": {"content": '{"vurdering": "Streptokokktonsillitt"}'}}
        return httpx.Response(200, json=reply, request=httpx.Request("POST", url))

    note = notes.generate_note("Lege: Testen er positiv.", post=fake_post)
    assert note["vurdering"] == "Streptokokktonsillitt"
    assert sent["url"].endswith("/api/chat")
    assert sent["body"]["messages"][1]["content"] == "Lege: Testen er positiv."


def test_generate_note_reports_unreachable_model():
    def failing_post(url, json, timeout):
        raise httpx.ConnectError("refused")

    with pytest.raises(notes.NoteError, match="Ollama"):
        notes.generate_note("Hei", post=failing_post)


def test_generate_note_rejects_empty_transcript():
    with pytest.raises(notes.NoteError):
        notes.generate_note("   ")
