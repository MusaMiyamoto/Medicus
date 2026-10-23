import json

import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
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
    monkeypatch.setattr(medicus_app, "audit", medicus_app.AuditLog(tmp_path / "audit.jsonl"))

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
    checks = app.get("/api/sikkerhet").json()
    assert checks[-1]["navn"] == "Nødtilgangsrapporter" and checks[-1]["status"] == "ok"


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
