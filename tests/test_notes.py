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


def _reply(url, content):
    return httpx.Response(200, json={"message": {"content": content}}, request=httpx.Request("POST", url))


def test_generate_note_asks_once_more_after_broken_json():
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json["messages"])
        return _reply(url, "ikke json" if len(calls) == 1 else '{"plan": "Kontroll om en uke"}')

    note = notes.generate_note("Lege: Kontroll om en uke.", post=fake_post)
    assert note["plan"] == "Kontroll om en uke"
    assert len(calls) == 2 and calls[1][-1]["content"] == notes.RETRY_PROMPT
    assert len(calls[0]) == 2  # the first ask is not changed by the retry


def test_generate_note_gives_up_after_the_second_broken_reply():
    calls = []

    def fake_post(url, json, timeout):
        calls.append(1)
        return httpx.Response(200, json={"uventet": True}, request=httpx.Request("POST", url))

    with pytest.raises(notes.NoteError, match="uventet format"):
        notes.generate_note("Hei", post=fake_post)
    assert len(calls) == 2


def test_generate_note_uses_the_settings(monkeypatch):
    sent = {}
    monkeypatch.setattr(notes, "settings", notes.settings.__class__(llm_temperature=0.0, llm_timeout=42))

    def fake_post(url, json, timeout):
        sent.update(options=json["options"], timeout=timeout)
        return _reply(url, "{}")

    notes.generate_note("Hei", post=fake_post)
    assert sent == {"options": {"temperature": 0.0}, "timeout": 42}


def test_generate_note_refuses_a_too_long_transcript(monkeypatch):
    monkeypatch.setattr(notes, "settings", notes.settings.__class__(llm_max_chars=10))
    with pytest.raises(notes.NoteError, match="for lang"):
        notes.generate_note("x" * 11, post=lambda *a, **k: pytest.fail("must not call the model"))


def test_parse_cuts_a_runaway_section(monkeypatch):
    monkeypatch.setattr(notes, "settings", notes.settings.__class__(note_max_chars=5))
    assert notes.parse_note(json.dumps({"plan": "abcdefghij"}))["plan"] == "abcde"
