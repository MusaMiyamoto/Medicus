"""The hospital's record systems in locked-down windows (journalsystem)."""

import socket
import tomllib

import pytest

import journalsystem as js

CONFIG = """
[[system]]
navn = "Journal (fjern)"
type = "rdp"
server = "RDS.sykehuset.no"
program = "||Journal"
gateway = "rdgw.sykehuset.no"

[[system]]
navn = "Lab"
type = "rdp"
server = "lab.sykehuset.no"
port = 3390
mikrofon = true

[[system]]
navn = "Journal (web)"
type = "web"
url = "https://journal.sykehuset.no/start"
"""


def systems():
    return js.parse(tomllib.loads(CONFIG))


def test_config_is_read_and_cleaned():
    remote, lab, web = systems()
    assert remote.server == "rds.sykehuset.no" and remote.endpoints() == [("rdgw.sykehuset.no", 443)]
    assert lab.endpoints() == [("lab.sykehuset.no", 3390)] and web.endpoints() == []
    assert remote.slug == "journal-fjern"


def test_remote_window_shares_nothing_and_logs_in_with_the_card():
    remote, lab, _ = systems()
    command = js.rdp_command(remote)
    assert command[0] == "xfreerdp3" and "/cert:deny" in command and "-clipboard" in command
    assert "/smartcard-logon" in command
    assert "/app:program:||Journal,name:Journal (fjern)" in command
    assert "/gateway:g:rdgw.sykehuset.no:443,type:auto" in command
    for shared in ("/drive", "+drives", "/usb", "/printer", "/serial", "/parallel", "+clipboard", "/cert:ignore"):
        assert not any(arg.startswith(shared) for arg in command)
    assert "/microphone" not in command and "/microphone" in js.rdp_command(lab)


@pytest.mark.parametrize("entry, error", [
    ('navn = "X"\ntype = "rdp"\nserver = "rds"', "navn"),
    ('navn = "Journal"\ntype = "rdp"\nserver = "rds"', "vertsnavn"),
    ('navn = "Journal"\ntype = "rdp"\nserver = "rds.sykehuset.no /drive:hjem,/home"', "vertsnavn"),
    ('navn = "Journal"\ntype = "rdp"\nserver = "rds.sykehuset.no"\nprogram = "||a,drive:x,/"', "RemoteApp"),
    ('navn = "Journal"\ntype = "rdp"\nserver = "rds.sykehuset.no"\nport = 0', "port"),
    ('navn = "Journal"\ntype = "web"\nurl = "http://journal.sykehuset.no"', "https"),
    ('navn = "Journal"\ntype = "web"\nurl = "https://a:b@journal.sykehuset.no"', "https"),
    ('navn = "Journal"\ntype = "citrix"', "type"),
    ('navn = "Journal\\nExec=sh"\ntype = "web"\nurl = "https://journal.sykehuset.no"', "navn"),
])
def test_bad_entries_stop_the_whole_update(entry, error):
    with pytest.raises(js.ConfigError, match=error):
        js.parse(tomllib.loads(f"[[system]]\n{entry}\n"))


def test_same_name_twice_is_refused():
    with pytest.raises(js.ConfigError):
        js.parse(tomllib.loads(CONFIG + '\n[[system]]\nnavn = "lab"\ntype = "web"\nurl = "https://x.sykehuset.no"\n'))


def test_hosts_block_is_replaced_not_duplicated():
    current = "127.0.0.1\tlocalhost\n"
    once = js.hosts_file(current, {"rds.sykehuset.no": ["10.1.2.3"]})
    twice = js.hosts_file(once, {"rds.sykehuset.no": ["10.1.2.4"]})
    assert twice.count(js.HOSTS_START) == 1 and "10.1.2.4\trds.sykehuset.no" in twice and "10.1.2.3" not in twice
    assert js.hosts_file(twice, {}) == current


def test_firewall_opens_exactly_the_approved_pairs():
    script = js.nft_script({"rdgw.sykehuset.no": ["10.1.0.9", "2001:db8::9"], "lab.sykehuset.no": ["10.1.0.7"],
                            "rds.sykehuset.no": ["10.1.0.5"]}, systems())
    assert "flush set inet filter journalsystem4" in script
    assert "{ 10.1.0.7 . 3390, 10.1.0.9 . 443 }" in script  # the RDS server behind the gateway is not opened
    assert "{ 2001:db8::9 . 443 }" in script and "10.1.0.5" not in script
    assert js.nft_script({}, []).count("add element") == 0


def test_resolve_survives_dns_failure():
    def broken(*a, **k):
        raise socket.gaierror("no")
    assert js.resolve("rds.sykehuset.no", 443, broken) == []
    found = [(0, 0, 0, "", ("10.1.0.5", 443)), (0, 0, 0, "", ("10.1.0.5", 443))]
    assert js.resolve("rds.sykehuset.no", 443, lambda *a, **k: found) == ["10.1.0.5"]


def test_web_filter_and_browser_allow_only_the_exact_host(tmp_path, monkeypatch):
    assert js.proxy_filter(systems()) == "^journal\\.sykehuset\\.no$\n"
    path = tmp_path / "journalsystemer.toml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setattr(js, "CONFIG", path)
    monkeypatch.setattr(js.web_hosts, "__defaults__", (path,))
    from nettleser import regler
    assert regler.is_allowed("https://journal.sykehuset.no/start")
    assert not regler.is_allowed("https://evil.journal.sykehuset.no/")
    assert not regler.is_allowed("http://journal.sykehuset.no/")
    path.write_text("ikke toml [", encoding="utf-8")
    assert not regler.is_allowed("https://journal.sykehuset.no/start")


def test_desktop_icon_opens_through_the_checked_launcher():
    text = js.desktop_entry(systems()[0])
    assert "Exec=medicus-journalsystem start journal-fjern" in text and "Name=Journal (fjern)" in text


def test_only_a_normal_card_login_may_open_a_system(tmp_path, monkeypatch):
    import journalsystem.__main__ as cli
    import tilgang.client
    path = tmp_path / "journalsystemer.toml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setattr(js, "CONFIG", path)
    monkeypatch.setattr(js.load, "__defaults__", (path,))
    started = []
    monkeypatch.setattr(cli.os, "execvp", lambda prog, args: started.append(args))
    for session in (None, {"modus": "nød"}, {"modus": "it"}, {"modus": "normal", "holdt_sekunder_igjen": 60}):
        monkeypatch.setattr(tilgang.client, "call", lambda cmd, s=session: {"okt": s})
        assert cli.start("journal-fjern") == 1
    monkeypatch.setattr(tilgang.client, "call", lambda cmd: {"okt": {"modus": "normal"}})
    cli.start("journal-web")
    assert started == [["medicus-nettleser", "https://journal.sykehuset.no/start"]]
    assert cli.start("ukjent") == 1
