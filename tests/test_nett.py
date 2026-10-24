"""Clinical network binding: normal logins only on the site's VLANs, through the TPM certificate."""

import json
from types import SimpleNamespace

import pytest

from medicus.audit import AuditLog
from tilgang import nett
from tilgang.arbeidssted import NO_NETWORK, Arbeidssted, load
from tilgang.authd import Authority
from tilgang.cards import SimulatedReader, build_cards_file
from tilgang.nett import Network

ROOT = 0
WARD = ("10.20.0.0/16", "2001:db8:20::/48")
ON_WARD = Network(("10.20.4.17",), certified=True)

DEMO = [
    {"card_id": "lege", "navn": "Ingrid Berg", "rolle": "Lege", "hpr": "999000101", "username": "ingrid-berg",
     "demo_pin": "1234"},
    {"card_id": "spl", "navn": "Jonas Lie", "rolle": "Sykepleier", "hpr": "999000202", "username": "jonas-lie",
     "demo_pin": "2345"},
    {"card_id": "it", "navn": "Eirik Strand", "rolle": "IT", "hpr": "IT-4401", "username": "eirik-strand",
     "demo_pin": "4401"},
]


@pytest.mark.parametrize("network, ok", [
    (ON_WARD, True),
    (Network(("10.20.4.17",), certified=False), False),        # right subnet, but not through the certificate
    (Network(("192.168.1.20",), certified=True), False),      # certificate, but a different network
    (Network(("2001:db8:20::5",), certified=True), True),
    (Network(("::ffff:10.20.4.17",), certified=True), False),  # mapped IPv6 is not the IPv4 VLAN
    (Network((), certified=True), False),
])
def test_on_clinical_network(network, ok):
    assert nett.on_clinical_network(network, WARD) is ok


def test_no_subnets_configured_means_no_check():
    assert nett.on_clinical_network(Network(), ())


def test_reads_ip_and_networkmanager():
    def run(cmd, **_):
        if cmd[0] == "ip":
            out = json.dumps([{"ifname": "eth0", "addr_info": [{"local": "10.20.4.17"}, {"family": "inet6"}]}])
        else:
            out = "Medicus\\: kablet nett\nlo\n"
        return SimpleNamespace(stdout=out)
    assert nett.read(run) == Network(("10.20.4.17",), True)
    assert nett.read(lambda *a, **k: SimpleNamespace(stdout="not json")) == Network((), False)


def test_site_file_with_subnets(tmp_path):
    path = tmp_path / "arbeidssted.toml"
    path.write_text('id = "ous"\nnavn = "OUS"\nnett = ["10.20.0.0/16"]\n', encoding="utf-8")
    assert load(path).nett == ("10.20.0.0/16",)
    path.write_text('id = "ous"\nnavn = "OUS"\n', encoding="utf-8")
    assert load(path).nett == ()


@pytest.mark.parametrize("value", ['["10.20.0.1/16"]', '["kontor"]', '"10.20.0.0/16"', "[]"])
def test_a_broken_subnet_list_closes_instead_of_opening(tmp_path, value):
    path = tmp_path / "arbeidssted.toml"
    path.write_text(f'id = "ous"\nnavn = "OUS"\nnett = {value}\n', encoding="utf-8")
    assert load(path).nett == NO_NETWORK
    assert not nett.on_clinical_network(ON_WARD, NO_NETWORK)


@pytest.fixture
def make(tmp_path):
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(DEMO))
    build_cards_file(demo, tmp_path / "kort.json")
    audit = AuditLog(tmp_path / "audit.jsonl")
    where = {"net": ON_WARD}

    def authority():
        return Authority(SimulatedReader(tmp_path / "kort.json", tmp_path / "tries.json"), audit, set(),
                         site=Arbeidssted("ous", "OUS", WARD), network=lambda: where["net"])
    return authority, where, audit


def ask(authority, uid=4242, **request):
    return authority.handle(request, uid)


