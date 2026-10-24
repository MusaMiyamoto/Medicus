import httpx
import pytest
from fastapi.testclient import TestClient

from helsenett import fnr
from helsenett.client import HelsenettError, IkkeTilkoblet, NhnClient, SimulatedClient, get_client
from helsenett.sim import seed
from helsenett.sim.app import create_app

BERG = seed.BERG
LIE = seed.LIE


@pytest.fixture
def sim(tmp_path):
    return TestClient(create_app(tmp_path / "state.json"))


def test_seed_numbers_are_valid_synthetic():
    for number in (seed.OLA, seed.KARI, seed.SOFIE, seed.ERIK):
        assert fnr.is_valid(number)
        assert fnr.is_synthetic(number)


@pytest.mark.parametrize("bad", ["", "123", "1234567890a", "12038012345"])
def test_invalid_numbers(bad):
    assert not fnr.is_valid(bad)


def test_mask_hides_personal_number():
    assert fnr.mask("12838012345") == "128380 *****"


def test_critical_info_contains_only_critical_parts(sim):
    data = sim.get(f"/api/kjernejournal/{seed.OLA}").json()
    assert set(data) == {"pasient", "allergier", "tilstander", "implantater", "legemidler", "parorende"}
    assert data["allergier"][0]["stoff"] == "Penicillin"
    assert "kontakter" not in data


def test_unknown_patient_is_404(sim):
    assert sim.get(f"/api/kjernejournal/{fnr.make_synthetic(1, 1, 99, 1)}").status_code == 404


def test_access_is_visible_to_patient(sim):
    sim.post(f"/api/innsyn/{seed.SOFIE}", json={"aktor": LIE, "modus": "nød", "begrunnelse": "Bevisstløs pasient", "hva": "Kritisk informasjon"})
    events = sim.get(f"/api/innsyn/{seed.SOFIE}").json()
    assert events[0]["modus"] == "nød"
    assert events[0]["aktor"]["navn"] == "Jonas Lie"


def test_only_doctors_can_prescribe(sim):
    body = {"legemiddel": "Paracet", "dosering": "1 g x 4", "indikasjon": "Smerter"}
    assert sim.post(f"/api/resepter/{seed.OLA}", json={"aktor": LIE, **body}).status_code == 403
    assert sim.post(f"/api/resepter/{seed.OLA}", json={"aktor": BERG, **body}).status_code == 200
    assert sim.get(f"/api/resepter/{seed.OLA}").json()[0]["legemiddel"] == "Paracet"


def test_shared_note_reaches_gp_view(sim):
    sim.post(f"/api/journal/{seed.ERIK}", json={"aktor": LIE, "type": "Legevakt", "notat": "Falt hjemme, ingen brudd."})
    notes = sim.get(f"/api/journal/{seed.ERIK}").json()
    assert notes[0]["notat"] == "Falt hjemme, ingen brudd."
    assert notes[0]["virksomhet"] == LIE["virksomhet"]


def request_body(**overrides):
    return {
        "myndighetstype": "Politiet / påtalemyndigheten",
        "myndighet": "Politiet, Testby", "saksbehandler": "Etterforsker Test", "fnr": seed.KARI,
        "hjemmel": "Pasientens samtykke (helsepersonelloven § 22)", "formal": "Etterforskning av sak 123, samtykke vedlagt.",
        "data": ["Kontakter og notater"], "periode": "2026-08", **overrides,
    }


def test_disclosure_needs_listed_legal_basis(sim):
    assert sim.post("/api/utlevering", json=request_body(hjemmel="Fordi vi vil")).status_code == 422


def test_legal_basis_must_fit_the_authority(sim):
    # The tax office cannot use the child-welfare provision; only consent or an explicit law.
    body = request_body(myndighetstype="Annen myndighet eller virksomhet", myndighet="Skatteetaten",
                        hjemmel="Pålegg fra barnevernstjenesten (helsepersonelloven § 33, barnevernsloven § 13-2)")
    assert sim.post("/api/utlevering", json=body).status_code == 422
    assert sim.post("/api/utlevering", json=request_body(myndighetstype="Hemmelig tjeneste")).status_code == 422


def test_child_welfare_can_request_with_its_own_basis(sim):
    body = request_body(myndighetstype="Barnevernstjenesten", myndighet="Barnevernstjenesten i Testby",
                        hjemmel="Pålegg fra barnevernstjenesten (helsepersonelloven § 33, barnevernsloven § 13-2)")
    assert sim.post("/api/utlevering", json=body).status_code == 200


