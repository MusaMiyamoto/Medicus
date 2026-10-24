import json

import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
from epj import HelsenettJournal
from helsenett.client import SimulatedClient
from helsenett.sim import seed
from helsenett.sim.app import create_app

DOCTOR = {**seed.BERG, "modus": "normal"}
NURSE = {**seed.LIE, "modus": "normal"}
EMERGENCY = {**seed.LIE, "modus": "nød", "situasjon": "Bevisstløs pasient", "sekunder_igjen": 1700}
IT = {"navn": "Eirik Strand", "rolle": "IT", "hpr": "IT-4401", "virksomhet": "Oslo universitetssykehus", "modus": "it"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    sim = TestClient(create_app(tmp_path / "sim.json"))
    monkeypatch.setattr(medicus_app, "helsenett", lambda: SimulatedClient("http://sim", http=sim))
    monkeypatch.setattr(medicus_app, "journal", lambda: HelsenettJournal(SimulatedClient("http://sim", http=sim)))
    monkeypatch.setattr(medicus_app, "audit", medicus_app.AuditLog(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(medicus_app, "patient_lists", {})
    monkeypatch.setattr(medicus_app, "response_times", medicus_app.deque(maxlen=200))

    def login(session):
        if session is None:
            monkeypatch.delenv("MEDICUS_DEV_IDENTITY", raising=False)
            monkeypatch.setattr(medicus_app, "auth_call", lambda *a, **k: {"okt": None})
        else:
            monkeypatch.setenv("MEDICUS_DEV_IDENTITY", json.dumps(session))

    return TestClient(medicus_app.app), sim, login


def test_not_logged_in_gets_nothing(env):
    app, _sim, login = env
    login(None)
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 401
    assert app.get(f"/api/nod/pasient/{seed.OLA}").status_code == 403


def test_held_session_after_card_out_gets_nothing(env, monkeypatch):
    app, _sim, login = env
    login(None)
    monkeypatch.setattr(medicus_app, "auth_call", lambda *a, **k: {"okt": {**DOCTOR, "holdt_sekunder_igjen": 600}})
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 401


def test_opening_a_record_notifies_the_patient(env):
    app, sim, login = env
    login(DOCTOR)
    record = app.get(f"/api/pasient/{seed.KARI}").json()
    assert record["kritisk"]["implantater"][0]["navn"] == "Pacemaker"
    latest = sim.get(f"/api/innsyn/{seed.KARI}").json()[0]
    assert latest["aktor"]["navn"] == "Ingrid Berg" and latest["modus"] == "normal"


def test_emergency_session_sees_only_critical_info(env):
    app, sim, login = env
    login(EMERGENCY)
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 403
    info = app.get(f"/api/nod/pasient/{seed.OLA}").json()
    assert "kontakter" not in info and info["allergier"]
    latest = sim.get(f"/api/innsyn/{seed.OLA}").json()[0]
    assert latest["modus"] == "nød" and latest["begrunnelse"] == "Nødtilgang: Bevisstløs pasient"


def test_normal_session_cannot_use_emergency_page(env):
    app, _sim, login = env
    login(DOCTOR)
    assert app.get(f"/api/nod/pasient/{seed.OLA}").status_code == 403


def test_nurse_cannot_prescribe(env):
    app, _sim, login = env
    login(NURSE)
    body = {"legemiddel": "Paracet", "dosering": "1 g", "indikasjon": "Smerter"}
    assert app.post(f"/api/pasient/{seed.OLA}/resept", json=body).status_code == 403
    login(DOCTOR)
    assert app.post(f"/api/pasient/{seed.OLA}/resept", json=body).status_code == 200


def test_invalid_number_is_rejected_before_network(env):
    app, _sim, login = env
    login(DOCTOR)
    assert app.get("/api/pasient/12345678901").status_code == 422


def test_journal_assistant_requires_login(env):
    app, _sim, login = env
    login(None)
    assert app.post("/api/note", json={"transcript": "hei"}).status_code == 401
    assert app.post("/api/kildesjekk", json={"transcript": "hei", "seksjoner": {}}).status_code == 401


def test_draft_comes_with_its_source_check(env, monkeypatch):
    app, _sim, login = env
    login(DOCTOR)
    draft = {"kontaktarsak": "Vondt i halsen.", "anamnese": "Ikke nevnt.", "funn": "Lungene normale.",
             "vurdering": "Ikke nevnt.", "plan": "Ikke nevnt."}
    monkeypatch.setattr(medicus_app.notes, "generate_note", lambda transcript: draft)
    data = app.post("/api/note", json={"transcript": "Pasient: Jeg har vondt i halsen."}).json()
    assert data["kilder"]["uten_kilde"] == 1
    assert data["kilder"]["seksjoner"]["kontaktarsak"][0]["status"] == "støttet"
    edited = {**draft, "funn": "Ikke nevnt."}
    again = app.post("/api/kildesjekk", json={"transcript": "Pasient: Jeg har vondt i halsen.", "seksjoner": edited})
    assert again.json()["uten_kilde"] == 0
    too_long = app.post("/api/kildesjekk", json={"transcript": "x", "seksjoner": {"funn": "x" * 60_000}})
    assert too_long.status_code == 413


def test_patient_list_is_fetched_once_per_login_and_timed(env, monkeypatch):
    app, _sim, login = env
    calls = []

    class Journal:
        name = "Test"

        def my_patients(self, who):
            calls.append(who["hpr"])
            return [{"fnr": "1", "navn": "A"}]
    monkeypatch.setattr(medicus_app, "journal", Journal)
    login({**DOCTOR, "startet": "2026-10-24T08:00:00"})
    assert app.get("/api/journal/pasienter").json()["pasienter"] == [{"fnr": "1", "navn": "A"}]
    app.get("/api/journal/pasienter")
    assert len(calls) == 1  # the second time comes from memory (fetched at login by medicus-forhent)
    app.get("/api/journal/pasienter?oppdater=true")
    assert len(calls) == 2
    login({**DOCTOR, "startet": "2026-10-24T14:00:00"})  # a new login never sees an old list
    app.get("/api/journal/pasienter")
    login({**NURSE, "startet": "2026-10-24T14:00:00"})  # nor does another person
    app.get("/api/journal/pasienter")
    assert len(calls) == 4 and len(medicus_app.response_times) == 4
    monkeypatch.setattr(medicus_app.time, "monotonic", lambda: 10**9)  # much later: expired
    login({**NURSE, "startet": "2026-10-24T14:00:00"})
    app.get("/api/journal/pasienter")
    assert len(calls) == 5


def test_it_mode_never_sees_patient_data(env):
    app, _sim, login = env
    login(IT)
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 403
    assert app.get(f"/api/nod/pasient/{seed.OLA}").status_code == 403
    assert app.get("/api/pasienter").status_code == 403
    assert app.get("/api/sample").status_code == 403


def test_security_center_is_only_for_it_mode(env, monkeypatch):
    app, _sim, login = env
    monkeypatch.setattr(medicus_app.sikkerhet, "checks", lambda: [])
    monkeypatch.setattr(medicus_app, "auth_call", lambda cmd, **_: {"rapporter": []})
    login(DOCTOR)
    assert app.get("/api/sikkerhet").status_code == 403
    login(IT)
    checks = {c["navn"]: c for c in app.get("/api/sikkerhet").json()}
    assert checks["Nødtilgangsrapporter"]["status"] == "ok" and "Medisinsk USB-utstyr" in checks


def test_emergency_report_is_passed_to_the_login_service(env, monkeypatch):
    app, _sim, login = env
    sent = {}
    monkeypatch.setattr(medicus_app, "auth_call", lambda cmd, **kw: sent.update(cmd=cmd, **kw) or {"rapport": {"id": "r1"}})
    login(NURSE)
    reply = app.post("/api/nodrapport", json={"id": "r1", "tekst": "Pasient funnet bevisstløs, trengte allergier."})
    assert reply.status_code == 200 and sent["cmd"] == "report" and sent["id"] == "r1"


def test_recording_needs_the_patients_yes(env):
    app, _sim, login = env
    login(DOCTOR)
    medicus_app.consents.clear()
    audio = {"audio": ("opptak.webm", b"lyd", "audio/webm")}
    assert app.post("/api/transcribe", files=audio).status_code == 403
    assert app.post("/api/samtykke", json={"svar": "kanskje"}).status_code == 422
    app.post("/api/samtykke", json={"svar": "ja"})
    assert medicus_app.has_consent(DOCTOR)
    app.delete("/api/samtykke")
    assert not medicus_app.has_consent(DOCTOR)
    app.post("/api/samtykke", json={"svar": "nei"})
    assert app.post("/api/transcribe", files=audio).status_code == 403
    actions = [json.loads(line)["action"] for line in medicus_app.audit.path.read_text().splitlines()]
    assert actions.count("recording_consent") == 2 and "recording_consent_withdrawn" in actions


def test_unfinished_note_survives_the_session_but_only_for_its_author(env, monkeypatch):
    app, _sim, login = env
    monkeypatch.setattr(medicus_app, "drafts", {})
    login(DOCTOR)
    assert app.get("/api/utkast").json() == {"utkast": None}
    draft = {"transcript": "Pasient: vondt i halsen", "seksjoner": {"funn": "Røde mandler."}, "fnr": seed.KARI}
    assert app.put("/api/utkast", json=draft).json() == {"lagret": True}
    login(NURSE)  # someone else on the same PC sees nothing
    assert app.get("/api/utkast").json() == {"utkast": None}
    login(DOCTOR)  # the author, in a new session
    back = app.get("/api/utkast").json()["utkast"]
    assert back["seksjoner"] == {"funn": "Røde mandler."} and back["fnr"] == seed.KARI and ":" in back["lagret_kl"]
    app.post("/api/approve", json={"note": "Funn: Røde mandler.", "fnr": ""})
    assert app.get("/api/utkast").json() == {"utkast": None}  # approved: gone


def test_drafts_expire_can_be_discarded_and_need_a_normal_login(env, monkeypatch):
    app, _sim, login = env
    monkeypatch.setattr(medicus_app, "drafts", {})
    login(DOCTOR)
    app.put("/api/utkast", json={"transcript": "x", "seksjoner": {}})
    assert app.delete("/api/utkast").json() == {"ok": True}
    assert app.get("/api/utkast").json() == {"utkast": None}
    app.put("/api/utkast", json={"transcript": "x", "seksjoner": {}})
    monkeypatch.setattr(medicus_app.time, "time", lambda: 10**11)  # long after the shift
    assert app.get("/api/utkast").json() == {"utkast": None}
    assert app.put("/api/utkast", json={"transcript": "", "seksjoner": {"funn": " "}}).json() == {"lagret": False}
    assert app.put("/api/utkast", json={"transcript": "x", "seksjoner": {}, "fnr": "1" * 12}).status_code == 422
    for who in (IT, EMERGENCY, None):
        login(who)
        assert app.get("/api/utkast").status_code in (401, 403)


def test_patient_outside_own_list_needs_a_reason_the_patient_can_see(env, monkeypatch):
    app, sim, login = env
    login(NURSE)  # Jonas Lie has seen Ola and Sofie at the legevakt, never Kari
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 200
    start = len(sim.get(f"/api/innsyn/{seed.KARI}").json())
    refused = app.get(f"/api/pasient/{seed.KARI}")
    assert refused.status_code == 409 and refused.json()["detail"]["begrunnelse_kreves"]
    assert "Vakt" in refused.json()["detail"]["valg"]
    before = len(sim.get(f"/api/innsyn/{seed.KARI}").json())
    assert before == start  # refusing read nothing and logged nothing
    url = f"/api/pasient/{seed.KARI}/apne"
    assert app.post(url, json={"begrunnelse": "Fordi jeg vil"}).status_code == 422
    assert app.post(url, json={"begrunnelse": "Annet", "forklaring": "  sjekk  "}).status_code == 422
    opened = app.post(url, json={"begrunnelse": "Vakt", "forklaring": "Ringte  om\nbrystsmerter"})
    assert opened.status_code == 200 and opened.json()["kritisk"]["implantater"]
    log = sim.get(f"/api/innsyn/{seed.KARI}").json()
    assert len(log) == before + 1 and log[0]["begrunnelse"] == "Vakt: Ringte om brystsmerter"
    last = json.loads(medicus_app.audit.path.read_text().splitlines()[-1])
    assert last["action"] == "patient_opened_with_reason"


def test_reason_is_asked_for_when_the_patient_list_is_unavailable(env, monkeypatch):
    app, _sim, login = env

    class Down:
        name = "Test"

        def my_patients(self, who):
            raise ConnectionError("journal system down")
    monkeypatch.setattr(medicus_app, "journal", Down)
    login(DOCTOR)
    assert app.get(f"/api/pasient/{seed.OLA}").status_code == 409  # not blocked: asked why
    assert app.post(f"/api/pasient/{seed.OLA}/apne", json={"begrunnelse": "Pasienten er hos meg nå"}).status_code == 200
    login(IT)
    assert app.post(f"/api/pasient/{seed.OLA}/apne", json={"begrunnelse": "Vakt"}).status_code == 403


def test_patient_data_is_never_cached_and_pages_are_always_revalidated(env):
    app, _sim, login = env
    login(DOCTOR)
    assert app.get(f"/api/pasient/{seed.OLA}").headers["cache-control"] == "no-store"
    assert app.get("/api/meg").headers["cache-control"] == "no-store"
    assert app.get("/static/common.js").headers["cache-control"] == "no-cache"
    assert app.get("/pasient").headers["cache-control"] == "no-cache"


def test_too_large_recording_is_refused_while_it_streams(env, monkeypatch, tmp_path):
    app, _sim, login = env
    login(DOCTOR)
    medicus_app.consents.clear()
    app.post("/api/samtykke", json={"svar": "ja"})
    monkeypatch.setattr(medicus_app, "settings", medicus_app.settings.__class__(upload_max_mb=1))
    seen = []
    monkeypatch.setattr("medicus.transcribe.transcribe", lambda path: (seen.append(path), ("Hei", 2.0))[1])
    monkeypatch.setattr(medicus_app.tempfile, "tempdir", str(tmp_path))

    big = {"audio": ("opptak.webm", b"x" * (1024 * 1024 + 1), "audio/webm")}
    reply = app.post("/api/transcribe", files=big)
    assert reply.status_code == 413 and "1 MB" in reply.json()["detail"]
    assert not seen and not list(tmp_path.glob("*.webm"))  # never transcribed, and the part file is gone

    small = {"audio": ("opptak.webm", b"x" * 1000, "audio/webm")}
    assert app.post("/api/transcribe", files=small).json() == {"transcript": "Hei"}
    assert len(seen) == 1 and not list(tmp_path.glob("*.webm"))
    actions = [json.loads(line)["action"] for line in medicus_app.audit.path.read_text().splitlines()]
    assert "transcribe_refused_too_large" in actions and "transcribe" in actions


def test_failed_note_logs_only_the_kind_of_error(env, monkeypatch):
    app, _sim, login = env
    login(DOCTOR)

    def unreachable(transcript):
        raise medicus_app.notes.NoteError("Fikk ikke kontakt") from ConnectionRefusedError("detaljer")

    monkeypatch.setattr(medicus_app.notes, "generate_note", unreachable)
    assert app.post("/api/note", json={"transcript": "Pasient: hei"}).status_code == 502
    last = json.loads(medicus_app.audit.path.read_text().splitlines()[-1])
    assert last["action"] == "note_failed" and last["details"] == {"error": "ConnectionRefusedError"}


def test_broken_audit_chain_is_found_at_start(env, monkeypatch):
    _app, _sim, _login = env
    monkeypatch.setattr(medicus_app, "settings", medicus_app.settings.__class__(warmup=False))
    monkeypatch.setattr(medicus_app, "audit_at_start", {})
    assert medicus_app.audit_chain_check()["status"] == "info"

    medicus_app.audit.record("999000101", "patient_opened", {"patient": "123456*****"})
    with TestClient(medicus_app.app):
        pass
    assert medicus_app.audit_chain_check()["status"] == "ok"

    path = medicus_app.audit.path
    path.write_text(path.read_text().replace("patient_opened", "patient_closed"))
    with TestClient(medicus_app.app):
        pass
    check = medicus_app.audit_chain_check()
    assert check["status"] == "feil" and "linje 1" in check["forklaring"]
    assert json.loads(path.read_text().splitlines()[-1])["action"] == "audit_chain_broken_at_start"