def test_normal_login_only_on_the_clinical_network(make):
    authority, where, audit = make
    a = authority()
    ask(a, cmd="insert", card_id="lege")
    where["net"] = Network(("192.168.1.20",), certified=False)
    reply = ask(a, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    assert not reply["ok"] and "kliniske nett" in reply["error"]
    assert ask(a, cmd="status")["okt"] is None
    assert "login_refused_network" in audit.path.read_text()
    where["net"] = ON_WARD
    assert ask(a, ROOT, cmd="login", username="ingrid-berg", pin="1234")["ok"]


def test_a_laptop_carried_away_stays_locked(make, monkeypatch):
    import tilgang.authd
    monkeypatch.setattr(tilgang.authd, "_uid_of", lambda name: 1001)
    authority, where, _ = make
    a = authority()
    ask(a, cmd="insert", card_id="lege")
    ask(a, ROOT, cmd="login", username="ingrid-berg", pin="1234")
    where["net"] = Network(("192.168.1.20",), certified=False)
    assert not ask(a, 1001, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]
    where["net"] = ON_WARD
    assert ask(a, 1001, cmd="unlock", username="ingrid-berg", pin="1234")["ok"]


def test_emergency_and_it_still_work_but_are_marked(make):
    authority, where, audit = make
    where["net"] = Network()
    a = authority()
    ask(a, cmd="insert", card_id="spl")
    assert ask(a, ROOT, cmd="emergency", situasjon="Hjertestans")["ok"]
    ask(a, ROOT, cmd="end")
    ask(a, cmd="remove")
    ask(a, cmd="insert", card_id="it")
    assert ask(a, ROOT, cmd="login", username="eirik-strand", pin="4401")["ok"]
    marked = [json.loads(line) for line in audit.path.read_text().splitlines() if "utenfor_klinisk_nett" in line]
    assert [e["action"] for e in marked] == ["emergency_start", "login"]


# --- Mobile PCs: the VPN counts instead of the ward's 802.1X ---------------------

VPN_RANGE = ("10.99.0.0/16",)
IN_CAR = Network(("100.64.3.9", "10.99.0.42"), certified=False, vpn=True)  # 4G address + tunnel address


def test_mobile_pc_counts_the_vpn_but_a_fixed_pc_never_does():
    assert nett.on_clinical_network(IN_CAR, VPN_RANGE, mobile=True)
    assert not nett.on_clinical_network(IN_CAR, VPN_RANGE, mobile=False)
    no_tunnel = Network(("100.64.3.9",), certified=False, vpn=False)
    assert not nett.on_clinical_network(no_tunnel, VPN_RANGE, mobile=True)
    # "VPN up" is not enough on its own: the address must be the hospital's VPN range.
    other_vpn = Network(("100.64.3.9", "10.50.0.2"), certified=False, vpn=True)
    assert not nett.on_clinical_network(other_vpn, VPN_RANGE, mobile=True)


def test_vpn_needs_the_tunnel_up_and_the_kill_switch():
    def machine(link_flags, kill_switch):
        def run(cmd, **_):
            if cmd[:3] == ["ip", "-j", "link"]:
                return SimpleNamespace(stdout=json.dumps([{"ifname": "helsenett", "flags": link_flags}]), returncode=0)
            if cmd[0] == "nft":
                return SimpleNamespace(stdout="", returncode=0 if kill_switch else 1)
            return SimpleNamespace(stdout="", returncode=1)
        return run
    assert nett.vpn_up(machine(["POINTOPOINT", "NOARP", "UP", "LOWER_UP"], True))
    assert not nett.vpn_up(machine(["POINTOPOINT", "NOARP", "UP", "LOWER_UP"], False))  # tunnel, but leaks
    assert not nett.vpn_up(machine(["POINTOPOINT", "NOARP"], True))  # down
    assert not nett.vpn_up(lambda *a, **k: SimpleNamespace(stdout="Device does not exist", returncode=1))


@pytest.mark.parametrize("value, profile", [('"mobil"', "mobil"), ('"fast"', "fast"), ('"Mobil"', "fast"),
                                            ("true", "fast"), (None, "fast")])
def test_profile_from_the_site_file_and_mobile_pcs_always_need_the_pin(tmp_path, value, profile):
    path = tmp_path / "arbeidssted.toml"
    extra = f"profil = {value}\n" if value else ""
    path.write_text(f'id = "hjem"\nnavn = "Hjemmesykepleien"\n{extra}kort_uten_pin_minutter = 240\n', encoding="utf-8")
    site = load(path)
    assert site.profil == profile
    assert site.kort_uten_pin_minutter == (0 if profile == "mobil" else 240)


def test_home_nurse_logs_in_over_vpn_and_is_told_what_to_do_without_it(make):
    _authority, where, audit = make
    a = Authority(SimulatedReader(audit.path.parent / "kort.json", audit.path.parent / "tries.json"), audit, set(),
                  site=Arbeidssted("hjem", "Hjemmesykepleien", VPN_RANGE, 0, "mobil"), network=lambda: where["net"])
    ask(a, cmd="insert", card_id="spl")
    where["net"] = Network(("100.64.3.9",), certified=False, vpn=False)
    reply = ask(a, ROOT, cmd="login", username="jonas-lie", pin="2345")
    assert not reply["ok"] and "VPN" in reply["error"]
    where["net"] = IN_CAR
    assert ask(a, ROOT, cmd="login", username="jonas-lie", pin="2345")["ok"]
