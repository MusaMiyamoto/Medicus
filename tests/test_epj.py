"""Patient picker, DIPS (FHIR) and transfer from Epic."""

import base64
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import medicus.app as medicus_app
from epj import epic, fhir, get_journal
from epj.dips import DipsClient
from helsenett.client import HelsenettError, IkkeTilkoblet
from helsenett.sim import seed
from helsenett.sim.app import create_app
from tests.test_app import DOCTOR, IT, NURSE, env  # noqa: F401  (env is a fixture)

SAMPLE = Path(__file__).parent.parent / "samples" / "epic-eksport-eksempel.json"


def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


# --- Patient picker and saving the approved note --------------------------------

def test_doctor_sees_own_patients(env):
    app, _sim, login = env
    login(DOCTOR)
    data = app.get("/api/journal/pasienter").json()
    assert {p["navn"] for p in data["pasienter"]} == {"Ola Nordmann", "Kari Nordmann", "Sofie Hansen", "Erik Johansen"}
    login(NURSE)  # not anyone's fastlege: only patients she has seen
    assert {p["navn"] for p in app.get("/api/journal/pasienter").json()["pasienter"]} == {"Ola Nordmann", "Sofie Hansen"}


def test_it_mode_gets_no_patient_list(env):
    app, _sim, login = env
    login(IT)
    assert app.get("/api/journal/pasienter").status_code == 403


def test_approved_note_is_saved_in_the_chosen_patients_record(env):
    app, sim, login = env
    login(DOCTOR)
    reply = app.post("/api/approve", json={"note": "Kontroll. Uendret behandling.", "fnr": seed.ERIK}).json()
    assert reply["lagret_i"] == "Helsenett (simulert)"
    newest = sim.get(f"/api/journal/{seed.ERIK}").json()[0]
    assert newest["notat"] == "Kontroll. Uendret behandling." and newest["aktor"]["navn"] == "Ingrid Berg"
    assert app.post("/api/approve", json={"note": "x", "fnr": "12345678901"}).status_code == 422
    assert app.post("/api/approve", json={"note": "Bare godkjent."}).json()["lagret_i"] is None


# --- DIPS over FHIR R4, against the simulator's FHIR server ------------------------

@pytest.fixture
def dips(tmp_path):
    sim = TestClient(create_app(tmp_path / "sim.json"), base_url="http://sim/fhir")
    return DipsClient("http://sim/fhir", lambda: "test-token", http=sim), sim


def test_dips_finds_patient_by_fodselsnummer(dips):
    client, _ = dips
    assert client.find_patient(seed.KARI)["navn"] == "Kari Nordmann"
    with pytest.raises(HelsenettError):
        client.find_patient("04875800000")


def test_dips_lists_todays_patients_for_the_doctor(dips):
    client, _ = dips
    assert len(client.my_patients(seed.BERG)) == 4
    assert client.my_patients(seed.LIE) == []


def test_dips_saves_note_as_document_reference(dips, tmp_path):
    client, sim = dips
    assert client.save_note(seed.OLA, seed.BERG, "Journalnotat", "Blodsukker stabilt.")["system"] == "DIPS Arena"
    newest = TestClient(create_app(tmp_path / "sim.json")).get(f"/api/journal/{seed.OLA}").json()[0]
    assert newest["notat"] == "Blodsukker stabilt." and newest["aktor"]["hpr"] == seed.BERG["hpr"]


def test_document_reference_follows_fhir():
    doc = fhir.document("p1", seed.BERG, "Journalnotat", "Æ ø å")
    assert doc["subject"] == {"reference": "Patient/p1"} and doc["docStatus"] == "final"
    assert doc["author"][0]["identifier"] == {"system": fhir.HPR, "value": seed.BERG["hpr"]}
    assert base64.b64decode(doc["content"][0]["attachment"]["data"]).decode() == "Æ ø å"


def test_dips_without_agreement_says_what_is_missing():
    journal = get_journal({"journal": {"system": "dips"}, "dips": {}})
    with pytest.raises(IkkeTilkoblet, match="avtale"):
        journal.find_patient(seed.OLA)


# --- Epic export -----------------------------------------------------------------

def test_epic_export_is_read():
    t = epic.read_bundle(sample())
    assert t["pasient"]["fnr"] == seed.KARI
    assert [a["stoff"] for a in t["allergier"]] == ["Jodholdig kontrastmiddel", "Lateks"]  # error entry left out
    assert {m["navn"] for m in t["legemidler"]} == {"Warfarin 2,5 mg tablett", "Metoprolol depottablett 50 mg"}
    assert [d["tittel"] for d in t["dokumenter"]] == ["Epikrise kardiologisk avdeling", "Poliklinisk notat"]
    assert len(t["advarsler"]) == 1 and "PDF" in t["advarsler"][0]


