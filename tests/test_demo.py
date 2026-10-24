import time

import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
from epj import HelsenettJournal
from helsenett.client import SimulatedClient
from helsenett.sim.app import create_app
from medicus import demo


@pytest.fixture
def web(tmp_path, monkeypatch):
    sim = TestClient(create_app(tmp_path / "sim.json"))
    monkeypatch.delenv("MEDICUS_DEV_IDENTITY", raising=False)
    monkeypatch.setattr(medicus_app, "settings", medicus_app.settings.__class__(demo=True, warmup=False))
    monkeypatch.setattr(medicus_app, "helsenett", lambda: SimulatedClient("http://sim", http=sim))
    monkeypatch.setattr(medicus_app, "journal", lambda: HelsenettJournal(SimulatedClient("http://sim", http=sim)))
    monkeypatch.setattr(medicus_app, "audit", medicus_app.AuditLog(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(medicus_app, "patient_lists", {})
    monkeypatch.setattr(demo, "visitors", {})
    return lambda: TestClient(medicus_app.app, follow_redirects=False)


def site():
    return demo.load_sites()[0].id


def login(browser, card="lege", pin="1234"):
    return browser.post("/api/demo/logginn", json={"kort": card, "pin": pin, "arbeidssted": site()})


def test_the_demo_is_off_unless_switched_on(tmp_path, monkeypatch):
    monkeypatch.setattr(medicus_app, "settings", medicus_app.settings.__class__(demo=False))
    browser = TestClient(medicus_app.app)
    assert browser.get("/demo").status_code == 404
    assert browser.post("/api/demo/logginn", json={"kort": "lege", "pin": "1234", "arbeidssted": site()}).status_code == 404


def test_pages_send_a_new_visitor_to_the_card_picker(web):
    browser = web()
    for page in ("/", "/pasient", "/post", "/sikkerhet"):
        reply = browser.get(page)
        assert reply.status_code == 303 and reply.headers["location"] == "/demo"
    assert browser.get("/demo").status_code == 200
    assert browser.get("/api/meg").status_code == 401
    info = browser.get("/api/demo").json()
    assert info["okt"] is None and {c["kort"] for c in info["kort"]} >= {"lege", "spl"}


def test_card_and_pin_log_in_and_each_browser_has_its_own_session(web):
    alice, bob = web(), web()
    reply = login(alice)
    assert reply.status_code == 200 and reply.json() == {"modus": "normal", "til": "/demo"}
    cookie = reply.cookies.get(demo.COOKIE)
    assert cookie and "httponly" in reply.headers["set-cookie"].lower()
    assert alice.get("/api/meg").json()["navn"] == "Ingrid Berg"
    assert alice.get("/").status_code == 200
    assert bob.get("/api/meg").status_code == 401
    alice.post("/api/demo/loggut")
    assert alice.get("/api/meg").status_code == 401


def test_three_wrong_pins_block_the_card_for_that_browser_only(web):
    alice, bob = web(), web()
    assert login(alice, pin="0000").json()["detail"] == "Feil PIN. 2 forsøk igjen."
    assert login(alice, pin="0000").json()["detail"] == "Feil PIN. 1 forsøk igjen."
    assert login(alice, pin="0000").json()["detail"] == "Feil PIN. Kortet er nå sperret."
    assert login(alice).status_code == 423  # even the right PIN
    assert next(c for c in alice.get("/api/demo").json()["kort"] if c["kort"] == "lege")["sperret"]
    assert login(bob).status_code == 200
    alice.post("/api/demo/nullstill")
    assert login(alice).status_code == 200


def test_it_card_opens_the_security_centre(web):
    browser = web()
    it = next(c for c in demo.load_cards().values() if c["rolle"] == "IT")
    reply = login(browser, it["card_id"])
    assert reply.json() == {"modus": "it", "til": "/sikkerhet"}
    assert browser.get("/sikkerhet").status_code == 200
    assert browser.post("/api/demo/nod", json={"kort": it["card_id"], "situasjon": "Hjertestans",
                                                "arbeidssted": site()}).status_code == 403


def test_emergency_access_needs_a_report_afterwards(web, monkeypatch):
    browser = web()
    reply = browser.post("/api/demo/nod", json={"kort": "spl", "situasjon": "Hjertestans", "arbeidssted": site()})
    assert reply.json() == {"modus": "nød", "til": "/nod"}
    me = browser.get("/api/meg").json()
    assert me["modus"] == "nød" and 0 < me["sekunder_igjen"] <= 30 * 60
    browser.post("/api/nod/avslutt")
    assert login(browser, "spl").status_code == 200
    reports = browser.get("/api/meg").json()["rapporter"]
    assert len(reports) == 1
    too_short = browser.post("/api/nodrapport", json={"id": reports[0]["id"], "tekst": "kort"})
    assert too_short.status_code == 422
    text = "Pasienten fikk hjertestans på venterommet. Jeg åpnet kritisk informasjon for å se allergier."
    assert browser.post("/api/nodrapport", json={"id": reports[0]["id"], "tekst": text}).status_code == 200
    assert browser.get("/api/meg").json()["rapporter"] == []


def test_emergency_access_closes_after_thirty_minutes(web, monkeypatch):
    browser = web()
    browser.post("/api/demo/nod", json={"kort": "spl", "situasjon": "Hjertestans", "arbeidssted": site()})
    later = time.time() + 31 * 60
    monkeypatch.setattr(demo.time, "time", lambda: later)
    assert browser.get("/api/meg").status_code == 401


def test_only_the_example_conversation_becomes_a_note_and_recording_is_off(web):
    browser = web()
    login(browser)
    sample = demo.SAMPLE.read_text(encoding="utf-8")
    note = browser.post("/api/note", json={"transcript": sample}).json()
    assert "klaritromycin" in note["text"].lower()
    assert note["kilder"]["uten_kilde"] == 0  # every sentence of the example note is in the conversation
    assert browser.post("/api/note", json={"transcript": "Pasienten har vondt i ryggen."}).status_code == 422
    assert browser.post("/api/transcribe", files={"audio": ("a.wav", b"RIFF", "audio/wav")}).status_code == 403


def test_the_example_note_only_says_what_the_conversation_said():
    """The fixed note must pass the same source check as a real one: every number is in the transcript."""
    import json
    import re
    sample = demo.SAMPLE.read_text(encoding="utf-8").lower()
    note = json.loads(demo.EXAMPLE_NOTE.read_text(encoding="utf-8"))
    for text in note.values():
        for number in re.findall(r"\d+", text):
            assert number in sample, number


def test_old_visitors_are_forgotten(web, monkeypatch):
    monkeypatch.setattr(demo, "MAX_VISITORS", 3)
    browsers = [web() for _ in range(5)]
    for b in browsers:
        login(b)
    assert len(demo.visitors) <= 3
    assert browsers[-1].get("/api/meg").status_code == 200