def test_every_authority_has_a_basis_and_police_cannot_just_demand():
    from helsenett import hjemler
    assert all(a["hjemler"] for a in hjemler.AUTHORITIES)
    police = hjemler.BY_TYPE["Politiet / påtalemyndigheten"]["hjemler"]
    assert not any("kjennelse" in h.lower() for h in police)


def test_approved_disclosure_releases_minimum_and_notifies(sim):
    r = sim.post("/api/utlevering", json=request_body()).json()
    decided = sim.post(f"/api/utlevering/{r['id']}/vedtak", json={
        "beslutning": "godkjent", "begrunnelse": "Gyldig kjennelse, begrenset til august.", "behandlet_av": "Avdelingsleder Test",
    }).json()
    assert decided["status"] == "Godkjent"
    assert set(decided["utlevert"]) == {"Kontakter og notater"}
    assert all(k["tid"].startswith("2026-08") for k in decided["utlevert"]["Kontakter og notater"])
    assert sim.get(f"/api/utleveringer/{seed.KARI}").json()[0]["mottaker"] == "Politiet, Testby"


def test_rejected_disclosure_releases_nothing(sim):
    r = sim.post("/api/utlevering", json=request_body()).json()
    decided = sim.post(f"/api/utlevering/{r['id']}/vedtak", json={
        "beslutning": "avslått", "begrunnelse": "Mangler gyldig hjemmel.", "behandlet_av": "Avdelingsleder Test",
    }).json()
    assert decided["status"] == "Avslått"
    assert "utlevert" not in decided
    assert sim.get(f"/api/utleveringer/{seed.KARI}").json() == []


def test_withholding_notice_requires_legal_basis(sim):
    r = sim.post("/api/utlevering", json=request_body()).json()
    response = sim.post(f"/api/utlevering/{r['id']}/vedtak", json={
        "beslutning": "godkjent", "begrunnelse": "Gyldig kjennelse.", "behandlet_av": "Ombud", "varsle_pasient": False,
    })
    assert response.status_code == 422


def test_request_cannot_be_decided_twice(sim):
    r = sim.post("/api/utlevering", json=request_body()).json()
    decision = {"beslutning": "avslått", "begrunnelse": "Mangler hjemmel.", "behandlet_av": "Ombud"}
    assert sim.post(f"/api/utlevering/{r['id']}/vedtak", json=decision).status_code == 200
    assert sim.post(f"/api/utlevering/{r['id']}/vedtak", json=decision).status_code == 409


def test_state_survives_restart(tmp_path):
    path = tmp_path / "state.json"
    TestClient(create_app(path)).post(f"/api/journal/{seed.OLA}", json={"aktor": BERG, "type": "Notat", "notat": "Husk meg"})
    assert TestClient(create_app(path)).get(f"/api/journal/{seed.OLA}").json()[0]["notat"] == "Husk meg"


def test_simulated_client_talks_to_simulator(sim):
    client = SimulatedClient("http://sim", http=sim)
    assert client.critical_info(seed.KARI)["implantater"][0]["navn"] == "Pacemaker"
    client.log_access(seed.KARI, BERG, "normal", "Behandling", "Journal")
    assert client.http.get(f"/api/innsyn/{seed.KARI}").json()[0]["hva"] == "Journal"
    with pytest.raises(HelsenettError):
        client.find_patient(fnr.make_synthetic(1, 1, 99, 1))


def test_simulated_client_reports_unreachable_network():
    def refuse(request):
        raise httpx.ConnectError("refused")

    client = SimulatedClient("http://sim", http=httpx.Client(base_url="http://sim", transport=httpx.MockTransport(refuse)))
    with pytest.raises(HelsenettError, match="kontakt"):
        client.list_patients()


def test_nhn_mode_explains_what_is_missing():
    client = get_client({"modus": "nhn", "nhn": {}})
    assert isinstance(client, NhnClient)
    with pytest.raises(IkkeTilkoblet, match="Kjernejournal"):
        client.critical_info(seed.OLA)


def test_unknown_mode_is_rejected():
    with pytest.raises(HelsenettError):
        get_client({"modus": "internett"})


def test_the_simulator_service_only_answers_this_machine(tmp_path, monkeypatch):
    from helsenett.sim.app import make_app
    monkeypatch.setenv("MEDICUS_SIM_STATE", str(tmp_path / "state.json"))
    app = make_app()
    assert TestClient(app, base_url="http://127.0.0.1:8100").get("/api/pasienter").status_code == 200
    assert TestClient(app, base_url="http://evil.example:8100").get("/api/pasienter").status_code == 400
