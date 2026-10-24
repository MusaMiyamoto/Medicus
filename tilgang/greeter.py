"""The Medicus login screen (a LightDM greeter, GTK 4).

    medicus-greeter            real login screen, started by LightDM
    medicus-greeter --demo     same screen with fake back-ends, for development and screenshots
"""

import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import EMERGENCY_MINUTES, EMERGENCY_USER, IT_ROLE, SITUATIONS  # noqa: E402
from .ekg import Ekg  # noqa: E402
from .sprak import LOCALES, date_text, t  # noqa: E402

BRANDING = Path(__file__).parent.parent / "branding"

CSS = """
window.medicus { background: linear-gradient(160deg, #06281a 0%, #0f5333 50%, #1f8f55 100%); color: #ffffff; }
.tagline { font-size: 10px; letter-spacing: 3px; color: rgba(255, 255, 255, 0.62); }
.site { font-size: 15px; font-weight: 600; color: #ffffff; margin-top: 6px; }
.glass { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.14);
         border-radius: 16px; padding: 8px 16px; }
.clock { font-size: 30px; font-weight: 300; }
.date { font-size: 12px; color: rgba(255, 255, 255, 0.75); }
.panel { background: #ffffff; color: #17241c; border-radius: 22px; padding: 30px 32px;
         box-shadow: 0 18px 50px rgba(0, 0, 0, 0.35); }
.panel .title { font-size: 22px; font-weight: 700; }
.panel .muted { color: #56655b; }
.panel entry { min-height: 46px; font-size: 18px; border-radius: 12px; }
.panel button { min-height: 46px; font-weight: 700; border-radius: 12px; }
.card-badge { background: #1a7f4b; border-radius: 999px; padding: 14px; }
button.primary { background: #1a7f4b; color: #ffffff; border: none; }
button.primary:hover { background: #156b3f; }
button.emergency { background: transparent; color: #b3261e; border: 2px solid #b3261e; }
button.emergency:hover { background: #fdecea; }
.emergency-info { font-size: 12px; color: #7a1a14; }
button.emergency-go { background: #b3261e; color: #ffffff; border: none; }
button.emergency-go:hover { background: #8f1d17; }
.emergency-box { background: #fdecea; border-radius: 14px; padding: 14px; }
.emergency-title { font-size: 16px; font-weight: 700; color: #7a1a14; }
.error { color: #b3261e; font-weight: 600; }
.sim { padding: 10px 14px; }
.sim .sim-title { font-size: 10px; letter-spacing: 2px; font-weight: 700; color: #7fe0ad; }
.sim .sim-text { font-size: 13px; color: rgba(255, 255, 255, 0.85); }
.sim button, .sim dropdown button { background: rgba(255, 255, 255, 0.12); color: #ffffff; border: none; border-radius: 10px; }
.sim button:hover { background: rgba(255, 255, 255, 0.22); }
.power { min-width: 54px; min-height: 54px; border-radius: 999px; padding: 0;
         background: rgba(255, 255, 255, 0.10); border: 1px solid rgba(255, 255, 255, 0.16); }
.power:hover { background: rgba(255, 255, 255, 0.22); }
.sim button.card-toggle { padding: 6px 14px; }
button.lang { min-height: 54px; border-radius: 999px; padding: 0 20px; font-weight: 600; color: #ffffff;
              background: rgba(255, 255, 255, 0.10); border: 1px solid rgba(255, 255, 255, 0.16); }
button.lang:hover { background: rgba(255, 255, 255, 0.22); }
/* The card and workplace lists: a plain light list, without the dark shadow frame around it. */
.sim popover > contents { box-shadow: none; border-radius: 10px; padding: 4px; }
.sim popover { box-shadow: none; margin: 0; }
"""


BLOCKED = "Kortet er sperret etter for mange feil PIN-forsøk. Kontakt IT-avdelingen for å låse det opp."
REVOKED = "Dette kortet er meldt tapt eller erstattet og virker ikke lenger. Kontakt IT-avdelingen."
EXPIRED = "Kortet er utløpt. Hent nytt kort. Nødtilgang virker fortsatt."


