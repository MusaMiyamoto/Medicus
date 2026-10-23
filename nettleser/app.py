"""Medicus Nettleser: window, toolbar and safety rules around the WebKit engine."""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402

from tilgang.ekg import Ekg  # noqa: E402

from . import regler, sider  # noqa: E402

APP_ID = "no.medicus.Nettleser"
PROXY = "http://127.0.0.1:8888"
ICON = Path(__file__).parent.parent / "branding" / "nettleser.svg"

CSS = """
.medicus-bar { background: #0f4f2f; color: #ffffff; padding: 4px 8px; }
.medicus-bar button { color: #ffffff; background: transparent; border: none; min-width: 34px; min-height: 34px; border-radius: 8px; }
.medicus-bar button:hover { background: rgba(255, 255, 255, 0.14); }
.medicus-bar button:disabled { opacity: 0.35; }
.medicus-bar entry { min-height: 34px; border-radius: 10px; background: rgba(255, 255, 255, 0.12);
                     color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.16); }
.medicus-bar entry image { color: #7fe0ad; }
"""


def make_session() -> WebKit.NetworkSession:
    """Nothing is stored on disk (no history, cookies or cache survive), trackers are limited,
    and all internet traffic goes through the Medicus web filter."""
    session = WebKit.NetworkSession.new_ephemeral()
    session.set_itp_enabled(True)
    session.set_proxy_settings(WebKit.NetworkProxyMode.CUSTOM,
                               WebKit.NetworkProxySettings.new(PROXY, ["localhost", "127.0.0.1"]))
    session.connect("download-started", on_download)
    return session


def on_download(_session, download):
    folder = Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or Path.home() / "Nedlastinger")
    folder.mkdir(parents=True, exist_ok=True)

    def decide(dl, name):
        dl.set_destination(str(folder / Path(name).name))
        return True

    download.connect("decide-destination", decide)


class BrowserWindow(Gtk.ApplicationWindow):
    def __init__(self, app, session, url, kiosk=False):
        super().__init__(application=app, title="Medicus Nettleser")
        self.set_default_size(1200, 800)
        self.set_icon_name("medicus-nettleser")
        self.kiosk = kiosk

        self.view = WebKit.WebView(network_session=session)
        settings = self.view.get_settings()
        settings.set_enable_developer_extras(False)
        settings.set_enable_media_stream(True)  # microphone for the journal assistant (asked per site)
        settings.set_javascript_can_open_windows_automatically(False)
        # Reveal as little as possible to websites: the engine's ordinary user agent with no
        # Medicus name added, no WebGL (graphics-card fingerprint) and no WebRTC (can leak the
        # machine's internal IP address).
        settings.set_user_agent(None)
        settings.set_enable_webgl(False)
        settings.set_enable_webrtc(False)
        self.view.connect("decide-policy", self.on_policy)
        self.view.connect("permission-request", self.on_permission)
        self.view.connect("load-changed", self.on_load)
        self.view.connect("load-failed", self.on_failed)
        self.view.connect("load-failed-with-tls-errors", self.on_tls_error)
        self.view.connect("notify::uri", lambda *_: self.update_bar())
        self.view.connect("notify::title", lambda *_: self.update_title())
        self.view.connect("close", lambda *_: self.close())
        self.view.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        if not kiosk:
            box.append(self.build_bar())
        box.append(self.view)
        self.set_child(box)
        if kiosk:
            self.fullscreen()
        self.view.load_uri(regler.normalize(url))

    def build_bar(self):
        bar = Gtk.Box(spacing=4)
        bar.add_css_class("medicus-bar")
        self.back = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.back.set_tooltip_text("Tilbake")
        self.back.connect("clicked", lambda *_: self.view.go_back())
        self.forward = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self.forward.set_tooltip_text("Fremover")
        self.forward.connect("clicked", lambda *_: self.view.go_forward())
        reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        reload.set_tooltip_text("Last inn på nytt")
        reload.connect("clicked", lambda *_: self.view.reload())
        home = Gtk.Button.new_from_icon_name("go-home-symbolic")
        home.set_tooltip_text("Godkjente nettsteder")
        home.connect("clicked", lambda *_: self.view.load_uri(regler.HOME))
        self.address = Gtk.Entry(hexpand=True)
        self.address.connect("activate", lambda e: self.view.load_uri(regler.normalize(e.get_text())))
        # The Medicus heartbeat instead of a spinner, while a page loads.
        self.loading = Ekg(width=90, height=26)
        self.loading.set_visible(False)
        for widget in (self.back, self.forward, reload, home, self.address, self.loading):
            bar.append(widget)
        return bar

    # --- rules -------------------------------------------------------------
    def on_policy(self, _view, decision, kind):
        if kind in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            url = decision.get_navigation_action().get_request().get_uri()
            if not regler.is_allowed(url):
                decision.ignore()
                self.view.load_alternate_html(sider.blocked(url), url, None)
                return True
            if kind == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
                decision.ignore()
                self.view.load_uri(url)  # open in the same window
                return True
        elif kind == WebKit.PolicyDecisionType.RESPONSE and not decision.is_mime_type_supported():
            decision.download()
            return True
        return False

    def on_permission(self, _view, request):
        # Only the Medicus apps on this machine may use the microphone; nothing else is granted.
        if isinstance(request, WebKit.UserMediaPermissionRequest) and regler.is_medicus_app(self.view.get_uri() or ""):
            request.allow()
        else:
            request.deny()
        return True

    def on_load(self, _view, event):
        if self.kiosk:
            return
        self.loading.set_visible(event != WebKit.LoadEvent.FINISHED)
        self.update_bar()

    def on_failed(self, _view, _event, url, error):
        if error.matches(WebKit.NetworkError.quark(), WebKit.NetworkError.CANCELLED):
            return False
        self.view.load_alternate_html(sider.failed(url, error.message), url, None)
        return True

    def on_tls_error(self, _view, url, _certificate, _errors):
        self.view.load_alternate_html(sider.insecure(url), url, None)
        return True

    # --- toolbar -------------------------------------------------------------
    def update_bar(self):
        if self.kiosk:
            return
        uri = self.view.get_uri() or ""
        if not self.address.has_focus():
            self.address.set_text(uri)
        secure = uri.startswith("https://") or regler.is_medicus_app(uri) or uri.startswith("http://127.0.0.1")
        self.address.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                             "channel-secure-symbolic" if secure else "channel-insecure-symbolic")
        self.back.set_sensitive(self.view.can_go_back())
        self.forward.set_sensitive(self.view.can_go_forward())

    def update_title(self):
        title = self.view.get_title()
        self.set_title(f"{title} – Medicus Nettleser" if title else "Medicus Nettleser")


class BrowserApp(Gtk.Application):
    def __init__(self, kiosk=False):
        flags = Gio.ApplicationFlags.HANDLES_OPEN
        if kiosk:
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=APP_ID, flags=flags)
        self.kiosk = kiosk
        self.session = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_application_name("Medicus Nettleser")
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        from gi.repository import Gdk

        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.session = make_session()

    def do_activate(self):
        BrowserWindow(self, self.session, regler.HOME, self.kiosk).present()

    def do_open(self, files, _n, _hint):
        for f in files:
            BrowserWindow(self, self.session, f.get_uri(), self.kiosk).present()


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    kiosk = "--kiosk" in argv
    if kiosk:
        argv.remove("--kiosk")
    return BrowserApp(kiosk).run(argv)
