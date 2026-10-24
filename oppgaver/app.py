"""GTK 4 window: running programs, and closing them. Two versions of the same window:

- Oppgavebehandling (IT mode, medicus-oppgaver): every program on the PC. Closing goes through
  `sudo medicus-oppgaver stopp`, which asks for the IT card PIN and checks and logs everything itself
  (oppgaver/__main__.py); this window only asks.
- Lukk program som henger (health personnel, medicus-lukk-program, Ctrl+Shift+Esc): only the user's
  own work programs (prosesser.user_may_close). No PIN: it is their own program and they are logged
  in with their card. Each close is logged by the Medicus service.

IT mode also has Tjenester: the services in oppgaver/tjenester.py, with "Start på nytt" for the ones
that may be restarted (`sudo medicus-oppgaver omstart`, PIN as above).

The lists update every 3 seconds.
"""

import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import __main__ as helper  # noqa: E402
from . import prosesser, tjenester  # noqa: E402
from .sprak import _  # noqa: E402

APP_ID = "no.medicus.Oppgaver"
PERSONAL_APP_ID = "no.medicus.LukkProgram"
COMMAND = "/usr/local/bin/medicus-oppgaver"
REFRESH_MS = 3000
# Exit codes from `medicus-oppgaver stopp` and `omstart` (and 1 from sudo when the PIN is wrong).
WRONG_PIN, PROTECTED, GONE, STILL_RUNNING, FAILED = 1, 3, 4, 5, 6

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
PERSONAL_COLUMNS = ((_("Program"), 34), (_("Status"), 18), (_("CPU"), 7), (_("Minne"), 9))


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


def run_restart(unit: str, pin: str) -> int:
    """Ask the root helper to restart a service. Returns its exit code (1: wrong PIN)."""
    try:
        return subprocess.run(["sudo", "-S", "-p", "", COMMAND, "omstart", unit], input=pin + "\n",
                              capture_output=True, text=True, timeout=120).returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


def restart_text(code: int, service) -> tuple[str, bool]:
    """The message for an `omstart` exit code, and whether it is an error."""
    name = _(service.name)
    if code == 0:
        return _("{} er startet på nytt.").format(name), False
    if code == WRONG_PIN:
        return _("Feil PIN, eller IT-kortet er sperret."), True
    if code == PROTECTED:
        return _("Denne tjenesten er beskyttet og kan ikke startes på nytt her."), True
    if code == FAILED:
        return _("{} startet ikke. Se loggen i terminalen: journalctl -u {}").format(name, service.unit), True
    return _("Noe gikk galt: {}").format(code), True


def _cell(text: str, width: int, right=False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=1 if right else 0, width_chars=width, max_width_chars=width)
    label.set_ellipsize(3)  # Pango.EllipsizeMode.END
    return label


class ConfirmWindow(Gtk.Window):
    """Close or force close one program: confirmed with the IT card PIN, or (personal) with a click."""

    def __init__(self, parent, p, force: bool, done, personal=False):
        super().__init__(transient_for=parent, modal=True,
                         title=_("Lukk program som henger") if personal else _("Oppgavebehandling"))
        self.p, self.force, self.done, self.personal = p, force, done, personal
        self.set_default_size(440, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=18, margin_bottom=18,
                      margin_start=18, margin_end=18)
        heading = _("Tvinge {} til å avslutte?") if force else _("Avslutte {}?")
        title = Gtk.Label(label=heading.format(_(p.name)), xalign=0, wrap=True)
        title.add_css_class("title")
        box.append(title)
        if not personal:
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
        self.pin = Gtk.PasswordEntry(show_peek_icon=False)
        self.pin.connect("activate", self.confirm)
        if not personal:
            box.append(Gtk.Label(label=_("Bekreft med PIN for IT-kortet"), xalign=0))
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
        (self.ok if personal else self.pin).grab_focus()

    def confirm(self, *_args):
        pin = self.pin.get_text()
        if not pin and not self.personal:
            return
        self.pin.set_text("")
        self.ok.set_sensitive(False)
        self.message.set_text(_("Lukker …") if self.personal else _("Stopper …"))
        if self.personal:
            work = lambda: helper.close_own(self.p.pid, self.p.start, self.force)  # noqa: E731
        else:
            work = lambda: run_stop(self.p, self.force, pin)  # noqa: E731
        threading.Thread(target=lambda: GLib.idle_add(self.finished, work()), daemon=True).start()

    def finished(self, code: int):
        if code == WRONG_PIN and not self.personal:
            self.message.set_text(result_text(code, _(self.p.name))[0])
            self.ok.set_sensitive(True)
            self.pin.grab_focus()
            return False
        self.done(*result_text(code, _(self.p.name)))
        self.close()
        return False