def card_problem(card: dict | None) -> tuple[str, bool, bool]:
    """(message, normal login possible, emergency access possible) for the card in the reader."""
    if not card:
        return "", False, False
    if card.get("tilbakekalt"):
        return REVOKED, False, False  # someone else may be holding it
    if card.get("sperret"):
        return BLOCKED, False, False
    if card.get("utlopt"):
        return EXPIRED, False, True
    return "", True, True


def picture(name: str, size: int) -> Gtk.Image:
    image = Gtk.Image.new_from_file(str(BRANDING / name))
    image.set_pixel_size(size)
    return image


class LightDMBackend:
    def __init__(self):
        gi.require_version("LightDM", "1")
        from gi.repository import LightDM

        self.LightDM = LightDM
        self.greeter = LightDM.Greeter()
        self.greeter.connect("show-prompt", self._prompt)
        self.greeter.connect("show-message", self._message)
        self.greeter.connect("authentication-complete", self._complete)
        self.greeter.connect_to_daemon_sync()
        self.secret = None
        self.session = None
        self.message = ""
        self.done = None
        self.language = None  # e.g. "en_GB.UTF-8": the locale the session starts in

    def login(self, user, secret, session, done):
        if self.greeter.get_in_authentication():
            self.greeter.cancel_authentication()
        self.secret, self.session, self.message, self.done = secret, session, "", done
        self.greeter.authenticate(user)

    def _prompt(self, _greeter, _text, _kind):
        self.greeter.respond(self.secret)
        self.secret = None

    def _message(self, _greeter, text, _kind):
        self.message = text.strip()

    def _complete(self, _greeter):
        if self.greeter.get_is_authenticated():
            try:
                if self.language:
                    self.greeter.set_language(self.language)
                self.greeter.start_session_sync(self.session)
                return
            except GLib.Error:
                self.done(False, "Kunne ikke starte økten.")
                return
        self.done(False, self.message or "Innloggingen ble avvist.")

    def shutdown(self):
        self.LightDM.shutdown()

    def restart(self):
        self.LightDM.restart()


class AuthdBackend:
    def __init__(self):
        from . import client

        self.client = client

    def status(self):
        return self.client.call("status")

    def cards(self):
        return self.client.call("cards")["kort"]

    def insert(self, card_id):
        self.client.call("insert", card_id=card_id)

    def remove(self):
        self.client.call("remove")

    def set_site(self, site_id):
        self.client.call("set_site", site_id=site_id)


class DemoBackend:
    """In-memory stand-ins for screenshots and development without LightDM."""

    SITES = [{"id": "ous-ulleval", "navn": "Oslo universitetssykehus, Ullevål"},
             {"id": "stolav", "navn": "St. Olavs hospital, Trondheim"}]
    CARDS = [
        {"card_id": "lege", "navn": "Ingrid Berg", "rolle": "Lege", "hpr": "999000101", "username": "ingrid-berg",
         "stillinger": {"ous-ulleval": "Overlege, kardiologi", "stolav": "Gjesteoverlege, kardiologi"}, "sperret": False},
        {"card_id": "amb", "navn": "Amir Haddad", "rolle": "Ambulansearbeider", "hpr": "999000303",
         "username": "amir-haddad", "stillinger": {}, "sperret": False},
        {"card_id": "it", "navn": "Eirik Strand", "rolle": "IT", "hpr": "IT-4401",
         "username": "eirik-strand", "stillinger": {}, "sperret": False},
    ]

    def __init__(self):
        self.card = None
        self.site = self.SITES[0]
        self.language = None

    def status(self):
        card = None
        if self.card:
            card = {**self.card, "stilling": self.card["stillinger"].get(self.site["id"]) or self.card["rolle"]}
        return {"kort": card, "okt": None, "simulert": True, "arbeidssted": self.site, "arbeidssteder": self.SITES}

    def cards(self):
        return self.CARDS

    def insert(self, card_id):
        self.card = next(c for c in self.CARDS if c["card_id"] == card_id)

    def remove(self):
        self.card = None

    def set_site(self, site_id):
        self.site = next(s for s in self.SITES if s["id"] == site_id)

    def login(self, user, secret, session, done):
        ok = secret == "1234" or user == EMERGENCY_USER
        GLib.timeout_add(400, lambda: done(ok, "" if ok else "Feil PIN. 2 forsøk igjen.") and False)

    def shutdown(self):
        print("shutdown")

    def restart(self):
        print("restart")


