"""The Medicus login screen (a LightDM greeter, GTK 4).

    medicus-greeter            real login screen, started by LightDM
    medicus-greeter --demo     same screen with fake back-ends, for development and screenshots
"""

import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import EMERGENCY_MINUTES, EMERGENCY_USER  # noqa: E402

BRANDING = Path(__file__).parent.parent / "branding"
REASONS = ["Bevisstløs pasient", "Hjertestans", "Alvorlig allergisk reaksjon", "Alvorlig skade", "Annet"]
DAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]

CSS = """
window.medicus { background: linear-gradient(160deg, #06281a 0%, #0f5333 50%, #1f8f55 100%); color: #ffffff; }
.tagline { font-size: 10px; letter-spacing: 3px; color: rgba(255, 255, 255, 0.62); }
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
button.emergency-go { background: #b3261e; color: #ffffff; border: none; }
.emergency-box { background: #fdecea; border-radius: 14px; padding: 16px; color: #7a1a14; }
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
"""


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


class DemoBackend:
    """In-memory stand-ins for screenshots and development without LightDM."""

    CARDS = [
        {"card_id": "lege", "navn": "Ingrid Berg", "rolle": "Lege", "virksomhet": "Medicus legesenter (simulert)",
         "hpr": "999000101", "username": "ingrid-berg", "sperret": False},
        {"card_id": "amb", "navn": "Amir Haddad", "rolle": "Ambulansearbeider", "virksomhet": "Ambulansetjenesten (simulert)",
         "hpr": "999000303", "username": "amir-haddad", "sperret": False},
    ]

    def __init__(self):
        self.card = None

    def status(self):
        return {"kort": self.card, "okt": None, "simulert": True}

    def cards(self):
        return self.CARDS

    def insert(self, card_id):
        self.card = next(c for c in self.CARDS if c["card_id"] == card_id)

    def remove(self):
        self.card = None

    def login(self, user, secret, session, done):
        ok = secret == "1234" or user == EMERGENCY_USER
        GLib.timeout_add(400, lambda: done(ok, "" if ok else "Feil PIN. 2 forsøk igjen.") and False)

    def shutdown(self):
        print("shutdown")

    def restart(self):
        print("restart")


