"""GTK 4 window: calculator, volume, weight and weight ↔ volume."""

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import units  # noqa: E402
from .calc import CalcError, calculate  # noqa: E402
from .numfmt import NumberError, format_number, parse_number  # noqa: E402

APP_ID = "no.medicus.Kalkulator"

CSS = """
.result { font-size: 26px; font-weight: bold; }
.display { font-size: 24px; }
.unit-value { font-size: 18px; font-weight: bold; }
.error { color: #c0392b; }
.warning { background: #fff4d6; color: #6b4e00; padding: 10px; border-radius: 8px; }
.keypad button { min-height: 48px; font-size: 18px; }
"""

DOSING_WARNING = (
    "Ikke bruk til legemiddeldosering. Bruk alltid preparatomtalen (SPC) "
    "og gjeldende rutiner.\nOmregningen gjelder bare når tettheten er riktig."
)


def page_box() -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(20)
    return box


def heading(text: str) -> Gtk.Label:
    label = Gtk.Label(xalign=0)
    label.set_markup(f"<b>{text}</b>")
    return label


class CalculatorPage(Gtk.Box):
    KEYS = [
        ["C", "⌫", "(", ")"],
        ["7", "8", "9", "÷"],
        ["4", "5", "6", "×"],
        ["1", "2", "3", "−"],
        ["0", ",", "=", "+"],
    ]

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        box = page_box()
        self.append(box)

        self.entry = Gtk.Entry(placeholder_text="For eksempel 2,5 × 4")
        self.entry.add_css_class("display")
        self.entry.connect("activate", lambda *_: self.solve())
        # Wraps, so a long error message can't make the window wider than the screen.
        self.result = Gtk.Label(xalign=1, selectable=True, wrap=True, justify=Gtk.Justification.RIGHT)
        self.result.add_css_class("result")
        box.append(self.entry)
        box.append(self.result)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6, row_homogeneous=True, column_homogeneous=True)
        grid.add_css_class("keypad")
        grid.set_vexpand(True)
        for row, keys in enumerate(self.KEYS):
            for col, key in enumerate(keys):
                button = Gtk.Button(label=key)
                if key == "=":
                    button.add_css_class("suggested-action")
                button.connect("clicked", self.on_key, key)
                grid.attach(button, col, row, 1, 1)
        box.append(grid)

    def on_key(self, _button, key):
        text = self.entry.get_text()
        if key == "C":
            self.entry.set_text("")
            self.show("", error=False)
        elif key == "⌫":
            self.entry.set_text(text[:-1])
        elif key == "=":
            self.solve()
        else:
            self.entry.set_text(text + key)
        self.entry.grab_focus()
        self.entry.set_position(-1)

    def solve(self):
        try:
            self.show("= " + format_number(calculate(self.entry.get_text())), error=False)
        except CalcError as e:
            self.show(str(e), error=True)

    def show(self, text, error):
        self.result.set_text(text)
        (self.result.add_css_class if error else self.result.remove_css_class)("error")


