"""Which addresses the browser may open. No GTK here, so it can be tested on its own.

Allowed:
  - the Medicus apps on this machine (http://127.0.0.1 and http://localhost, any port)
  - the approved health websites in medicus/nettsteder.py, over HTTPS only, with subdomains
Everything else is blocked, including unencrypted http:// to the internet and local files.
The web filter (tinyproxy) enforces the same list again, outside the browser.
"""

from urllib.parse import urlparse

from medicus import nettsteder

LOCAL_HOSTS = {"127.0.0.1", "localhost"}
HOME = "http://127.0.0.1:8000/nettsteder"


def is_allowed(url: str) -> bool:
    # about:srcdoc is a frame's inline content, written by the page itself: no network involved.
    if url in ("about:blank", "about:srcdoc", ""):
        return True
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if parts.scheme in ("http", "https") and host in LOCAL_HOSTS:
        return True
    if parts.scheme != "https" or not host:
        return False
    return any(host == domain or host.endswith("." + domain) for domain, _, _ in nettsteder.SITES)


def is_unencrypted(url: str) -> bool:
    """An http:// address on the internet (blocked because nothing would be encrypted)."""
    parts = urlparse(url)
    return parts.scheme == "http" and (parts.hostname or "").lower() not in LOCAL_HOSTS


def is_medicus_app(url: str) -> bool:
    """The local Medicus apps, which may use the microphone (journal assistant)."""
    parts = urlparse(url)
    return parts.scheme == "http" and parts.hostname == "127.0.0.1" and parts.port == 8000


def normalize(text: str) -> str:
    """What the user typed in the address bar → a URL. Bare names get https://."""
    text = text.strip()
    if not text:
        return HOME
    if "://" in text or text.startswith("about:"):
        return text
    host = text.split("/", 1)[0].split(":", 1)[0]
    scheme = "http" if host in LOCAL_HOSTS else "https"
    return f"{scheme}://{text}"


def window_title(page_title: str | None) -> str:
    """"Pasientjournal – Nettleser", never "… – Medicus – Nettleser"."""
    title = (page_title or "").strip()
    for suffix in (" – Medicus", " - Medicus"):
        title = title.removesuffix(suffix)
    if not title or title in ("Medicus", "Nettleser", "Medicus Nettleser"):
        return "Nettleser"
    return f"{title} – Nettleser"