@pytest.mark.parametrize("change, message", [
    (lambda b: {"resourceType": "Patient"}, "Bundle"),
    (lambda b: {**b, "entry": [e for e in b["entry"] if e["resource"]["resourceType"] != "Patient"]}, "én pasient"),
    (lambda b: {**b, "entry": b["entry"] + b["entry"][:1]}, "én pasient"),
])
def test_unusable_exports_are_refused(change, message):
    with pytest.raises(epic.TransferError, match=message):
        epic.read_bundle(change(sample()))


def test_export_without_fodselsnummer_is_refused():
    bundle = sample()
    bundle["entry"][0]["resource"]["identifier"] = [{"system": "urn:epic:mrn", "value": "E123"}]
    with pytest.raises(epic.TransferError, match="fødselsnummer"):
        epic.read_bundle(bundle)


def test_allergies_are_marked_for_checking():
    title, text = epic.journal_notes(epic.read_bundle(sample()), seed.BERG, "2026-10-24")[0]
    assert title == "Overført fra Epic: sammendrag" and "må kontrolleres" in text and "Lateks" in text


def test_fetch_from_epic_server_gets_binary_only_from_same_server():
    resources = {r["resourceType"] + "/" + r["id"]: r for r in (e["resource"] for e in sample()["entry"])}
    doc = resources["DocumentReference/d2"]
    stray = {**resources["DocumentReference/d1"], "id": "d9",
             "content": [{"attachment": {"contentType": "text/plain", "url": "https://elsewhere.example/Binary/b1"}}]}
    asked = []

    def handler(request: httpx.Request):
        asked.append(str(request.url))
        assert request.headers["authorization"] == "Bearer t"
        kind = request.url.path.rsplit("/", 1)[-1] if "Binary" not in request.url.path else "Binary"
        if kind == "Binary":
            return httpx.Response(200, content=base64.b64decode(resources["Binary/b1"]["data"]))
        if kind == "Patient":
            return httpx.Response(200, json={"resourceType": "Bundle", "entry": [{"resource": resources["Patient/eK1"]}]})
        found = [doc, stray] if kind == "DocumentReference" else [r for r in resources.values() if r["resourceType"] == kind]
        return httpx.Response(200, json={"resourceType": "Bundle", "entry": [{"resource": r} for r in found]})

    http = httpx.Client(base_url="https://epic.example/fhir", transport=httpx.MockTransport(handler))
    t = epic.read_bundle(epic.EpicSource("https://epic.example/fhir", lambda: "t", http=http).bundle_for(seed.KARI))
    assert [d["tittel"] for d in t["dokumenter"]] == ["Poliklinisk notat"]
    assert not any("elsewhere" in url for url in asked)


# --- Transfer through the web app --------------------------------------------------

def upload(app):
    return app.post("/api/overforing/epic/fil", files={"fil": ("eksport.json", SAMPLE.read_bytes(), "application/json")})


def test_transfer_preview_then_import(env):
    app, sim, login = env
    login(DOCTOR)
    preview = upload(app).json()
    assert preview["her"]["navn"] == "Kari Nordmann" and preview["journalsystem"] == "Helsenett (simulert)"
    before = len(sim.get(f"/api/journal/{seed.KARI}").json())
    reply = app.post("/api/overforing/importer", json={"id": preview["id"], "fnr": seed.KARI}).json()
    assert reply["notater"] == 3
    notes = sim.get(f"/api/journal/{seed.KARI}").json()
    assert len(notes) == before + 3 and any(n["type"] == "Overført fra Epic: Epikrise kardiologisk avdeling" for n in notes)
    assert sim.get(f"/api/innsyn/{seed.KARI}").json()[0]["begrunnelse"] == "Overføring av journal fra Epic"
    # A preview can be used once.
    assert app.post("/api/overforing/importer", json={"id": preview["id"], "fnr": seed.KARI}).status_code == 404


def test_transfer_needs_the_right_patient_and_the_same_person(env):
    app, _sim, login = env
    login(DOCTOR)
    preview_id = upload(app).json()["id"]
    assert app.post("/api/overforing/importer", json={"id": preview_id, "fnr": seed.OLA}).status_code == 422
    login({**seed.DAHL, "modus": "normal"})
    assert app.post("/api/overforing/importer", json={"id": preview_id, "fnr": seed.KARI}).status_code == 404


def test_transfer_refuses_bad_files_and_it_mode(env):
    app, _sim, login = env
    login(DOCTOR)
    bad = app.post("/api/overforing/epic/fil", files={"fil": ("x.json", b"not json", "application/json")})
    assert bad.status_code == 422
    login(IT)
    assert upload(app).status_code == 403


def test_fetch_from_epic_without_agreement_explains(env, monkeypatch):
    app, _sim, login = env
    monkeypatch.setattr(medicus_app.integration, "load", lambda: {"epic": {}})
    login(DOCTOR)
    reply = app.post("/api/overforing/epic/hent", json={"fnr": seed.KARI})
    assert reply.status_code == 502 and "avtale" in reply.json()["detail"]
