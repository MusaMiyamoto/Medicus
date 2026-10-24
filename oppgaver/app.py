"""GTK 4 window: running programs, and closing them with the IT card PIN.

The list updates every 3 seconds. Closing goes through `sudo medicus-oppgaver stopp`, which asks for
the PIN and checks and logs everything itself (oppgaver/__main__.py); this window only asks.
"""

import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import prosesser  # noqa: E402
from .sprak import _  # noqa: E402

APP_ID = "no.medicus.Oppgaver"
COMMAND = "/usr/local/bin/medicus-oppgaver"
REFRESH_MS = 3000
# Exit codes from `medicus-oppgaver stopp` (and 1 from sudo when the PIN is wrong).
WRONG_PIN, PROTECTED, GONE, STILL_RUNNING = 1, 3, 4, 5

CSS = """
window.oppgaver { background: #f6f4ef; color: #2a2418; }
.title { font-size: 20px; font-weight: 800; color: #8a5a00; }
.subtitle { font-size: 12px; color: #6b604c; }
.summary { font-size: 12px; color: #6b604c; }
.head { font-weight: bold; color: #6b604c; font-size: 12px; padding: 4px 8px; }
list.procs { background: #ffffff; border: 1px solid #e3dccd; border-radius: 10px; }
list.procs row { padding: 4px 8px; }
list.procs row:selected { background: #fbe7bf; color: #2a2418; }
.locked { color: #8a8170; }
.detail { font-size: 13px; }
.warning { color: #a33a00; font-weight: bold; }
.notice { padding: 8px 12px; border-radius: 8px; background: #eef5f0; color: #0b6b30; }
.notice.error { background: #fde8e4; color: #a33a00; }
button { border-radius: 10px; min-height: 36px; }
"""

COLUMNS = ((_("Program"), 26), (_("PID"), 7), (_("Bruker"), 12), (_("Status"), 16), (_("CPU"), 7),
           (_("Minne"), 9))


def size(n: int) -> str:
    return f"{n / 2**30:.1f} GB" if n >= 2**30 else f"{n // 2**20} MB"


def run_stop(p, force: bool, pin: str) -> int:
    """Ask the root helper to stop the program. Returns its exit code (1: wrong PIN)."""
    cmd = ["sudo", "-S", "-p", "", COMMAND, "stopp", str(p.pid), str(p.start)] + (["--tving"] if force else [])
    try:
        return subprocess.run(cmd, input=pin + "\n", capture_output=True, text=True, timeout=60).returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


def result_text(code: int, name: str) -> tuple[str, bool]:
    """The message for a helper exit code, and whether it is an error."""
    if code == 0:
        return _("{} er avsluttet.").format(name), False
    if code == WRONG_PIN:
        return _("Feil PIN, eller IT-kortet er sperret."), True
    if code == PROTECTED:
        return _("Dette programmet er beskyttet og kan ikke stoppes her."), True
    if code == GONE:
        return _("Programmet var allerede avsluttet."), False
    if code == STILL_RUNNING:
        return _("{} svarer ikke. Prøv «Tving avslutning».").format(name), True
    return _("Noe gikk galt: {}").format(code), True


def _cell(text: str, width: int, right=False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=1 if right else 0, width_chars=width, max_width_chars=width)
    label.set_ellipsize(3)  # Pango.EllipsizeMode.END
    return label


