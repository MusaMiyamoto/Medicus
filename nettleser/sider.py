"""The browser's own pages (blocked, could not load), in Medicus style and Norwegian."""

from html import escape

STYLE = """
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f2f6f3;
       font: 17px/1.5 "Noto Sans", sans-serif; color: #17241c; }
.card { max-width: 560px; background: #fff; border: 1px solid #d2ddd5; border-radius: 18px; padding: 32px 36px; }
h1 { margin: 0 0 8px; font-size: 1.4rem; color: #0f4f2f; }
.icon { width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center;
        color: #fff; font-size: 30px; font-weight: 800; margin-bottom: 16px; }
.blocked .icon { background: #b3261e; } .failed .icon { background: #c98a00; }
code { background: #eef5f0; padding: 2px 6px; border-radius: 6px; word-break: break-all; }
a { color: #1a7f4b; font-weight: 600; }
"""


def _page(kind: str, mark: str, title: str, body: str) -> str:
    return (f"<!doctype html><html lang='nb'><head><meta charset='utf-8'><title>{escape(title)}</title>"
            f"<style>{STYLE}</style></head><body class='{kind}'><div class='card'>"
            f"<div class='icon'>{mark}</div><h1>{escape(title)}</h1>{body}</div></body></html>")


def blocked(url: str, unencrypted: bool = False) -> str:
    if unencrypted:
        return _page("blocked", "✕", "Siden er ikke kryptert", (
            f"<p><code>{escape(url)}</code> bruker ikke en kryptert forbindelse (https), så alt du "
            "sender og leser kunne blitt sett av andre på nettet. Nettleseren åpner den derfor ikke.</p>"
            "<p>Prøv adressen med <code>https://</code> foran.</p>"
            "<p><a href='http://127.0.0.1:8000/nettsteder'>Gå til godkjente nettsteder</a></p>"))
    return _page("blocked", "✕", "Nettstedet er ikke godkjent", (
        f"<p>Nettleseren åpner bare godkjente nettsteder for helsepersonell. "
        f"<code>{escape(url)}</code> er ikke på listen.</p>"
        "<p>Trenger du det i arbeidet? Be IT legge det til.</p>"
        "<p><a href='http://127.0.0.1:8000/nettsteder'>Gå til godkjente nettsteder</a></p>"))


def failed(url: str, reason: str) -> str:
    return _page("failed", "!", "Siden kunne ikke åpnes", (
        f"<p>Fikk ikke kontakt med <code>{escape(url)}</code>.</p>"
        f"<p>{escape(reason)}</p>"
        "<p>Sjekk nettverkstilkoblingen, eller prøv igjen om litt.</p>"))


def insecure(url: str) -> str:
    return _page("blocked", "✕", "Usikker forbindelse stoppet", (
        f"<p>Sikkerhetssertifikatet til <code>{escape(url)}</code> er ikke gyldig. "
        "Det kan bety at noen prøver å avlytte forbindelsen.</p>"
        "<p>Siden er stoppet for din sikkerhet. Kontakt IT hvis det fortsetter.</p>"))
