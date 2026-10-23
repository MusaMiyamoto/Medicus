import json

import pytest

from medicus.audit import AuditLog
from tilgang import EMERGENCY_USER
from tilgang.authd import Authority
from tilgang.cards import SimulatedReader, build_cards_file

ROOT, MEDICUS_SERVICE, STRANGER = 0, 990, 4242

DEMO = [
    {"card_id": "lege", "navn": "Ingrid Berg", "rolle": "Lege", "virksomhet": "Legesenter",
     "hpr": "999000101", "username": "ingrid-berg", "demo_pin": "1234"},
    {"card_id": "spl", "navn": "Jonas Lie", "rolle": "Sykepleier", "virksomhet": "Legevakt",
     "hpr": "999000202", "username": "jonas-lie", "demo_pin": "2345"},
]


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def setup(tmp_path):
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(DEMO))
    cards = tmp_path / "simkort.json"
    build_cards_file(demo, cards)
    clock = Clock()
    audit = AuditLog(tmp_path / "audit.jsonl")
    authority = Authority(SimulatedReader(cards, tmp_path / "tries.json"), audit, {MEDICUS_SERVICE}, clock=clock)
    return authority, clock, audit, cards


def ask(authority, uid=STRANGER, **request):
    return authority.handle(request, uid)


def test_hashed_card_file_has_no_plain_pins(setup):
    *_, cards = setup
    text = cards.read_text()
    assert "1234" not in text and "demo_pin" not in text


def test_status_without_card(setup):
    authority, *_ = setup
    assert ask(authority, cmd="status") == {"ok": True, "kort": None, "okt": None, "simulert": True}


def test_normal_login_with_card_and_pin(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    assert ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")["ok"]
    session = ask(authority, cmd="status")["okt"]
    assert session["navn"] == "Ingrid Berg" and session["modus"] == "normal"


def test_only_root_can_log_in(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    reply = ask(authority, STRANGER, cmd="login", username="ingrid-berg", pin="1234")
    assert not reply["ok"]
    assert ask(authority, cmd="status")["okt"] is None


def test_login_needs_the_matching_card(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    assert not ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")["ok"]


def test_three_wrong_pins_block_the_card(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    replies = [ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="0000") for _ in range(3)]
    assert "2 forsøk igjen" in replies[0]["error"]
    assert "sperret" in replies[2]["error"]
    assert not ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")["ok"]
    assert not ask(authority, ROOT, cmd="emergency", reason="Bevisstløs pasient")["ok"]


def test_removing_card_ends_normal_session(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"] is None


def test_emergency_requires_card_and_reason(setup):
    authority, *_ = setup
    assert "kort" in ask(authority, ROOT, cmd="emergency", reason="Hjertestans")["error"]
    ask(authority, cmd="insert", card_id="spl")
    assert not ask(authority, ROOT, cmd="emergency", reason="")["ok"]
    assert ask(authority, ROOT, cmd="emergency", reason="Hjertestans")["ok"]
    session = ask(authority, cmd="status")["okt"]
    assert session["modus"] == "nød"
    assert session["navn"] == "Jonas Lie"
    assert session["linux_bruker"] == EMERGENCY_USER
    assert session["sekunder_igjen"] == 30 * 60


def test_emergency_survives_card_removal_but_expires(setup):
    authority, clock, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", reason="Hjertestans")
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"]["modus"] == "nød"
    clock.now += 30 * 60 + 1
    assert ask(authority, cmd="status")["okt"] is None


def test_who_may_end_a_session(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", reason="Hjertestans")
    assert not ask(authority, STRANGER, cmd="end")["ok"]
    assert ask(authority, MEDICUS_SERVICE, cmd="end")["ok"]
    assert ask(authority, cmd="status")["okt"] is None


def test_everything_is_audited_with_identity(setup):
    authority, _clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", reason="Bevisstløs pasient")
    entries = [json.loads(line) for line in audit.path.read_text().splitlines()]
    emergency = [e for e in entries if e["action"] == "emergency_start"][0]
    assert emergency["user"] == "999000202"
    assert emergency["details"]["reason"] == "Bevisstløs pasient"
    assert audit.verify() == (True, None)


def test_guard_terminates_desktops_without_matching_login():
    from tilgang.sessionguard import decide

    users = {"ingrid-berg", "jonas-lie", EMERGENCY_USER}
    sessions = [{"session": "3", "user": "ingrid-berg"}, {"session": "1", "user": "lightdm"}]
    assert decide(None, sessions, users) == (["3"], False)
    login = {"linux_bruker": "ingrid-berg"}
    assert decide(login, sessions, users) == ([], True)
    other = {"linux_bruker": "jonas-lie"}
    assert decide(other, sessions, users) == (["3"], False)
    emergency = {"linux_bruker": EMERGENCY_USER}
    assert decide(emergency, [{"session": "4", "user": EMERGENCY_USER}], users) == ([], True)


def test_unknown_command(setup):
    authority, *_ = setup
    assert not ask(authority, cmd="give_me_root")["ok"]


def test_simulated_reader_can_be_switched_off(setup):
    authority, *_ = setup
    authority.simulated = False
    assert not ask(authority, cmd="insert", card_id="lege")["ok"]