class ConfirmWindow(Gtk.Window):
    """Close or force close one program, confirmed with the IT card PIN."""

    def __init__(self, parent, p, force: bool, done):
        super().__init__(transient_for=parent, modal=True, title=_("Oppgavebehandling"))
        self.p, self.force, self.done = p, force, done
        self.set_default_size(440, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=18, margin_bottom=18,
                      margin_start=18, margin_end=18)
        heading = _("Tvinge {} til å avslutte?") if force else _("Avslutte {}?")
        title = Gtk.Label(label=heading.format(_(p.name)), xalign=0, wrap=True)
        title.add_css_class("title")
        box.append(title)
        box.append(Gtk.Label(label=_("PID {} · bruker {} · {}").format(p.pid, p.user, _(p.status)), xalign=0))
        what = (_("Programmet stoppes med en gang. Alt som ikke er lagret, går tapt.") if force else
                _("Programmet blir bedt om å lukke, slik at det kan lagre først."))
        box.append(Gtk.Label(label=what, xalign=0, wrap=True))
        if p.holds_patient_work:
            warn = Gtk.Label(label=_("Dette programmet kan ha journalnotater som ikke er lagret. Utkast lagres "
                                     "automatisk, men det siste du skrev kan gå tapt."), xalign=0, wrap=True)
            warn.add_css_class("warning")
            box.append(warn)
        if p.uid != os.getuid():
            box.append(Gtk.Label(label=_("Programmet tilhører en annen bruker ({}).").format(p.user), xalign=0))
        box.append(Gtk.Label(label=_("Bekreft med PIN for IT-kortet"), xalign=0))
        self.pin = Gtk.PasswordEntry(show_peek_icon=False)
        self.pin.set_input_purpose(Gtk.InputPurpose.PIN)
        self.pin.connect("activate", self.confirm)
        box.append(self.pin)
        self.message = Gtk.Label(xalign=0, wrap=True)
        self.message.add_css_class("warning")
        box.append(self.message)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label=_("Avbryt"))
        cancel.connect("clicked", lambda *_: self.close())
        self.ok = Gtk.Button(label=_("Tving avslutning") if force else _("Avslutt"))
        self.ok.add_css_class("destructive-action" if force else "suggested-action")
        self.ok.connect("clicked", self.confirm)
        buttons.append(cancel)
        buttons.append(self.ok)
        box.append(buttons)
        self.set_child(box)
        self.pin.grab_focus()

    def confirm(self, *_args):
        pin = self.pin.get_text()
        if not pin:
            return
        self.pin.set_text("")
        self.ok.set_sensitive(False)
        self.message.set_text(_("Stopper …"))
        threading.Thread(target=lambda: GLib.idle_add(self.finished, run_stop(self.p, self.force, pin)),
                         daemon=True).start()

    def finished(self, code: int):
        if code == WRONG_PIN:
            self.message.set_text(result_text(code, _(self.p.name))[0])
            self.ok.set_sensitive(True)
            self.pin.grab_focus()
            return False
        self.done(*result_text(code, _(self.p.name)))
        self.close()
        return False


class OppgaverWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Oppgavebehandling"))
        self.add_css_class("oppgaver")
        self.set_icon_name("utilities-system-monitor")
        self.set_default_size(900, 640)
        self.snapshot = prosesser.Snapshot()
        self.procs = []
        self.selected = None  # (pid, start)
        self.dialog_open = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=16, margin_bottom=16,
                       margin_start=16, margin_end=16)
        title = Gtk.Label(label=_("Oppgavebehandling"), xalign=0)
        title.add_css_class("title")
        root.append(title)
        sub = Gtk.Label(label=_("IT-modus. Å stoppe et program bekreftes med PIN for IT-kortet og skrives i "
                                "revisjonsloggen."), xalign=0, wrap=True)
        sub.add_css_class("subtitle")
        root.append(sub)

        bar = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text=_("Søk etter program, bruker eller PID"), hexpand=True)
        self.search.connect("search-changed", lambda *_: self.fill())
        bar.append(self.search)
        self.sort = Gtk.DropDown.new_from_strings([_("Sorter: CPU"), _("Sorter: minne"), _("Sorter: navn")])
        self.sort.connect("notify::selected", lambda *_: self.fill())
        bar.append(self.sort)
        root.append(bar)

        self.summary = Gtk.Label(xalign=0)
        self.summary.add_css_class("summary")
        root.append(self.summary)

        head = Gtk.Box(spacing=0)
        head.append(Gtk.Box(width_request=24))
        for i, (name, width) in enumerate(COLUMNS):
            cell = _cell(name, width, right=i >= 4)
            cell.add_css_class("head")
            head.append(cell)
        root.append(head)

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("procs")
        self.list.connect("row-selected", self.on_select)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.list)
        root.append(scroll)

        self.detail = Gtk.Label(label=_("Velg et program i listen."), xalign=0, wrap=True)
        self.detail.add_css_class("detail")
        root.append(self.detail)
        self.notice = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.notice.add_css_class("notice")
        root.append(self.notice)

        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.close_button = Gtk.Button(label=_("Avslutt"), sensitive=False)
        self.close_button.connect("clicked", lambda *_: self.ask(force=False))
        self.force_button = Gtk.Button(label=_("Tving avslutning"), sensitive=False)
        self.force_button.add_css_class("destructive-action")
        self.force_button.connect("clicked", lambda *_: self.ask(force=True))
        buttons.append(self.close_button)
        buttons.append(self.force_button)
        root.append(buttons)
        self.set_child(root)

        self.refresh()
        GLib.timeout_add(REFRESH_MS, self.refresh)

    def refresh(self):
        if not self.dialog_open:
            self.procs = [p for p in self.snapshot.read() if not p.kernel]
            used, total = prosesser.memory()
            cpu = sum(p.cpu for p in self.procs)
            self.summary.set_text(_("{} prosesser · CPU {} % · minne {} av {} brukt").format(
                len(self.procs), f"{min(cpu, 100):.0f}", size(used), size(total)))
            self.fill()
        return True

    def visible(self):
        q = self.search.get_text().strip().lower()
        shown = [p for p in self.procs
                 if not q or q in _(p.name).lower() or q in p.user.lower() or q == str(p.pid)]
        order = self.sort.get_selected()
        key = ((lambda p: (-p.cpu, -p.rss)), (lambda p: -p.rss), (lambda p: _(p.name).lower()))[order]
        return sorted(shown, key=key)

    def fill(self):
        keep = self.selected
        self.list.remove_all()
        for p in self.visible():
            locked = prosesser.protected(p)
            row = Gtk.ListBoxRow()
            row.proc = p
            line = Gtk.Box(spacing=0)
            icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic" if locked else "application-x-executable-symbolic")
            icon.set_size_request(24, -1)
            icon.set_tooltip_text(_("Beskyttet") if locked else None)
            line.append(icon)
            for i, value in enumerate((_(p.name), str(p.pid), p.user, _(p.status), f"{p.cpu:.1f} %", size(p.rss))):
                line.append(_cell(value, COLUMNS[i][1], right=i >= 4))
            if locked:
                line.add_css_class("locked")
            row.set_child(line)
            self.list.append(row)
            if keep == (p.pid, p.start):
                self.list.select_row(row)
        if keep and not self.list.get_selected_row():
            self.on_select(self.list, None)

    def on_select(self, _list, row):
        p = row.proc if row else None
        self.selected = (p.pid, p.start) if p else None
        locked = prosesser.protected(p) if p else None
        self.close_button.set_sensitive(bool(p) and not locked)
        self.force_button.set_sensitive(bool(p) and not locked)
        if not p:
            self.detail.set_text(_("Velg et program i listen."))
        else:
            text = f"{_(p.name)} · " + _("PID {} · bruker {} · {}").format(p.pid, p.user, _(p.status))
            self.detail.set_text(f"{text}\n{_('Beskyttet')}: {_(locked)}" if locked else text)

    def ask(self, force: bool):
        row = self.list.get_selected_row()
        if not row or prosesser.protected(row.proc):
            return
        self.dialog_open = True
        dialog = ConfirmWindow(self, row.proc, force, self.show_result)
        dialog.connect("close-request", self.dialog_closed)
        dialog.present()

    def dialog_closed(self, *_args):
        self.dialog_open = False
        GLib.idle_add(self.refresh_once)
        return False

    def refresh_once(self):
        self.refresh()
        return False

    def show_result(self, text: str, error: bool):
        self.notice.set_text(text)
        (self.notice.add_css_class if error else self.notice.remove_css_class)("error")
        self.notice.set_visible(True)


class OppgaverApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or OppgaverWindow(self)).present()


def main(argv=None):
    return OppgaverApp().run(argv if argv is not None else sys.argv[:1])