class ServicesWindow(Gtk.Window):
    """IT mode: the services in oppgaver/tjenester.py, and restarting one with the IT card PIN."""

    def __init__(self, parent, read=tjenester.read):
        super().__init__(transient_for=parent, title=_("Tjenester"))
        self.read = read
        self.busy = self.filling = False
        self.set_default_size(620, 560)
        self.add_css_class("oppgaver")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16)
        title = Gtk.Label(label=_("Tjenester"), xalign=0)
        title.add_css_class("title")
        box.append(title)
        sub = Gtk.Label(label=_("Start en tjeneste som henger på nytt. Bekreftes med PIN for IT-kortet og skrives "
                                "i revisjonsloggen. Sikkerhetstjenestene kan ikke startes på nytt herfra."),
                        xalign=0, wrap=True)
        sub.add_css_class("subtitle")
        box.append(sub)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("procs")
        self.list.connect("row-selected", self.on_select)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.list)
        box.append(scroll)
        self.detail = Gtk.Label(label=_("Velg en tjeneste i listen."), xalign=0, wrap=True)
        self.detail.add_css_class("detail")
        box.append(self.detail)
        box.append(Gtk.Label(label=_("Bekreft med PIN for IT-kortet"), xalign=0))
        self.pin = Gtk.PasswordEntry(show_peek_icon=False)
        self.pin.connect("activate", self.confirm)
        box.append(self.pin)
        self.notice = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.notice.add_css_class("notice")
        box.append(self.notice)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        close = Gtk.Button(label=_("Lukk"))
        close.connect("clicked", lambda *_: self.close())
        self.restart = Gtk.Button(label=_("Start på nytt"), sensitive=False)
        self.restart.add_css_class("suggested-action")
        self.restart.connect("clicked", self.confirm)
        buttons.append(close)
        buttons.append(self.restart)
        box.append(buttons)
        self.set_child(box)
        self.refresh()
        self.timer = GLib.timeout_add(REFRESH_MS, self.refresh)
        self.connect("close-request", lambda *_: GLib.source_remove(self.timer) and False)

    def refresh(self):
        if self.busy:
            return True
        selected = self.list.get_selected_row()
        keep = selected.service.unit if selected else None
        self.filling = True  # as in OppgaverWindow.fill: no button flicker while the rows are rebuilt
        self.list.remove_all()
        for s in self.read():
            row = Gtk.ListBoxRow()
            row.service = s
            line = Gtk.Box(spacing=0)
            icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic" if s.locked else "system-run-symbolic")
            icon.set_size_request(24, -1)
            line.append(icon)
            line.append(_cell(_(s.name), 30))
            line.append(_cell(_(s.status), 16))
            if s.locked:
                line.add_css_class("locked")
            row.set_child(line)
            self.list.append(row)
            if s.unit == keep:
                self.list.select_row(row)
        self.filling = False
        self.on_select(self.list, self.list.get_selected_row())
        return True

    def on_select(self, _list, row):
        if self.filling:
            return
        s = row.service if row else None
        self.restart.set_sensitive(bool(s) and not s.locked and not self.busy)
        if not s:
            self.detail.set_text(_("Velg en tjeneste i listen."))
        else:
            text = f"{_(s.name)} · {s.unit} · {_(s.status)}"
            self.detail.set_text(f"{text}\n{_('Beskyttet')}: {_(s.locked)}" if s.locked else text)

    def confirm(self, *_args):
        row = self.list.get_selected_row()
        pin = self.pin.get_text()
        if not row or row.service.locked or not pin or self.busy:
            return
        service = row.service
        self.pin.set_text("")
        self.busy = True
        self.restart.set_sensitive(False)
        self.show(_("Starter {} på nytt …").format(_(service.name)), False)
        threading.Thread(target=lambda: GLib.idle_add(self.finished, service, run_restart(service.unit, pin)),
                         daemon=True).start()

    def finished(self, service, code: int):
        self.busy = False
        self.show(*restart_text(code, service))
        self.refresh()
        return False

    def show(self, text: str, error: bool):
        self.notice.set_text(text)
        (self.notice.add_css_class if error else self.notice.remove_css_class)("error")
        self.notice.set_visible(True)


