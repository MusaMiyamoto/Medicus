import pytest

from nettleser import regler, sider


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/pasient",
    "http://localhost:8100/helsenorge",
    "https://www.felleskatalogen.no/medisin",
    "https://helsenorge.no/",
    "https://www.legemiddelhandboka.no/",
    "about:blank",
    "about:srcdoc",                             # a frame's inline content, no network
])
def test_allowed(url):
    assert regler.is_allowed(url)


@pytest.mark.parametrize("url", [
    "https://www.facebook.com/",
    "https://vgc.no/",                          # image server: only for pictures, not a page
    "http://www.felleskatalogen.no/",          # unencrypted to the internet
    "https://helsenorge.no.evil.example/",
    "https://fakehelsenorge.no/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "ftp://helsenorge.no/",
])
def test_blocked(url):
    assert not regler.is_allowed(url)


def test_unencrypted_internet_gets_its_own_explanation():
    assert regler.is_unencrypted("http://felleskatalogen.no/")
    assert not regler.is_unencrypted("http://127.0.0.1:8000/")
    assert not regler.is_unencrypted("https://felleskatalogen.no/")
    assert "ikke kryptert" in sider.blocked("http://felleskatalogen.no/", unencrypted=True)


def test_only_medicus_apps_get_the_microphone():
    assert regler.is_medicus_app("http://127.0.0.1:8000/")
    assert not regler.is_medicus_app("http://127.0.0.1:8100/helsenorge")
    assert not regler.is_medicus_app("https://helsenorge.no/")


@pytest.mark.parametrize("typed, url", [
    ("felleskatalogen.no", "https://felleskatalogen.no"),
    ("127.0.0.1:8000/post", "http://127.0.0.1:8000/post"),
    ("https://fhi.no", "https://fhi.no"),
    ("", regler.HOME),
])
def test_address_bar(typed, url):
    assert regler.normalize(typed) == url


def test_pages_escape_the_address():
    page = sider.blocked("https://x.example/<script>")
    assert "<script>" not in page and "&lt;script&gt;" in page


@pytest.mark.parametrize("page, window", [
    ("Pasientjournal – Medicus", "Pasientjournal – Medicus Nettleser"),
    ("NRK – Nyheter", "NRK – Nyheter – Medicus Nettleser"),
    ("Medicus Nettleser", "Medicus Nettleser"),
    ("", "Medicus Nettleser"),
    (None, "Medicus Nettleser"),
])
def test_window_title_says_medicus_once(page, window):
    assert regler.window_title(page) == window
