import json

import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
from helsenett.client import SimulatedClient
from helsenett.sim import seed
from helsenett.sim.app import create_app

DOCTOR = {**seed.BERG, "modus": "normal"}
NURSE = {**seed.LIE, "modus": "normal"}
EMERGENCY = {**seed.LIE, "modus": "nød", "begrunnelse": "Bevisstløs pasient", "sekunder_igjen": 1700}


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
    assert latest["modus"] == "nød" and latest["begrunnelse"] == "Bevisstløs pasient"


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
