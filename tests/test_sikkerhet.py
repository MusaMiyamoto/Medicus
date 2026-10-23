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


def test_browser_and_filter_use_the_same_list():
    from nettleser import regler

    patterns = [re.compile(line) for line in nettsteder.proxy_filter().splitlines()]
    for domain, _, _ in nettsteder.SITES:
        assert regler.is_allowed(f"https://www.{domain}/")
        assert any(p.search(f"www.{domain}") for p in patterns)


def test_government_sites_and_municipalities_are_allowed():
    from nettleser import regler

    for url in ("https://www.nav.no/", "https://www.skatteetaten.no/", "https://login.idporten.no/",
                "https://www.oslo.kommune.no/", "https://www.regjeringen.no/"):
        assert regler.is_allowed(url), url
    assert not regler.is_allowed("https://kommune.no.example.com/")