class UnitPage(Gtk.Box):
    """Type an amount in one unit; see it in every unit of the table at once."""

    def __init__(self, table: list[units.Unit], title: str, example: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.table = table
        box = page_box()
        self.append(box)
        box.append(heading(title))

        row = Gtk.Box(spacing=8)
        self.entry = Gtk.Entry(placeholder_text=example, hexpand=True)
        self.entry.connect("changed", lambda *_: self.update())
        self.unit = Gtk.DropDown.new_from_strings([f"{u.name} ({u.symbol})" for u in table])
        self.unit.connect("notify::selected", lambda *_: self.update())
        row.append(self.entry)
        row.append(self.unit)
        box.append(row)

        self.message = Gtk.Label(xalign=0)
        self.message.add_css_class("error")
        box.append(self.message)

        results = Gtk.Grid(row_spacing=10, column_spacing=16)
        self.values = []
        for i, unit in enumerate(table):
            value = Gtk.Label(xalign=1, selectable=True, hexpand=True)
            value.add_css_class("unit-value")
            results.attach(value, 0, i, 1, 1)
            results.attach(Gtk.Label(label=f"{unit.name} ({unit.symbol})", xalign=0), 1, i, 1, 1)
            self.values.append(value)
        box.append(results)
        self.update()

    def update(self):
        text = self.entry.get_text()
        try:
            amount = units.check_amount(parse_number(text)) if text.strip() else None
            self.message.set_text("")
        except (NumberError, units.AmountError) as e:
            amount = None
            self.message.set_text(str(e))
        source = self.table[self.unit.get_selected()]
        for label, (_, value) in zip(
            self.values, units.convert_to_all(amount or 0, source, self.table)
        ):
            label.set_text(format_number(value) if amount is not None else "–")


class DensityPage(Gtk.Box):
    """Weight ↔ volume in any units (e.g. liter → kilogram), using the substance's density.
    Type an amount in a weight or volume unit; see it in every unit of the other kind."""

    UNITS = units.MASS + units.VOLUME

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        box = page_box()
        self.append(box)
        box.append(heading("Vekt ↔ volum"))

        warning = Gtk.Label(label=DOSING_WARNING, xalign=0, wrap=True)
        warning.add_css_class("warning")
        box.append(warning)

        form = Gtk.Grid(row_spacing=10, column_spacing=12)
        amount_row = Gtk.Box(spacing=8)
        self.amount = Gtk.Entry(placeholder_text="For eksempel 250", hexpand=True)
        self.unit = Gtk.DropDown.new_from_strings([f"{u.name} ({u.symbol})" for u in self.UNITS])
        self.unit.set_selected(self.UNITS.index(units.GRAM))
        amount_row.append(self.amount)
        amount_row.append(self.unit)
        self.substance = Gtk.DropDown.new_from_strings(
            [s.name if s.density is None else f"{s.name} (ca. {format_number(s.density)} g/ml)"
             for s in units.SUBSTANCES]
        )
        self.density = Gtk.Entry(placeholder_text="g/ml, for eksempel 1,2", sensitive=False)
        for i, (label, widget) in enumerate([
            ("Mengde", amount_row),
            ("Stoff", self.substance),
            ("Tetthet (g/ml)", self.density),
        ]):
            form.attach(Gtk.Label(label=label, xalign=0), 0, i, 1, 1)
            form.attach(widget, 1, i, 1, 1)
        box.append(form)

        self.message = Gtk.Label(xalign=0, wrap=True)
        self.message.add_css_class("error")
        box.append(self.message)
        self.results = Gtk.Grid(row_spacing=10, column_spacing=16)
        box.append(self.results)
        self.detail = Gtk.Label(xalign=0, wrap=True)
        box.append(self.detail)

        for widget, signal in [
            (self.unit, "notify::selected"),
            (self.substance, "notify::selected"),
            (self.amount, "changed"),
            (self.density, "changed"),
        ]:
            widget.connect(signal, lambda *_: self.update())
        self.update()

    def show_rows(self, rows):
        while (child := self.results.get_first_child()) is not None:
            self.results.remove(child)
        for i, (unit, text) in enumerate(rows):
            value = Gtk.Label(label=text, xalign=1, selectable=True, hexpand=True)
            value.add_css_class("unit-value")
            self.results.attach(value, 0, i, 1, 1)
            self.results.attach(Gtk.Label(label=f"{unit.name} ({unit.symbol})", xalign=0), 1, i, 1, 1)

    def update(self):
        substance = units.SUBSTANCES[self.substance.get_selected()]
        self.density.set_sensitive(substance.density is None)
        source = self.UNITS[self.unit.get_selected()]
        empty = [(u, "–") for u in units.other_table(source)]
        self.message.set_text("")
        self.detail.set_text("")
        try:
            if not self.amount.get_text().strip():
                self.show_rows(empty)
                return
            amount = units.check_amount(parse_number(self.amount.get_text()))
            if substance.density is None:
                density = parse_number(self.density.get_text())
                name = "egendefinert tetthet"
            else:
                density = substance.density
                name = substance.name.lower()
            rows = units.across_to_all(amount, source, density)
        except (NumberError, units.AmountError, units.DensityError) as e:
            self.message.set_text(str(e))
            self.show_rows(empty)
            return
        self.show_rows([(u, format_number(v)) for u, v in rows])
        self.detail.set_text(f"{format_number(amount)} {source.symbol}, beregnet med tetthet "
                             f"{format_number(density)} g/ml ({name}).")


class KalkulatorWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Kalkulator")
        self.set_default_size(680, 640)
        self.set_icon_name("accessories-calculator")

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        self.stack.add_titled(CalculatorPage(), "kalkulator", "Kalkulator")
        self.stack.add_titled(UnitPage(units.VOLUME, "Volum", "For eksempel 250"), "volum", "Volum (µl – l)")
        self.stack.add_titled(UnitPage(units.MASS, "Vekt", "For eksempel 500"), "vekt", "Vekt (µg – kg)")
        self.stack.add_titled(DensityPage(), "tetthet", "Vekt ↔ volum")

        sidebar = Gtk.StackSidebar(stack=self.stack)
        sidebar.set_size_request(190, -1)
        layout = Gtk.Box()
        layout.append(sidebar)
        layout.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        layout.append(self.stack)
        self.set_child(layout)


class KalkulatorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def do_activate(self):
        window = self.get_active_window() or KalkulatorWindow(self)
        window.present()


def main(argv=None):
    GLib.set_prgname("medicus-kalkulator")  # the taskbar finds name and icon by this
    return KalkulatorApp().run(argv if argv is not None else sys.argv)