class LoginWindow(Gtk.ApplicationWindow):
    def __init__(self, app, auth, lightdm, lang="nb"):
        super().__init__(application=app, title="Medicus")
        self.auth, self.lightdm, self.lang = auth, lightdm, lang
        self.card_id = "init"  # differs from every real state, so the first refresh fills in the text
        self.busy = False
        self.add_css_class("medicus")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{side}")(32)
        self.set_child(root)

        # Top left: logo and the MED✚CUS wordmark. Top right: clock in a frosted panel.
        top = Gtk.Box(spacing=16, valign=Gtk.Align.START)
        top.append(picture("medicus-logo.svg", 60))
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        wordmark = Gtk.Picture.new_for_filename(str(BRANDING / "wordmark-compact.svg"))
        wordmark.set_can_shrink(False)
        wordmark.set_halign(Gtk.Align.START)
        tagline = Gtk.Label(label=self.t("TRYGG ARBEIDSSTASJON FOR HELSEPERSONELL"), xalign=0)
        tagline.add_css_class("tagline")
        # This PC's workplace, e.g. "Oslo universitetssykehus, Ullevål".
        self.site_label = Gtk.Label(xalign=0)
        self.site_label.add_css_class("site")
        brand.append(wordmark)
        brand.append(tagline)
        brand.append(self.site_label)
        top.append(brand)
        top.append(Gtk.Box(hexpand=True))
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START)
        clock_box.add_css_class("glass")
        self.clock = Gtk.Label(xalign=0.5)
        self.clock.add_css_class("clock")
        self.date = Gtk.Label(xalign=0.5)
        self.date.add_css_class("date")
        clock_box.append(self.clock)
        clock_box.append(self.date)
        top.append(clock_box)
        root.append(top)

        center = Gtk.Box(vexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        root.append(center)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.add_css_class("panel")
        panel.set_size_request(440, -1)
        center.append(panel)

        # Who's at the reader: a card symbol before a card is inserted, the person's picture after.
        header = Gtk.Box(spacing=16)
        self.badge = Gtk.Stack()
        no_card = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        no_card.add_css_class("card-badge")
        no_card.append(picture("icons/kort.svg", 36))
        self.badge.add_named(no_card, "kort")
        self.badge.add_named(picture("avatar.svg", 64), "person")
        header.append(self.badge)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(xalign=0, ellipsize=3)
        self.title.add_css_class("title")
        self.subtitle = Gtk.Label(xalign=0, ellipsize=3)
        self.subtitle.add_css_class("muted")
        names.append(self.title)
        names.append(self.subtitle)
        header.append(names)
        panel.append(header)

        self.pin = Gtk.PasswordEntry(placeholder_text=self.t("PIN-kode"), show_peek_icon=False)
        self.pin.connect("activate", lambda *_: self.login())
        self.login_button = Gtk.Button(label=self.t("Logg inn"))
        self.login_button.add_css_class("primary")
        self.login_button.connect("clicked", lambda *_: self.login())
        panel.append(self.pin)
        panel.append(self.login_button)

        self.message = Gtk.Label(xalign=0, wrap=True, max_width_chars=40, width_chars=40)
        self.message.add_css_class("error")
        panel.append(self.message)

        # While the PIN is checked and the desktop starts: the Medicus heartbeat animation.
        # No text: the animation alone says "working". Screen readers still get a label.
        self.loading = Ekg(width=160, height=40, color=(26 / 255, 127 / 255, 75 / 255))
        self.loading.set_halign(Gtk.Align.CENTER)
        self.loading.set_visible(False)
        panel.append(self.loading)

        panel.append(Gtk.Separator())
        self.emergency_button = Gtk.Button(label=self.t("Nødtilgang"))
        self.emergency_button.add_css_class("emergency")
        self.emergency_button.connect("clicked", lambda *_: self.show_emergency(True))
        panel.append(self.emergency_button)
        # Fixed line breaks: wrapping labels can stretch the panel when the screen is short.
        self.emergency_info = Gtk.Label(xalign=0, label=self.t(
            f"Kun livsviktig informasjon i {EMERGENCY_MINUTES} min. Logges med ditt navn.\n"
            "Du skriver en rapport om hvorfor før skiftet er slutt."))
        self.emergency_info.add_css_class("emergency-info")
        panel.append(self.emergency_info)

        # Two taps in total: "Nødtilgang", then the situation. Hard to open by mistake, but no
        # typing and no questions. The situation is filled in on the report afterwards.
        self.emergency = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, visible=False)
        self.emergency.add_css_class("emergency-box")
        self.emergency.append(Gtk.Label(xalign=0, label=self.t("Hva er situasjonen?"), css_classes=["emergency-title"]))
        for situation in SITUATIONS:
            button = Gtk.Button(label=self.t(situation))
            button.add_css_class("emergency-go")
            button.connect("clicked", lambda _b, s=situation: self.start_emergency(s))
            self.emergency.append(button)
        cancel = Gtk.Button(label=self.t("Avbryt"))
        cancel.connect("clicked", lambda *_: self.show_emergency(False))
        self.emergency.append(cancel)
        panel.append(self.emergency)

        # Bottom left: the simulated card reader (demo only). Bottom right: round power buttons.
        bottom = Gtk.Box(spacing=14, valign=Gtk.Align.END)
        self.sim = Gtk.Box(spacing=12)
        self.sim.add_css_class("glass")
        self.sim.add_css_class("sim")
        self.sim.append(picture("icons/kort.svg", 30))
        sim_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        sim_title = Gtk.Label(label="DEMO", xalign=0)
        sim_title.add_css_class("sim-title")
        sim_label = Gtk.Label(label=self.t("Simulering"), xalign=0)
        sim_label.add_css_class("sim-text")
        sim_text.append(sim_title)
        sim_text.append(sim_label)
        self.sim.append(sim_text)
        self.sim_cards = self.auth.cards() if self.auth.status().get("simulert") else []
        self.sim_choice = Gtk.DropDown.new_from_strings([f"{c['navn']} – {self.t(c['rolle'])}" for c in self.sim_cards] or ["–"])
        self.sim_choice.set_valign(Gtk.Align.CENTER)
        # One button that follows the reader: "Sett inn kort" when empty, "Ta ut kort" when a card is in.
        self.card_toggle = Gtk.Button(valign=Gtk.Align.CENTER)
        self.card_toggle.add_css_class("card-toggle")
        toggle_content = Gtk.Box(spacing=8)
        self.toggle_icon = Gtk.Stack()
        self.toggle_icon.add_named(picture("icons/kort-inn.svg", 22), "inn")
        self.toggle_icon.add_named(picture("icons/kort-ut.svg", 22), "ut")
        self.toggle_label = Gtk.Label()
        toggle_content.append(self.toggle_icon)
        toggle_content.append(self.toggle_label)
        self.card_toggle.set_child(toggle_content)
        self.card_toggle.connect("clicked", lambda *_: self.sim_toggle())
        # A click must not leave focus here, or Enter in the PIN field would press it (and take the card out).
        self.card_toggle.set_focus_on_click(False)
        # Demo only: pretend this PC stands at another hospital, to see the workplace change.
        status = self.auth.status()
        self.sim_sites = status.get("arbeidssteder") or []
        self.site_choice = Gtk.DropDown.new_from_strings([self.t(s["navn"]) for s in self.sim_sites] or ["–"])
        self.site_choice.set_valign(Gtk.Align.CENTER)
        current = next((i for i, s in enumerate(self.sim_sites) if s["id"] == status["arbeidssted"]["id"]), 0)
        self.site_choice.set_selected(current)
        self.site_choice.connect("notify::selected", lambda *_: self.sim_site())
        self.site_choice.set_visible(bool(self.sim_sites))
        for choice in (self.sim_choice, self.site_choice):
            choice.set_focus_on_click(False)
        self.sim.append(self.site_choice)
        self.sim.append(self.sim_choice)
        self.sim.append(self.card_toggle)
        self.sim.set_visible(bool(self.sim_cards))
        bottom.append(self.sim)
        bottom.append(Gtk.Box(hexpand=True))
        # Norsk / English: the screen at once, and the desktop session after login.
        language = Gtk.Button(label="English" if lang == "nb" else "Norsk", valign=Gtk.Align.CENTER)
        language.update_property([Gtk.AccessibleProperty.LABEL],
                                 ["Switch to English" if lang == "nb" else "Bytt til norsk"])
        language.add_css_class("lang")
        language.set_focus_on_click(False)
        language.connect("clicked", lambda *_: app.switch_language())
        bottom.append(language)
        for label, icon, action in (("Start på nytt", "icons/omstart.svg", self.lightdm.restart),
                                    ("Slå av", "icons/slaa-av.svg", self.lightdm.shutdown)):
            label = self.t(label)
            button = Gtk.Button(valign=Gtk.Align.CENTER, tooltip_text=label)
            button.update_property([Gtk.AccessibleProperty.LABEL], [label])
            button.add_css_class("power")
            button.set_child(picture(icon, 22))
            button.connect("clicked", lambda _b, a=action: a())
            bottom.append(button)
        root.append(bottom)

        self.refresh()
        self.tick()
        self.timers = [GLib.timeout_add(1000, self.refresh), GLib.timeout_add(1000, self.tick)]

    def t(self, text):
        return t(text, self.lang)

    def stop(self):
        """Before this window is replaced (a change of language)."""
        for timer in self.timers:
            GLib.source_remove(timer)

    def tick(self):
        now = datetime.now()
        self.clock.set_text(now.strftime("%H:%M"))
        self.date.set_text(date_text(now, self.lang))
        return True

    def refresh(self):
        try:
            status = self.auth.status()
            card, site = status["kort"], status["arbeidssted"]
        except Exception:
            card, site = None, {"id": "", "navn": ""}
            self.subtitle.set_text(self.t("Får ikke kontakt med innloggingstjenesten."))
        self.site_label.set_text(self.t(site["navn"]))
        state = (card["card_id"] if card else None, site["id"])
        if state != self.card_id:
            self.card_id = state
            self.card = card
            self.pin.set_text("")
            self.message.set_text("")
            self.show_emergency(False)
            self.badge.set_visible_child_name("person" if card else "kort")
            self.toggle_icon.set_visible_child_name("ut" if card else "inn")
            self.toggle_label.set_text(self.t("Ta ut kort" if card else "Sett inn kort"))
            self.sim_choice.set_sensitive(card is None)
            if card:
                self.title.set_text(self.t(f"Hei, {card['navn']}"))
                if card.get("rolle") == IT_ROLE:
                    self.subtitle.set_text(self.t(f"IT-modus · {site['navn']}"))
                else:
                    self.subtitle.set_text(self.t(f"{card['stilling']} · {site['navn']}"))
                # Emergency access is for health personnel; IT staff never see patient data.
                self.emergency_button.set_visible(card.get("rolle") != IT_ROLE)
                self.emergency_info.set_visible(card.get("rolle") != IT_ROLE)
                if card.get("rapporter"):
                    first = card["rapporter"][0]
                    late = self.t("Fristen er ute! ") if first["forsinket"] else ""
                    due = self.t(f"Du har en nødtilgangsrapport å skrive (frist kl. {first['frist'][11:16]}).")
                    self.message.set_text(f"{late}{due}\n{self.t('Den åpnes når du logger inn.')}")
                self.pin.grab_focus()
            else:
                self.title.set_text(self.t("Sett inn helsepersonellkortet"))
                self.subtitle.set_text(self.t("Kortleseren står ved siden av skjermen."))
        problem, normal, emergency = card_problem(card)
        if problem:
            self.message.set_text(self.t(problem))
        for widget in (self.pin, self.login_button):
            widget.set_sensitive(normal and not self.busy)
        self.emergency_button.set_sensitive(emergency and not self.busy)
        return True

    def show_emergency(self, visible):
        self.emergency.set_visible(visible)
        for widget in (self.emergency_button, self.emergency_info, self.pin, self.login_button):
            widget.set_visible(not visible)

    def set_busy(self, busy, text="Logger inn"):
        self.busy = busy
        self.loading.update_property([Gtk.AccessibleProperty.LABEL], [self.t(text)])
        self.loading.set_visible(busy)
        self.message.set_visible(not busy)
        self.refresh()

    def finished(self, ok, message):
        self.set_busy(False)
        if not ok:
            self.message.set_text(self.t(message))
            self.pin.set_text("")
            # The field lost focus while it was disabled during the check. Without this the next
            # click only gives the field its focus back, and a PIN typed after it goes nowhere.
            self.pin.grab_focus()
        return False

    def login(self):
        if not self.card or self.busy:
            return
        self.message.set_text("")
        self.set_busy(True)
        session = "medicus-it" if self.is_it_card() else "xfce"
        self.lightdm.language = LOCALES[self.lang]
        self.lightdm.login(self.card["username"], self.pin.get_text(), session, self.finished)

    def is_it_card(self):
        return bool(self.card) and self.card.get("rolle") == IT_ROLE

    def start_emergency(self, situation):
        if not self.card or self.busy:
            return
        self.message.set_text("")
        self.emergency.set_visible(False)
        self.set_busy(True, "Starter nødtilgang")
        self.lightdm.language = LOCALES[self.lang]
        # LightDM asks PAM for a "password"; for emergency access that answer is the situation.
        self.lightdm.login(EMERGENCY_USER, situation, "medicus-nod", self.finished)

    def sim_site(self):
        if not self.sim_sites:
            return
        try:
            self.auth.set_site(self.sim_sites[self.site_choice.get_selected()]["id"])
        except Exception as e:
            self.message.set_text(self.t(str(e)))
        self.refresh()

    def sim_toggle(self):
        try:
            if self.card:
                self.auth.remove()
            elif self.sim_cards:
                self.auth.insert(self.sim_cards[self.sim_choice.get_selected()]["card_id"])
        except Exception as e:
            self.message.set_text(self.t(str(e)))
        self.refresh()


class GreeterApp(Gtk.Application):
    def __init__(self, demo):
        super().__init__(application_id="no.medicus.Greeter")
        self.demo = demo
        self.lang = "nb"

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.demo:
            demo = DemoBackend()
            self.auth, self.lightdm = demo, demo
        else:
            self.auth, self.lightdm = AuthdBackend(), LightDMBackend()
        self.show_window()

    def switch_language(self):
        self.lang = "en" if self.lang == "nb" else "nb"
        old = self.window
        old.stop()
        self.show_window()
        old.destroy()

    def show_window(self):
        self.window = LoginWindow(self, self.auth, self.lightdm, self.lang)
        monitor = Gdk.Display.get_default().get_monitors().get_item(0)
        geometry = monitor.get_geometry()
        self.window.set_default_size(geometry.width, geometry.height)
        if not self.demo:
            self.window.fullscreen()
        self.window.present()


def main(argv=None):
    argv = sys.argv if argv is None else argv
    demo = "--demo" in argv
    return GreeterApp(demo).run([argv[0]])


if __name__ == "__main__":
    sys.exit(main())
