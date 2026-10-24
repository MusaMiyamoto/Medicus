"""The demo site (site/, served by Cloudflare from wrangler.jsonc): every picture exists, both languages match."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
VOID = {"meta", "link", "img", "input", "br", "hr"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.sources, self.no, self.en, self.problems = [], [], 0, 0, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("img", "link") and (attrs.get("src") or attrs.get("href", "")).endswith((".jpg", ".svg")):
            self.sources.append(attrs.get("src") or attrs["href"])
        classes = (attrs.get("class") or "").split()
        self.no += "no" in classes
        self.en += "en" in classes
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.problems.append(tag)


def page() -> Page:
    p = Page()
    p.feed((SITE / "index.html").read_text(encoding="utf-8"))
    return p


def test_the_page_is_well_formed_and_every_text_is_in_both_languages():
    p = page()
    assert p.problems == [] and p.stack == []
    assert p.no == p.en > 50


def test_every_picture_exists_and_every_screenshot_is_shown():
    p = page()
    for src in p.sources:
        assert (SITE / src).is_file(), src
    shown = {s for s in p.sources if s.startswith("img/")}
    assert shown == {f"img/{f.name}" for f in (SITE / "img").glob("*.jpg")}


def test_the_logo_is_the_one_from_branding():
    assert (SITE / "logo.svg").read_bytes() == (ROOT / "branding/medicus-logo.svg").read_bytes()


def test_wrangler_serves_the_site_folder_only():
    text = re.sub(r"^\s*//.*$", "", (ROOT / "wrangler.jsonc").read_text(encoding="utf-8"), flags=re.M)
    config = json.loads(text)
    assert config["assets"] == {"directory": "./site"} and "main" not in config


def test_the_demo_cards_on_the_site_are_the_real_ones():
    cards = json.loads((ROOT / "os/config/includes.chroot/etc/medicus/simkort-demo.json").read_text(encoding="utf-8"))
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for card in cards:
        assert card["navn"] in html and card["demo_pin"] in html
