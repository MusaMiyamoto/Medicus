import json

import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
from helsenett import bilder
from helsenett.client import SimulatedClient
from helsenett.sim import seed
from helsenett.sim.app import create_app

BERG, LIE, MOE = seed.BERG, seed.LIE, seed.MOE


def as_(actor):
    return {"X-Medicus-HPR": actor["hpr"]}


@pytest.fixture
def sim(tmp_path):
    return TestClient(create_app(tmp_path / "sim.json"))


def test_inbox_needs_known_identity(sim):
    assert sim.get("/api/post/innboks").status_code == 401
    assert sim.get("/api/post/innboks", headers={"X-Medicus-HPR": "123"}).status_code == 401


def test_inbox_marks_trust_level(sim):
    inbox = sim.get("/api/post/innboks", headers=as_(BERG)).json()
    levels = {m["emne"]: m["nivå"] for m in inbox}
    assert levels["Røntgen thorax – Ola Nordmann"] == "verifisert"
    assert levels["Kontoen din blir stengt – handling kreves"] == "mistenkelig"
    assert levels["Passordet ditt utløper i dag"] == "mistenkelig"
    assert levels["Nye nitrilhansker på lager"] == "ekstern"


def test_others_cannot_read_your_mail(sim):
    first = sim.get("/api/post/innboks", headers=as_(BERG)).json()[0]
    assert sim.get(f"/api/post/{first['id']}", headers=as_(LIE)).status_code == 404


def test_seeded_xray_is_a_viewable_dicom(sim):
    xray = next(m for m in sim.get("/api/post/innboks", headers=as_(BERG)).json() if m["emne"].startswith("Røntgen"))
    msg = sim.get(f"/api/post/{xray['id']}", headers=as_(BERG)).json()
    attachment = msg["vedlegg"][0]
    assert attachment["type"] == "dicom" and attachment["dicom"]["modalitet"] == "DX"
    png = sim.get(f"/api/post/vedlegg/{attachment['id']}/visning", headers=as_(BERG))
    assert png.headers["content-type"] == "image/png" and png.content.startswith(b"\x89PNG")
    assert sim.get(f"/api/post/vedlegg/{attachment['id']}", headers=as_(LIE)).status_code == 404


def send(sim, sender, files=(), fnr=""):
    return sim.post("/api/post", data={"aktor": json.dumps(sender), "til": [f"hpr:{LIE['hpr']}"],
                                       "emne": "Bilder", "tekst": "Se vedlegg", "fnr": fnr},
                    files=[("filer", f) for f in files] or None)


def test_send_image_linked_to_patient_notifies_patient(sim):
    dcm = bilder.synthetic_dicom("Sofie Hansen", seed.SOFIE, "DX", "Røntgen håndledd", "WRIST")
    reply = send(sim, BERG, [("hand.dcm", dcm, "application/dicom")], fnr=seed.SOFIE)
    assert reply.status_code == 200
    inbox = sim.get("/api/post/innboks", headers=as_(LIE)).json()
    assert inbox[0]["nivå"] == "verifisert" and inbox[0]["vedlegg"] == 1
    latest = sim.get(f"/api/innsyn/{seed.SOFIE}").json()[0]
    assert "sendt til Jonas Lie" in latest["hva"]


@pytest.mark.parametrize("content", [b"MZ\x90\x00 fake exe", b"<html>hi</html>"])
def test_only_images_and_pdf_can_be_attached(sim, content):
    assert send(sim, BERG, [("bilde.png", content, "image/png")]).status_code == 422


def test_unknown_recipient_rejected(sim):
    reply = sim.post("/api/post", data={"aktor": json.dumps(BERG), "til": ["hpr:000"], "emne": "x", "tekst": "x"})
    assert reply.status_code == 422


def test_external_gateway_checks_new_mail(sim):
    reply = sim.post("/api/post/ekstern", json={
        "navn": "NAV", "adresse": "post@nav-utbetaling.com", "til": [f"hpr:{BERG['hpr']}"],
        "emne": "Utbetaling stoppet", "tekst": "Bekreft fødselsnummer umiddelbart.", "vedlegg_navn": []})
    assert reply.json()["vurdering"]["nivå"] == "mistenkelig"


def test_reporting_marks_message(sim):
    phish = next(m for m in sim.get("/api/post/innboks", headers=as_(BERG)).json() if m["nivå"] == "mistenkelig")
    sim.post(f"/api/post/{phish['id']}/rapporter", headers=as_(BERG))
    assert sim.get(f"/api/post/{phish['id']}", headers=as_(BERG)).json()["rapportert"]


def test_clinician_app_sends_and_previews(tmp_path, monkeypatch):
    sim = TestClient(create_app(tmp_path / "sim.json"))
    monkeypatch.setattr(medicus_app, "helsenett", lambda: SimulatedClient("http://sim", http=sim))
    monkeypatch.setattr(medicus_app, "audit", medicus_app.AuditLog(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("MEDICUS_DEV_IDENTITY", json.dumps({**BERG, "modus": "normal"}))
    app = TestClient(medicus_app.app, base_url="http://127.0.0.1:8000")
    dcm = bilder.synthetic_dicom("Ola Nordmann", seed.OLA, "MR", "MR kne", "KNEE")
    reply = app.post("/api/post", data={"til": [f"hpr:{MOE['hpr']}"], "emne": "MR kne", "tekst": "Vurdering?",
                                        "fnr": seed.OLA}, files=[("filer", ("kne.dcm", dcm, "application/dicom"))])
    assert reply.status_code == 200
    sent = app.get("/api/post/sendt").json()
    msg = app.get(f"/api/post/{sent[0]['id']}").json()
    preview = app.get(f"/api/post/vedlegg/{msg['vedlegg'][0]['id']}?visning=true")
    assert preview.content.startswith(b"\x89PNG")
    download = app.get(f"/api/post/vedlegg/{msg['vedlegg'][0]['id']}")
    assert download.content == dcm


def test_emergency_session_has_no_mail(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDICUS_DEV_IDENTITY", json.dumps({**LIE, "modus": "nød"}))
    assert TestClient(medicus_app.app, base_url="http://127.0.0.1:8000").get("/api/post/innboks").status_code == 403
