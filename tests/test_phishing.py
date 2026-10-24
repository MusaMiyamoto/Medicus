import pytest

from helsenett.phishing import check_email, imitates, skeleton


def test_lookalike_characters_fold():
    assert skeleton("He1sen0rge") == "helsenorge"


@pytest.mark.parametrize("domain", ["helsen0rge.no", "helsenorge-sikkerhet.com", "nhn-no.com", "he1senorge.no"])
def test_lookalike_domains_are_caught(domain):
    assert imitates(domain)


@pytest.mark.parametrize("domain", ["helsenorge.no", "varsel.helsenorge.no", "nhn.no", "medisinutstyr.no", "gmail.com"])
def test_real_or_unrelated_domains_pass(domain):
    assert imitates(domain) is None


def test_classic_phishing_gets_every_warning():
    v = check_email(
        "Helsenorge", "varsel@helsenorge-sikkerhet.com",
        "Kontoen din blir stengt",
        "Logg inn med BankID innen 24 timer: [https://helsenorge.no/logginn](http://helsen0rge-login.xyz/a)",
        attachments=["faktura.pdf.exe"],
    )
    assert v.level == "mistenkelig"
    text = " ".join(v.reasons)
    assert "ligner på «helsenorge.no»" in text
    assert "tidspress" in text
    assert "viser «helsenorge.no», men går egentlig til «helsen0rge-login.xyz»" in text
    assert "ukryptert" in text
    assert "faktura.pdf.exe" in text
    assert v.links == [{"tekst": "https://helsenorge.no/logginn", "går_til": "helsen0rge-login.xyz"}]


def test_display_name_mismatch():
    v = check_email("Norsk helsenett (NHN)", "it@support-desk.net", "Info", "Hei")
    assert v.level == "mistenkelig"
    assert "Avsendernavnet" in v.reasons[0]


def test_reply_to_mismatch():
    v = check_email("Ola", "ola@medisinutstyr.no", "Tilbud", "Hei", reply_to="ola@gmail.com")
    assert v.level == "mistenkelig"


def test_ordinary_external_mail_is_only_marked_external():
    v = check_email("Medisinutstyr AS", "salg@medisinutstyr.no", "Nye hansker på lager",
                    "Hei! Se katalogen: https://medisinutstyr.no/katalog", attachments=["katalog.pdf"])
    assert v.level == "ekstern"
    assert v.reasons == []


def test_ip_address_links():
    v = check_email("X", "x@example.org", "Hei", "Se http://203.0.113.9/fil")
    assert any("IP-adresse" in r for r in v.reasons)