class LoginWindow(Gtk.ApplicationWindow):
    def __init__(self, app, auth, lightdm):
        super().__init__(application=app, title="Medicus")
        self.auth, self.lightdm = auth, lightdm
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
        tagline = Gtk.Label(label="TRYGG ARBEIDSSTASJON FOR HELSEPERSONELL", xalign=0)
        tagline.add_css_class("tagline")
        brand.append(wordmark)
        brand.append(tagline)
        top.append(brand)
        top.append(Gtk.Box(hexpand=True))
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START)
        clock_box.add_css_class("glass")
        self.clock = Gtk.Label(xalign=1)
        self.clock.add_css_class("clock")
        self.date = Gtk.Label(xalign=1)
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

        self.pin = Gtk.PasswordEntry(placeholder_text="PIN-kode", show_peek_icon=False)
        self.pin.connect("activate", lambda *_: self.login())
        self.login_button = Gtk.Button(label="Logg inn")
        self.login_button.add_css_class("primary")
        self.login_button.connect("clicked", lambda *_: self.login())
        panel.append(self.pin)
        panel.append(self.login_button)

        self.message = Gtk.Label(xalign=0, wrap=True, max_width_chars=40, width_chars=40)
        self.message.add_css_class("error")
        panel.append(self.message)

        panel.append(Gtk.Separator())
        self.emergency_button = Gtk.Button(label="Nødtilgang")
        self.emergency_button.add_css_class("emergency")
        self.emergency_button.connect("clicked", lambda *_: self.show_emergency(True))
        panel.append(self.emergency_button)

        self.emergency = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, visible=False)
        self.emergency.add_css_class("emergency-box")
        # Fixed line breaks: wrapping labels can stretch the panel when the screen is short.
        info = Gtk.Label(xalign=0, label=(
            f"Kun kritisk informasjon i {EMERGENCY_MINUTES} minutter.\n"
            "Tilgangen logges med ditt navn, kontrolleres\n"
            "i etterkant, og pasienten blir varslet."))
        self.reason = Gtk.DropDown.new_from_strings(REASONS)
        self.reason_detail = Gtk.Entry(placeholder_text="Utdyp kort (valgfritt)")
        go = Gtk.Button(label="Start nødtilgang")
        go.add_css_class("emergency-go")
        go.connect("clicked", lambda *_: self.start_emergency())
        cancel = Gtk.Button(label="Avbryt")
        cancel.connect("clicked", lambda *_: self.show_emergency(False))
        buttons = Gtk.Box(spacing=8, homogeneous=True)
        buttons.append(cancel)
        buttons.append(go)
        for widget in (info, self.reason, self.reason_detail, buttons):
            self.emergency.append(widget)
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
        sim_label = Gtk.Label(label="Simulert kortleser", xalign=0)
        sim_label.add_css_class("sim-text")
        sim_text.append(sim_title)
        sim_text.append(sim_label)
        self.sim.append(sim_text)
        self.sim_cards = self.auth.cards() if self.auth.status().get("simulert") else []
        self.sim_choice = Gtk.DropDown.new_from_strings([f"{c['navn']} – {c['rolle']}" for c in self.sim_cards] or ["–"])
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
        self.sim.append(self.sim_choice)
        self.sim.append(self.card_toggle)
        self.sim.set_visible(bool(self.sim_cards))
        bottom.append(self.sim)
        bottom.append(Gtk.Box(hexpand=True))
        for label, icon, action in (("Start på nytt", "icons/omstart.svg", self.lightdm.restart),
                                    ("Slå av", "icons/slaa-av.svg", self.lightdm.shutdown)):
            button = Gtk.Button(valign=Gtk.Align.CENTER, tooltip_text=label)
            button.update_property([Gtk.AccessibleProperty.LABEL], [label])
            button.add_css_class("power")
            button.set_child(picture(icon, 22))
            button.connect("clicked", lambda _b, a=action: a())
            bottom.append(button)
        root.append(bottom)

        self.refresh()
        self.tick()
        GLib.timeout_add(1000, self.refresh)
        GLib.timeout_add(1000, self.tick)

    def tick(self):
        now = datetime.now()
        self.clock.set_text(now.strftime("%H:%M"))
        self.date.set_text(f"{DAYS[now.weekday()]} {now.day}. {MONTHS[now.month - 1]}")
        return True

    def refresh(self):
        try:
            card = self.auth.status()["kort"]
        except Exception:
            card = None
            self.subtitle.set_text("Får ikke kontakt med innloggingstjenesten.")
        card_id = card["card_id"] if card else None
        if card_id != self.card_id:
            self.card_id = card_id
            self.card = card
            self.pin.set_text("")
            self.message.set_text("")
            self.show_emergency(False)
            self.badge.set_visible_child_name("person" if card else "kort")
            self.toggle_icon.set_visible_child_name("ut" if card else "inn")
            self.toggle_label.set_text("Ta ut kort" if card else "Sett inn kort")
            self.sim_choice.set_sensitive(card is None)
            if card:
                self.title.set_text(f"Hei, {card['navn']}")
                self.subtitle.set_text(f"{card['rolle']} · {card['virksomhet']}")
                self.pin.grab_focus()
            else:
                self.title.set_text("Sett inn helsepersonellkortet")
                self.subtitle.set_text("Kortleseren står ved siden av skjermen.")
        for widget in (self.pin, self.login_button, self.emergency_button):
            widget.set_sensitive(card is not None and not self.busy)
        return True

    def show_emergency(self, visible):
        self.emergency.set_visible(visible)
        for widget in (self.emergency_button, self.pin, self.login_button):
            widget.set_visible(not visible)

    def set_busy(self, busy):
        self.busy = busy
        self.refresh()

    def finished(self, ok, message):
        self.set_busy(False)
        if not ok:
            self.message.set_text(message)
            self.pin.set_text("")
        return False

    def login(self):
        if not self.card or self.busy:
            return
        self.message.set_text("")
        self.set_busy(True)
        self.lightdm.login(self.card["username"], self.pin.get_text(), "xfce", self.finished)

    def start_emergency(self):
        if not self.card or self.busy:
            return
        reason = REASONS[self.reason.get_selected()]
        detail = self.reason_detail.get_text().strip()
        if detail:
            reason = f"{reason}: {detail}"
        self.set_busy(True)
        self.lightdm.login(EMERGENCY_USER, reason, "medicus-nod", self.finished)

    def sim_toggle(self):
        if self.card:
            self.auth.remove()
        elif self.sim_cards:
            self.auth.insert(self.sim_cards[self.sim_choice.get_selected()]["card_id"])
        self.refresh()


class GreeterApp(Gtk.Application):
    def __init__(self, demo):
        super().__init__(application_id="no.medicus.Greeter")
        self.demo = demo

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.demo:
            demo = DemoBackend()
            auth, lightdm = demo, demo
        else:
            auth, lightdm = AuthdBackend(), LightDMBackend()
        self.window = LoginWindow(self, auth, lightdm)
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
