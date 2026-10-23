import json

import pytest

from medicus.audit import AuditLog
from tilgang import EMERGENCY_USER, REPORT_HOURS
from tilgang.arbeidssted import Arbeidssted, load
from tilgang.authd import Authority
from tilgang.cards import SimulatedReader, build_cards_file

ROOT, MEDICUS_SERVICE, STRANGER = 0, 990, 4242

ULLEVAL = Arbeidssted("ous-ulleval", "Oslo universitetssykehus, Ullevål")
STOLAV = Arbeidssted("stolav", "St. Olavs hospital, Trondheim")
AKER = Arbeidssted("ous-aker", "Oslo universitetssykehus, Aker")

DEMO = [
    {"card_id": "lege", "navn": "Ingrid Berg", "rolle": "Lege", "hpr": "999000101", "username": "ingrid-berg",
     "demo_pin": "1234", "stillinger": {"ous-ulleval": "Overlege, kardiologi", "stolav": "Gjesteoverlege"}},
    {"card_id": "spl", "navn": "Jonas Lie", "rolle": "Sykepleier", "hpr": "999000202", "username": "jonas-lie",
     "demo_pin": "2345"},
    {"card_id": "it", "navn": "Eirik Strand", "rolle": "IT", "hpr": "IT-4401", "username": "eirik-strand",
     "demo_pin": "4401"},
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
    authority = Authority(SimulatedReader(cards, tmp_path / "tries.json"), audit, {MEDICUS_SERVICE}, clock=clock,
                          site=ULLEVAL, sim_sites=[ULLEVAL, STOLAV, AKER])
    return authority, clock, audit, cards


def ask(authority, uid=STRANGER, **request):
    return authority.handle(request, uid)


def test_hashed_card_file_has_no_plain_pins(setup):
    *_, cards = setup
    text = cards.read_text()
    assert "1234" not in text and "demo_pin" not in text


def test_status_without_card(setup):
    authority, *_ = setup
    reply = ask(authority, cmd="status")
    assert (reply["kort"], reply["okt"], reply["simulert"]) == (None, None, True)
    assert reply["arbeidssted"] == ULLEVAL.public()


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
    assert ask(authority, cmd="status")["kort"]["sperret"]
    right_pin = ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    assert not right_pin["ok"]
    assert "sperret" in right_pin["error"] and "Feil PIN" not in right_pin["error"]
    assert not ask(authority, ROOT, cmd="emergency", situasjon="Bevisstløs pasient")["ok"]


def test_removing_card_ends_normal_session(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"] is None


def test_emergency_needs_only_the_card(setup):
    authority, *_ = setup
    assert "kort" in ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")["error"]
    ask(authority, cmd="insert", card_id="spl")
    assert ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")["ok"]
    session = ask(authority, cmd="status")["okt"]
    assert session["modus"] == "nød" and session["situasjon"] == "Hjertestans"
    assert session["navn"] == "Jonas Lie"
    assert session["linux_bruker"] == EMERGENCY_USER
    assert session["sekunder_igjen"] == 30 * 60


def test_emergency_survives_card_removal_but_expires(setup):
    authority, clock, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"]["modus"] == "nød"
    clock.now += 30 * 60 + 1
    assert ask(authority, cmd="status")["okt"] is None


def test_who_may_end_a_session(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")
    assert not ask(authority, STRANGER, cmd="end")["ok"]
    assert ask(authority, MEDICUS_SERVICE, cmd="end")["ok"]
    assert ask(authority, cmd="status")["okt"] is None


def test_everything_is_audited_with_identity(setup):
    authority, _clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Bevisstløs pasient")
    entries = [json.loads(line) for line in audit.path.read_text().splitlines()]
    emergency = [e for e in entries if e["action"] == "emergency_start"][0]
    assert emergency["user"] == "999000202"
    assert emergency["details"]["situasjon"] == "Bevisstløs pasient"
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


def test_guard_reads_loginctl_json_and_refuses_to_guess():
    from types import SimpleNamespace

    from tilgang.sessionguard import desktop_sessions

    seen = {}

    def fake_run(cmd, **_kw):
        seen["cmd"] = cmd
        return SimpleNamespace(stdout='[{"session":"3","user":"ingrid-berg"}]')

    assert desktop_sessions(fake_run) == [{"session": "3", "user": "ingrid-berg"}]
    assert "--json=short" in seen["cmd"]
    # systemd ignores some flags and prints a table instead: that must not count as "no sessions".
    table = lambda cmd, **_kw: SimpleNamespace(stdout="SESSION UID USER\n 3 1001 ingrid-berg\n")  # noqa: E731
    assert desktop_sessions(table) is None


def login(authority, card_id="lege", username="ingrid-berg", pin="1234"):
    ask(authority, cmd="insert", card_id=card_id)
    assert ask(authority, ROOT, cmd="login", username=username, pin=pin)["ok"]
    return ask(authority, cmd="status")["okt"]


def test_workplace_comes_from_the_pc_and_position_from_that_workplace(setup):
    authority, *_ = setup
    session = login(authority)
    assert session["virksomhet"] == "Oslo universitetssykehus, Ullevål"
    assert session["stilling"] == "Overlege, kardiologi"


def test_same_card_at_another_hospital_shows_that_hospital(setup):
    authority, *_ = setup
    assert ask(authority, cmd="set_site", site_id="stolav")["ok"]
    session = login(authority)
    assert session["virksomhet"] == "St. Olavs hospital, Trondheim"
    assert session["stilling"] == "Gjesteoverlege"


def test_no_position_at_a_workplace_falls_back_to_authorization(setup):
    authority, *_ = setup
    ask(authority, cmd="set_site", site_id="ous-aker")
    assert login(authority)["stilling"] == "Lege"


def test_card_status_shows_position_before_login(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="lege")
    reply = ask(authority, cmd="status")
    assert reply["kort"]["stilling"] == "Overlege, kardiologi"
    assert reply["arbeidssted"]["navn"] == "Oslo universitetssykehus, Ullevål"


def test_workplace_cannot_change_during_a_session(setup):
    authority, *_ = setup
    login(authority)
    assert not ask(authority, cmd="set_site", site_id="stolav")["ok"]


def test_workplace_switching_is_demo_only(setup):
    authority, *_ = setup
    authority.simulated = False
    assert not ask(authority, cmd="set_site", site_id="stolav")["ok"]


def test_workplace_config_file(tmp_path):
    path = tmp_path / "arbeidssted.toml"
    path.write_text('id = "stolav"\nnavn = "St. Olavs hospital, Trondheim"\n', encoding="utf-8")
    assert load(path) == STOLAV
    assert load(tmp_path / "missing.toml").id == "ukjent"


def test_unknown_command(setup):
    authority, *_ = setup
    assert not ask(authority, cmd="give_me_root")["ok"]


def test_simulated_reader_can_be_switched_off(setup):
    authority, *_ = setup
    authority.simulated = False
    assert not ask(authority, cmd="insert", card_id="lege")["ok"]


# --- Emergency reports ---------------------------------------------------------------

def test_unknown_situation_is_recorded_as_not_given(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="<script>")
    assert ask(authority, cmd="status")["okt"]["situasjon"] == "Ikke oppgitt"


def test_emergency_access_leaves_a_report_to_write(setup):
    authority, _clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")
    ask(authority, MEDICUS_SERVICE, cmd="end")
    # Next time the card goes in, the login screen knows a report is owed ...
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="spl")
    owed = ask(authority, cmd="status")["kort"]["rapporter"]
    assert len(owed) == 1 and owed[0]["situasjon"] == "Hjertestans" and not owed[0]["forsinket"]
    # ... and after a normal login the person writes it.
    ask(authority, ROOT, cmd="login", username="jonas-lie", pin="2345")
    report_id = ask(authority, cmd="status")["okt"]["rapporter"][0]["id"]
    assert "mer" in ask(authority, MEDICUS_SERVICE, cmd="report", id=report_id, tekst="ok")["error"]
    text = "Pasient funnet bevisstløs på gangen. Trengte allergier før behandling."
    assert ask(authority, MEDICUS_SERVICE, cmd="report", id=report_id, tekst=text)["ok"]
    assert ask(authority, cmd="status")["okt"]["rapporter"] == []
    written = [json.loads(line) for line in audit.path.read_text().splitlines() if "report_written" in line]
    assert written[0]["details"]["tekst"] == text


def test_only_the_person_who_opened_it_can_write_the_report(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")
    report_id = ask(authority, cmd="status")["okt"]["rapporter"][0]["id"]
    ask(authority, MEDICUS_SERVICE, cmd="end")
    ask(authority, cmd="remove")
    login(authority)  # Ingrid Berg
    text = "Dette er en lang nok tekst for en rapport."
    assert not ask(authority, MEDICUS_SERVICE, cmd="report", id=report_id, tekst=text)["ok"]
    assert not ask(authority, STRANGER, cmd="report", id=report_id, tekst=text)["ok"]


def test_late_reports_are_flagged_once(setup):
    authority, clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="spl")
    ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")
    assert ask(authority, MEDICUS_SERVICE, cmd="overdue")["rapporter"] == []
    clock.now += REPORT_HOURS * 3600 + 1
    late = ask(authority, MEDICUS_SERVICE, cmd="overdue")["rapporter"]
    assert len(late) == 1 and late[0]["forsinket"]
    ask(authority, cmd="status")
    flagged = [line for line in audit.path.read_text().splitlines() if "emergency_report_overdue" in line]
    assert len(flagged) == 1
    assert not ask(authority, STRANGER, cmd="overdue")["ok"]


def test_reports_survive_a_restart(tmp_path):
    from tilgang.nodrapport import Reports
    clock = Clock()
    Reports(tmp_path / "r.json", clock).open("999000202", "Jonas Lie", "Hjertestans")
    again = Reports(tmp_path / "r.json", clock)
    assert again.missing("999000202")[0]["situasjon"] == "Hjertestans"


# --- IT mode -----------------------------------------------------------------------

def test_it_card_logs_in_to_it_mode(setup):
    authority, *_ = setup
    login(authority, card_id="it", username="eirik-strand", pin="4401")
    assert ask(authority, cmd="status")["okt"]["modus"] == "it"
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"] is None


def test_it_card_cannot_open_emergency_access(setup):
    authority, *_ = setup
    ask(authority, cmd="insert", card_id="it")
    assert not ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")["ok"]


def test_admin_actions_need_the_it_card_and_pin(setup):
    authority, _clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="lege")
    assert not ask(authority, ROOT, cmd="verify", username="ingrid-berg", pin="1234")["ok"]
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="it")
    assert not ask(authority, STRANGER, cmd="verify", username="eirik-strand", pin="4401")["ok"]
    assert not ask(authority, ROOT, cmd="verify", username="eirik-strand", pin="0000")["ok"]
    assert ask(authority, ROOT, cmd="verify", username="eirik-strand", pin="4401")["ok"]
    assert "admin_confirmed" in audit.path.read_text()
