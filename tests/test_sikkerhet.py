import re

from medicus import nettsteder, sikkerhet


def by_name(results):
    return {r["navn"]: r for r in results}


def test_everything_running():
    results = by_name(sikkerhet.checks(active=lambda unit: True,
                                       read=lambda p: "none [integrity] confidentiality" if "lockdown" in p else "Y"))
    assert results["Brannmur"]["status"] == "ok"
    assert results["Kjernebeskyttelse"]["status"] == "ok"
    assert results["VPN til helsenettet"]["status"] == "ok"
    assert results["AppArmor"]["status"] == "ok"


def test_failures_are_shown_plainly():
    results = by_name(sikkerhet.checks(active=lambda unit: False, read=lambda p: ""))
    assert results["Brannmur"]["status"] == "feil"
    assert "Kontakt IT" in results["Brannmur"]["forklaring"]
    assert results["Virusbeskyttelse"]["status"] == "feil"
    # A missing VPN is information, not an error: it needs an agreement first.
    assert results["VPN til helsenettet"]["status"] == "info"


def test_old_virus_database_is_a_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(sikkerhet, "newest_mtime", lambda paths: 0.0)
    results = by_name(sikkerhet.checks(active=lambda unit: True, read=lambda p: "", now=lambda: 30 * 86400))
    assert results["Virusbeskyttelse"]["status"] == "advarsel"


def test_web_filter_matches_sites_and_subdomains_only():
    patterns = [re.compile(line) for line in nettsteder.proxy_filter().splitlines()]

    def allowed(host):
        return any(p.search(host) for p in patterns)

    assert allowed("helsenorge.no")
    assert allowed("www.felleskatalogen.no")
    assert not allowed("helsenorge.no.evil.com")
    assert not allowed("fakehelsenorge.no")
    assert not allowed("google.com")


def test_browser_allowlist_matches_filter():
    assert len(nettsteder.firefox_exceptions()) == len(nettsteder.SITES)
    assert all(e.startswith("https://") for e in nettsteder.firefox_exceptions())
