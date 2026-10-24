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
    assert reply["arbeidssted"] == {**ULLEVAL.public(), "bekreftet": "ubekreftet"}  # no machine certificate


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


def test_removing_card_holds_the_session_for_15_minutes_then_ends_it(setup):
    authority, clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="lege")
    ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    ask(authority, cmd="remove")
    assert ask(authority, cmd="status")["okt"]["holdt_sekunder_igjen"] == 15 * 60
    clock.now += 15 * 60 + 1
    assert ask(authority, cmd="status")["okt"] is None
    assert "card_not_returned" in audit.path.read_text()


def test_same_card_and_pin_resume_the_held_session(setup, monkeypatch):
    import tilgang.authd
    authority, clock, audit, _ = setup
    INGRID = 1001
    monkeypatch.setattr(tilgang.authd, "_uid_of", lambda name: INGRID if name == "ingrid-berg" else None)
    started = login(authority)["startet"]
    ask(authority, cmd="remove")
    ask(authority, cmd="remove")  # taking it out "again" does not restart the 15 minutes
    clock.now += 10 * 60
    assert not ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]  # card still out
    ask(authority, cmd="insert", card_id="lege")
    assert not ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="0000")["ok"]
    assert "holdt_sekunder_igjen" in ask(authority, cmd="status")["okt"]
    assert ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]
    session = ask(authority, cmd="status")["okt"]
    assert session["startet"] == started and "holdt_sekunder_igjen" not in session
    clock.now += 60 * 60  # resumed: no longer on the clock
    assert ask(authority, cmd="status")["okt"]["navn"] == "Ingrid Berg"
    assert '"held_seconds": 600' in audit.path.read_text()


def test_another_card_cannot_resume_but_can_take_over_the_pc(setup):
    authority, _clock, audit, _ = setup
    login(authority)
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="spl")
    assert not ask(authority, ROOT, cmd="unlock", username="jonas-lie", pin="2345")["ok"]
    assert ask(authority, ROOT, cmd="login", username="jonas-lie", pin="2345")["ok"]
    assert ask(authority, cmd="status")["okt"]["navn"] == "Jonas Lie"
    assert "other_user_logged_in" in audit.path.read_text()


def test_held_session_resumes_through_the_login_screen_too(setup):
    authority, *_ = setup
    login(authority)
    ask(authority, cmd="remove")
    session = login(authority)
    assert "holdt_sekunder_igjen" not in session


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


def test_guard_locks_a_held_desktop_but_keeps_it():
    from tilgang.sessionguard import decide, to_lock

    sessions = [{"session": "3", "user": "ingrid-berg"}, {"session": "1", "user": "lightdm"}]
    held = {"linux_bruker": "ingrid-berg", "holdt_sekunder_igjen": 600}
    assert decide(held, sessions, {"ingrid-berg"}) == ([], True)
    assert to_lock(held, sessions) == ["3"]
    assert to_lock({"linux_bruker": "ingrid-berg"}, sessions) == [] and to_lock(None, sessions) == []


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
    assert "holdt_sekunder_igjen" in ask(authority, cmd="status")["okt"]  # held and locked, like any card login


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


def test_screen_unlock_only_for_own_session(setup, monkeypatch):
    import tilgang.authd
    authority, _clock, audit, _ = setup
    INGRID = 1001
    monkeypatch.setattr(tilgang.authd, "_uid_of", lambda name: INGRID if name == "ingrid-berg" else None)
    ask(authority, cmd="insert", card_id="lege")
    assert not ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]  # nobody logged in
    ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    assert not ask(authority, STRANGER, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]
    assert not ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="0000")["ok"]
    assert ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]
    assert "unlock_failed" in audit.path.read_text()
    ask(authority, ROOT, cmd="end")
    assert not ask(authority, INGRID, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]  # logged out


