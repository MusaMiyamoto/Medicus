"""Text: a plain text editor for notes and lists (GTK 4).

Medicus has its own editor so no other product's name shows in the window title.
"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import dokument  # noqa: E402

APP_ID = "no.medicus.Tekst"
ICON = "medicus-tekst"

CSS = """
.tekst-bar { padding: 4px 6px; }
.tekst-bar button { min-height: 32px; }
textview.tekst { font-size: 12pt; }
textview.tekst text { padding: 6px; }
.error { color: #b3261e; padding: 6px 0; }
"""

ACCELS = {
    "win.ny": ["<Control>n"],
    "win.apne": ["<Control>o"],
    "win.lagre": ["<Control>s"],
    "win.lagre-som": ["<Control><Shift>s"],
    "win.angre": ["<Control>z"],
    "win.gjor-om": ["<Control>y", "<Control><Shift>z"],
    "win.lukk": ["<Control>w"],
}


def documents_folder() -> Gio.File:
    folder = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or str(Path.home())
    return Gio.File.new_for_path(folder)


class TekstWindow(Gtk.ApplicationWindow):
    def __init__(self, app, path: Path | None = None):
        super().__init__(application=app)
        self.set_default_size(820, 620)
        self.set_icon_name(ICON)
        self.path = None
        self.closing = False

        self.buffer = Gtk.TextBuffer(enable_undo=True)
        self.buffer.connect("modified-changed", lambda *_: self.update_title())
        view = Gtk.TextView(buffer=self.buffer, wrap_mode=Gtk.WrapMode.WORD_CHAR, monospace=False)
        view.add_css_class("tekst")
        scroller = Gtk.ScrolledWindow(child=view, vexpand=True)

        self.message = Gtk.Label(xalign=0, wrap=True, visible=False, margin_start=10, margin_end=10)
        self.message.add_css_class("error")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.build_bar())
        box.append(Gtk.Separator())
        box.append(self.message)
        box.append(scroller)
        self.set_child(box)

        for name, handler in (("ny", self.on_new), ("apne", self.on_open), ("lagre", self.on_save),
                              ("lagre-som", self.on_save_as), ("angre", lambda *_: self.buffer.undo()),
                              ("gjor-om", lambda *_: self.buffer.redo()), ("lukk", lambda *_: self.close())):
            action = Gio.SimpleAction(name=name)
            action.connect("activate", handler)
            self.add_action(action)
        self.connect("close-request", self.on_close_request)

        if path:
            self.load(path)
        self.update_title()
        view.grab_focus()

    def build_bar(self):
        bar = Gtk.Box(spacing=4)
        bar.add_css_class("tekst-bar")
        for icon, tooltip, action in (
            ("document-new-symbolic", "Nytt dokument (Ctrl+N)", "win.ny"),
            ("document-open-symbolic", "Åpne (Ctrl+O)", "win.apne"),
            ("document-save-symbolic", "Lagre (Ctrl+S)", "win.lagre"),
            ("document-save-as-symbolic", "Lagre som (Ctrl+Shift+S)", "win.lagre-som"),
            ("edit-undo-symbolic", "Angre (Ctrl+Z)", "win.angre"),
            ("edit-redo-symbolic", "Gjør om (Ctrl+Y)", "win.gjor-om"),
        ):
            button = Gtk.Button.new_from_icon_name(icon)
            button.set_tooltip_text(tooltip)
            button.set_action_name(action)
            button.add_css_class("flat")
            bar.append(button)
        return bar

    # --- files -------------------------------------------------------------
    def load(self, path: Path):
        try:
            text = dokument.read_text(path)
        except (OSError, dokument.OpenError) as e:
            self.show_message(str(e) if isinstance(e, dokument.OpenError) else f"Kunne ikke åpne {path.name}.")
            return
        self.buffer.begin_irreversible_action()
        self.buffer.set_text(text)
        self.buffer.end_irreversible_action()
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.set_modified(False)
        self.path = path
        self.show_message("")

    def save_to(self, path: Path) -> bool:
        start, end = self.buffer.get_bounds()
        try:
            dokument.write_text(path, self.buffer.get_text(start, end, False))
        except OSError:
            self.show_message(f"Kunne ikke lagre {path.name}. Er disken full, eller mangler du tilgang?")
            return False
        self.path = path
        self.buffer.set_modified(False)
        self.show_message("")
        self.update_title()
        return True

    def show_message(self, text):
        self.message.set_text(text)
        self.message.set_visible(bool(text))

    def update_title(self):
        self.set_title(dokument.window_title(self.path, self.buffer.get_modified()))

    # --- actions -----------------------------------------------------------
    def on_new(self, *_):
        TekstWindow(self.get_application()).present()

    def on_open(self, *_):
        dialog = Gtk.FileDialog(title="Åpne", initial_folder=documents_folder())
        dialog.open(self, None, self.opened)

    def opened(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # cancelled
        path = Path(file.get_path())
        # An empty, untouched window is reused; otherwise the file gets its own window.
        if self.path is None and not self.buffer.get_modified() and self.buffer.get_char_count() == 0:
            self.load(path)
            self.update_title()
        else:
            TekstWindow(self.get_application(), path).present()

    def on_save(self, *_):
        if self.path:
            self.save_to(self.path)
        else:
            self.on_save_as()

    def on_save_as(self, *_, then_close=False):
        dialog = Gtk.FileDialog(title="Lagre som", initial_folder=documents_folder(),
                                initial_name=self.path.name if self.path else f"{dokument.UNTITLED}.txt")
        dialog.save(self, None, self.saved, then_close)

    def saved(self, dialog, result, then_close):
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if self.save_to(Path(file.get_path())) and then_close:
            self.closing = True
            self.close()

    def on_close_request(self, *_):
        if self.closing or not self.buffer.get_modified():
            return False
        name = self.path.name if self.path else dokument.UNTITLED
        alert = Gtk.AlertDialog(message=f"Vil du lagre endringene i «{name}»?",
                                detail="Endringene går tapt hvis du ikke lagrer.",
                                buttons=["Avbryt", "Ikke lagre", "Lagre"], cancel_button=0, default_button=2)
        alert.choose(self, None, self.answered)
        return True

    def answered(self, alert, result):
        try:
            choice = alert.choose_finish(result)
        except GLib.Error:
            return
        if choice == 1:
            self.closing = True
            self.close()
        elif choice == 2:
            if self.path:
                if self.save_to(self.path):
                    self.closing = True
                    self.close()
            else:
                self.on_save_as(then_close=True)


class TekstApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_application_name(dokument.APP_NAME)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        for action, keys in ACCELS.items():
            self.set_accels_for_action(action, keys)

    def do_activate(self):
        TekstWindow(self).present()

    def do_open(self, files, _n, _hint):
        for f in files:
            TekstWindow(self, Path(f.get_path()) if f.get_path() else None).present()


def main(argv=None):
    GLib.set_prgname("medicus-tekst")  # the taskbar finds name and icon by this
    return TekstApp().run(argv if argv is not None else sys.argv)
