import re
from datetime import datetime
from pathlib import Path

from nettleser import sider
from tilgang import SITUATIONS, sprak

ROOT = Path(__file__).parent.parent


def test_norwegian_is_left_as_it_is():
    assert sprak.t("Logg inn", "nb") == "Logg inn"
    assert sprak.t("Feil PIN. 2 forsøk igjen.", "nb") == "Feil PIN. 2 forsøk igjen."


def test_login_screen_in_english():
    assert sprak.t("Logg inn", "en") == "Log in"
    assert sprak.t("Feil PIN. 2 forsøk igjen.", "en") == "Wrong PIN. 2 tries left."
    assert sprak.t("Hei, Ingrid Berg", "en") == "Hello, Ingrid Berg"
    assert sprak.t("Overlege, kardiologi · Oslo universitetssykehus, Ullevål", "en") == \
        "Consultant, cardiology · Oslo University Hospital, Ullevål"
    assert sprak.t("IT-modus · St. Olavs hospital, Trondheim", "en") == "IT mode · St. Olav's Hospital, Trondheim"
    assert sprak.t("Ukjent melding fra PAM.", "en") == "Ukjent melding fra PAM."  # unknown: shown as it is


def test_every_emergency_situation_has_english():
    for situation in SITUATIONS:
        assert sprak.t(situation, "en") != situation


def test_the_card_messages_from_authd_have_english():
    """Every message medicus-authd can show on the login screen (PIN, card, emergency) is translated."""
    source = "".join((ROOT / f"tilgang/{name}.py").read_text(encoding="utf-8") for name in ("authd", "cards"))
    for message in ["Feil PIN. Kortet er nå sperret.", "Ukjent kort.", "Sett inn helsepersonellkortet ditt.",
                    "Kortet tilhører en annen bruker.", "Nødtilgang er bare for helsepersonell.", "Kortet er sperret.",
                    "Nødtilgang krever helsepersonellkort, slik at tilgangen kan spores."]:
        assert message in source, message
        assert sprak.t(message, "en") != message, message


def test_the_session_language_is_a_locale_the_image_builds():
    build = (ROOT / "os/build.sh").read_text(encoding="utf-8")
    built = re.search(r"live-config\.locales=(\S+)", build)[1].split(",")
    assert set(sprak.LOCALES.values()) <= set(built)
    assert built[0] == sprak.LOCALES["nb"]  # Norwegian stays the default


def test_date_on_the_login_screen():
    day = datetime(2026, 10, 24)
    assert sprak.date_text(day, "nb") == "Lørdag 24. oktober"
    assert sprak.date_text(day, "en") == "Saturday 24 October"


def test_browser_pages_follow_the_session_language(monkeypatch):
    assert "ikke kryptert" in sider.blocked("http://x.no/", unencrypted=True, en=False)
    assert "not encrypted" in sider.blocked("http://x.no/", unencrypted=True, en=True)
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    assert "not approved" in sider.blocked("https://x.example/")
    monkeypatch.setenv("LANG", "nb_NO.UTF-8")
    assert "ikke godkjent" in sider.blocked("https://x.example/")


def test_start_menu_entries_have_english_names():
    share = ROOT / "os/config/includes.chroot/usr/share"
    entries = list((share / "applications").glob("medicus-*.desktop")) + \
        list((share / "medicus-it/applications").glob("*.desktop"))
    assert entries
    for entry in entries:
        text = entry.read_text(encoding="utf-8")
        assert "\nName[en]=" in text and "\nComment[en]=" in text, entry.name


def test_every_web_page_has_the_language_switch():
    pages = list((ROOT / "medicus/static").glob("*.html")) + list((ROOT / "helsenett/sim/static").glob("*.html"))
    for page in pages:
        assert "i18n.js" in page.read_text(encoding="utf-8"), page.name