def test_it_lifts_a_pin_block_and_it_is_logged(setup):
    authority, _clock, audit, _ = setup
    ask(authority, cmd="insert", card_id="lege")
    for _ in range(3):
        ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="0000")
    assert ask(authority, cmd="status")["kort"]["sperret"]
    assert not ask(authority, STRANGER, cmd="unblock", card_id="lege")["ok"]       # only root (sudo + IT card)
    assert not ask(authority, ROOT, cmd="unblock", card_id="spl", it_bruker="eirik-strand")["ok"]  # not blocked
    assert ask(authority, ROOT, cmd="unblock", card_id="lege", it_bruker="eirik-strand")["ok"]
    assert not ask(authority, cmd="status")["kort"]["sperret"]
    assert ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")["ok"]
    unblocked = [json.loads(line) for line in audit.path.read_text().splitlines() if "card_unblocked" in line]
    assert unblocked[0]["user"] == "eirik-strand" and unblocked[0]["details"] == {"card": "lege"}


def tap_site(authority, minutes):
    authority.site = Arbeidssted(ULLEVAL.id, ULLEVAL.navn, (), minutes)


def test_tap_in_resumes_a_held_session_without_pin_within_the_limit(setup):
    authority, clock, audit, _ = setup
    tap_site(authority, 240)
    login(authority)
    ask(authority, cmd="remove")
    assert not ask(authority, ROOT, cmd="tap")["ok"]  # card still out
    clock.now += 5 * 60
    ask(authority, cmd="insert", card_id="lege")
    assert ask(authority, ROOT, cmd="tap")["ok"]
    assert "holdt_sekunder_igjen" not in ask(authority, cmd="status")["okt"]
    assert '"uten_pin": true' in audit.path.read_text()
    assert not ask(authority, ROOT, cmd="tap")["ok"]  # nothing held any more


def test_tap_in_is_off_by_default_and_never_for_it_mode(setup):
    authority, *_ = setup
    login(authority)
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="lege")
    reply = ask(authority, ROOT, cmd="tap")
    assert not reply["ok"] and "PIN" in reply["error"]
    tap_site(authority, 240)
    login(authority, "it", "eirik-strand", "4401")  # the IT card takes over the PC
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="it")
    assert not ask(authority, ROOT, cmd="tap")["ok"]


def test_tap_in_needs_the_pin_again_after_the_limit_and_the_pin_restarts_it(setup, monkeypatch):
    import tilgang.authd
    authority, clock, *_ = setup
    monkeypatch.setattr(tilgang.authd, "_uid_of", lambda name: 1001 if name == "ingrid-berg" else None)
    tap_site(authority, 60)
    login(authority)
    clock.now += 50 * 60
    ask(authority, cmd="remove")
    clock.now += 11 * 60  # 61 minutes since the PIN
    ask(authority, cmd="insert", card_id="lege")
    assert not ask(authority, ROOT, cmd="tap")["ok"]
    assert ask(authority, 1001, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]  # PIN: clock restarts
    clock.now += 30 * 60
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="lege")
    assert ask(authority, 1001, cmd="tap")["ok"]  # the lock screen (own user) may ask too
    assert not ask(authority, STRANGER, cmd="tap")["ok"]


def test_tap_in_only_with_the_same_card_and_not_off_the_clinical_network(setup):
    authority, *_ = setup
    tap_site(authority, 240)
    login(authority)
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="spl")
    assert not ask(authority, ROOT, cmd="tap")["ok"]
    ask(authority, cmd="remove")
    authority.site = Arbeidssted(ULLEVAL.id, ULLEVAL.navn, ("10.20.0.0/16",), 240)
    from tilgang.nett import Network
    authority.network = lambda: Network(("192.168.1.20",), certified=False)  # carried home
    ask(authority, cmd="insert", card_id="lege")
    reply = ask(authority, ROOT, cmd="tap")
    assert not reply["ok"] and "kliniske nett" in reply["error"]


def test_tap_in_limit_from_the_workplace_file(tmp_path):
    f = tmp_path / "a.toml"
    for value, expected in (("240", 240), ("0", 0), ("721", 0), ("-5", 0), ('"240"', 0), ("true", 0), ("2.5", 0)):
        f.write_text(f'id = "x"\nnavn = "X"\nkort_uten_pin_minutter = {value}\n')
        assert load(f).kort_uten_pin_minutter == expected, value
    f.write_text('id = "x"\nnavn = "X"\n')
    assert load(f).kort_uten_pin_minutter == 0