class OppgaverWindow(Gtk.ApplicationWindow):
    def __init__(self, app, personal=False):
        name = _("Lukk program som henger") if personal else _("Oppgavebehandling")
        super().__init__(application=app, title=name)
        self.personal = personal
        self.columns = PERSONAL_COLUMNS if personal else COLUMNS
        self.filling = False
        self.add_css_class("oppgaver")
        self.set_icon_name("process-stop" if personal else "utilities-system-monitor")
        self.set_default_size(720 if personal else 900, 520 if personal else 640)
        self.snapshot = prosesser.Snapshot()
        self.procs = []
        self.selected = None  # (pid, start)
        self.dialog_open = False
        self.pointer_on_list = False
        self.order: list[tuple[int, int]] = []  # (pid, start) as last shown

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=16, margin_bottom=16,
                       margin_start=16, margin_end=16)
        title = Gtk.Label(label=name, xalign=0)
        title.add_css_class("title")
        root.append(title)
        about = (_("Her ser du bare programmene du jobber i. Lukk et program som har hengt seg opp. Utkast i "
                   "journalen lagres automatisk.") if personal else
                 _("IT-modus. Å stoppe et program bekreftes med PIN for IT-kortet og skrives i revisjonsloggen."))
        sub = Gtk.Label(label=about, xalign=0, wrap=True)
        sub.add_css_class("subtitle")
        root.append(sub)

        bar = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text=_("Søk etter program") if personal else
                                      _("Søk etter program, bruker eller PID"), hexpand=True)
        self.search.connect("search-changed", lambda *_: self.fill())
        bar.append(self.search)
        self.sort = Gtk.DropDown.new_from_strings([_("Sorter: CPU"), _("Sorter: minne"), _("Sorter: navn")])
        self.sort.connect("notify::selected", lambda *_: self.fill())
        bar.append(self.sort)
        if not personal:
            services = Gtk.Button(label=_("Tjenester"))
            services.connect("clicked", lambda *_: ServicesWindow(self).present())
            bar.append(services)
        root.append(bar)

        self.summary = Gtk.Label(xalign=0)
        self.summary.add_css_class("summary")
        root.append(self.summary)

        head = Gtk.Box(spacing=0)
        head.append(Gtk.Box(width_request=24))
        for i, (column, width) in enumerate(self.columns):
            cell = _cell(column, width, right=i >= len(self.columns) - 2)
            cell.add_css_class("head")
            head.append(cell)
        root.append(head)

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("procs")
        self.list.connect("row-selected", self.on_select)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.list)
        # While the pointer is over the list, the figures update but the rows stay where they are,
        # so a row can't move under the pointer just as you click it.
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: setattr(self, "pointer_on_list", True))
        motion.connect("leave", lambda *_: setattr(self, "pointer_on_list", False))
        scroll.add_controller(motion)
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
            everything = [p for p in self.snapshot.read() if not p.kernel]
            if self.personal:
                uid = os.getuid()
                self.procs = [p for p in everything if prosesser.user_may_close(p, uid)]
                self.summary.set_text(_("1 program åpent") if len(self.procs) == 1
                                      else _("{} programmer åpne").format(len(self.procs)))
            else:
                self.procs = everything
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
        if self.pointer_on_list and self.order:
            where = {key: i for i, key in enumerate(self.order)}
            return sorted(shown, key=lambda p: where.get((p.pid, p.start), len(where)))  # new ones last
        order = self.sort.get_selected()
        key = ((lambda p: (-p.cpu, -p.rss)), (lambda p: -p.rss), (lambda p: _(p.name).lower()))[order]
        return sorted(shown, key=key)

    def fill(self):
        # While the list is rebuilt, the selection briefly disappears; on_select ignores that, so the
        # buttons don't flicker off and on (a click landing just then would be lost).
        keep = self.selected
        self.filling = True
        self.list.remove_all()
        shown = self.visible()
        self.order = [(p.pid, p.start) for p in shown]
        for p in shown:
            locked = prosesser.protected(p)
            row = Gtk.ListBoxRow()
            row.proc = p
            line = Gtk.Box(spacing=0)
            icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic" if locked else "application-x-executable-symbolic")
            icon.set_size_request(24, -1)
            icon.set_tooltip_text(_("Beskyttet") if locked else None)
            line.append(icon)
            values = ((_(p.name), _(p.status), f"{p.cpu:.1f} %", size(p.rss)) if self.personal else
                      (_(p.name), str(p.pid), p.user, _(p.status), f"{p.cpu:.1f} %", size(p.rss)))
            for i, value in enumerate(values):
                line.append(_cell(value, self.columns[i][1], right=i >= len(values) - 2))
            if locked:
                line.add_css_class("locked")
            row.set_child(line)
            self.list.append(row)
            if keep == (p.pid, p.start):
                self.list.select_row(row)
        self.filling = False
        self.on_select(self.list, self.list.get_selected_row())

    def on_select(self, _list, row):
        if self.filling:
            return
        p = row.proc if row else None
        self.selected = (p.pid, p.start) if p else None
        locked = prosesser.protected(p) if p else None
        self.close_button.set_sensitive(bool(p) and not locked)
        self.force_button.set_sensitive(bool(p) and not locked)
        if not p:
            self.detail.set_text(_("Velg et program i listen."))
        else:
            text = (f"{_(p.name)} · {_(p.status)}" if self.personal else
                    f"{_(p.name)} · " + _("PID {} · bruker {} · {}").format(p.pid, p.user, _(p.status)))
            self.detail.set_text(f"{text}\n{_('Beskyttet')}: {_(locked)}" if locked else text)

    def ask(self, force: bool):
        row = self.list.get_selected_row()
        if not row or prosesser.protected(row.proc):
            return
        dialog = ConfirmWindow(self, row.proc, force, self.show_result, personal=self.personal)
        dialog.connect("close-request", self.dialog_closed)
        self.dialog_open = True  # only now: if the dialog failed, the list must keep updating
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
    def __init__(self, personal=False):
        super().__init__(application_id=PERSONAL_APP_ID if personal else APP_ID)
        self.personal = personal

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or OppgaverWindow(self, self.personal)).present()


def main(argv=None, personal=False):
    # Started as "python3 -c ...": without this the window's class (taskbar grouping) would be "-c".
    GLib.set_prgname("medicus-lukk-program" if personal else "medicus-oppgaver")
    return OppgaverApp(personal).run(argv if argv is not None else sys.argv[:1])
