"""The browser's own pages (blocked, could not load), in Medicus style, in Norwegian or English.

English when the session was started in English on the login screen (LANG=en_GB…).
"""

import os
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
HOME_LINK = "<p><a href='http://127.0.0.1:8000/nettsteder'>{}</a></p>"


def english() -> bool:
    return os.environ.get("LANG", "").startswith("en")


def _page(kind: str, mark: str, title: str, body: str, en: bool) -> str:
    return (f"<!doctype html><html lang='{'en' if en else 'nb'}'><head><meta charset='utf-8'><title>{escape(title)}</title>"
            f"<style>{STYLE}</style></head><body class='{kind}'><div class='card'>"
            f"<div class='icon'>{mark}</div><h1>{escape(title)}</h1>{body}</div></body></html>")


def blocked(url: str, unencrypted: bool = False, en: bool | None = None) -> str:
    en = english() if en is None else en
    code = f"<code>{escape(url)}</code>"
    if unencrypted and en:
        return _page("blocked", "✕", "The page is not encrypted", (
            f"<p>{code} does not use an encrypted connection (https), so everything you send and read "
            "could be seen by others on the network. The browser therefore does not open it.</p>"
            "<p>Try the address with <code>https://</code> in front.</p>"
            + HOME_LINK.format("Go to approved websites")), en)
    if unencrypted:
        return _page("blocked", "✕", "Siden er ikke kryptert", (
            f"<p>{code} bruker ikke en kryptert forbindelse (https), så alt du "
            "sender og leser kunne blitt sett av andre på nettet. Nettleseren åpner den derfor ikke.</p>"
            "<p>Prøv adressen med <code>https://</code> foran.</p>"
            + HOME_LINK.format("Gå til godkjente nettsteder")), en)
    if en:
        return _page("blocked", "✕", "The website is not approved", (
            f"<p>The browser opens only websites approved for health personnel. {code} is not on the list.</p>"
            "<p>Do you need it for your work? Ask IT to add it.</p>"
            + HOME_LINK.format("Go to approved websites")), en)
    return _page("blocked", "✕", "Nettstedet er ikke godkjent", (
        f"<p>Nettleseren åpner bare godkjente nettsteder for helsepersonell. {code} er ikke på listen.</p>"
        "<p>Trenger du det i arbeidet? Be IT legge det til.</p>"
        + HOME_LINK.format("Gå til godkjente nettsteder")), en)


def failed(url: str, reason: str, en: bool | None = None) -> str:
    en = english() if en is None else en
    if en:
        return _page("failed", "!", "The page could not be opened", (
            f"<p>Could not reach <code>{escape(url)}</code>.</p><p>{escape(reason)}</p>"
            "<p>Check the network connection, or try again in a little while.</p>"), en)
    return _page("failed", "!", "Siden kunne ikke åpnes", (
        f"<p>Fikk ikke kontakt med <code>{escape(url)}</code>.</p><p>{escape(reason)}</p>"
        "<p>Sjekk nettverkstilkoblingen, eller prøv igjen om litt.</p>"), en)


def insecure(url: str, en: bool | None = None) -> str:
    en = english() if en is None else en
    if en:
        return _page("blocked", "✕", "Unsafe connection stopped", (
            f"<p>The security certificate of <code>{escape(url)}</code> is not valid. "
            "It may mean that someone is trying to eavesdrop on the connection.</p>"
            "<p>The page is stopped for your safety. Contact IT if it keeps happening.</p>"), en)
    return _page("blocked", "✕", "Usikker forbindelse stoppet", (
        f"<p>Sikkerhetssertifikatet til <code>{escape(url)}</code> er ikke gyldig. "
        "Det kan bety at noen prøver å avlytte forbindelsen.</p>"
        "<p>Siden er stoppet for din sikkerhet. Kontakt IT hvis det fortsetter.</p>"), en)