def test_guard_taps_only_for_the_held_logins_own_card():
    from tilgang.sessionguard import should_tap
    held = {"username": "ingrid-berg", "modus": "normal", "holdt_sekunder_igjen": 500}
    card = {"username": "ingrid-berg", "sperret": False}
    site = {"kort_uten_pin_minutter": 240}
    assert should_tap({"okt": held, "kort": card, "arbeidssted": site})
    assert not should_tap({"okt": held, "kort": card, "arbeidssted": {"kort_uten_pin_minutter": 0}})
    assert not should_tap({"okt": held, "kort": {**card, "username": "jonas-lie"}, "arbeidssted": site})
    assert not should_tap({"okt": held, "kort": {**card, "sperret": True}, "arbeidssted": site})
    assert not should_tap({"okt": {**held, "modus": "it"}, "kort": card, "arbeidssted": site})
    not_held = {k: v for k, v in held.items() if k != "holdt_sekunder_igjen"}
    assert not should_tap({"okt": not_held, "kort": card, "arbeidssted": site})  # card left in: PIN needed
    assert not should_tap({"okt": None, "kort": card, "arbeidssted": site})


# --- The workplace signed into the machine certificate ----------------------------

def make_cert(tmp_path, subject):
    import subprocess
    cert = tmp_path / "maskin.crt"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                    "-keyout", str(tmp_path / "k.pem"), "-out", str(cert), "-days", "1", "-subj", subject],
                   check=True, capture_output=True)
    return cert


def test_workplace_is_read_from_the_certificate(tmp_path):
    from tilgang.arbeidssted import certificate_site
    assert certificate_site(tmp_path / "finnes-ikke.crt") is None
    assert certificate_site(make_cert(tmp_path, "/CN=pc-0042/OU=ous-ulleval/O=Oslo universitetssykehus")) == "ous-ulleval"
    (tmp_path / "sub").mkdir()
    assert certificate_site(make_cert(tmp_path / "sub", "/CN=pc-0042")) is None  # an older certificate: no OU
    broken = tmp_path / "broken.crt"
    broken.write_text("not a certificate")
    assert certificate_site(broken) == ""  # unreadable counts as not matching


def test_certificate_is_read_once_until_it_changes(tmp_path):
    from types import SimpleNamespace

    from tilgang.arbeidssted import certificate_site
    cert = tmp_path / "c.crt"
    cert.write_text("x")
    calls = []

    def run(cmd, **_):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="subject=CN=pc,OU=stolav\n")
    assert certificate_site(cert, run) == certificate_site(cert, run) == "stolav"
    assert len(calls) == 1
    cert.write_text("changed")
    certificate_site(cert, run)
    assert len(calls) == 2


def test_a_workplace_that_does_not_match_the_certificate_closes_records_but_not_emergency(setup, monkeypatch):
    import tilgang.authd
    authority, _clock, audit, _ = setup
    monkeypatch.setattr(tilgang.authd, "_uid_of", lambda name: 1001)
    authority.signed_site = lambda: "stolav"  # the file says Ullevål, the CA signed St. Olavs
    assert ask(authority, cmd="status")["arbeidssted"]["bekreftet"] == "feil"
    ask(authority, cmd="insert", card_id="lege")
    reply = ask(authority, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    assert not reply["ok"] and "maskinsertifikatet" in reply["error"]
    assert "login_refused_site" in audit.path.read_text()
    assert ask(authority, ROOT, cmd="emergency", situasjon="Hjertestans")["ok"]
    authority.session = None
    ask(authority, cmd="remove")
    login(authority, "it", "eirik-strand", "4401")  # IT can still log in to fix it
    authority.signed_site = lambda: "ous-ulleval"
    assert ask(authority, cmd="status")["arbeidssted"]["bekreftet"] == "bekreftet"
    ask(authority, cmd="remove")
    login(authority)
    authority.signed_site = lambda: ""  # the certificate became unreadable while logged in
    ask(authority, cmd="remove")
    ask(authority, cmd="insert", card_id="lege")
    assert not ask(authority, 1001, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]
