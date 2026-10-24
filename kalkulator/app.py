"""GTK 4 window: calculator, volume, weight, weight ↔ volume and clinical scores."""

import subprocess
import sys
from decimal import Decimal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import klinisk, units  # noqa: E402
from .calc import CalcError, calculate  # noqa: E402
from .numfmt import NumberError, format_number, parse_number  # noqa: E402

APP_ID = "no.medicus.Kalkulator"

CSS = """
.result { font-size: 26px; font-weight: bold; }
.display { font-size: 24px; }
.unit-value { font-size: 18px; font-weight: bold; }
.error { color: #c0392b; }
.warning { background: #fff4d6; color: #6b4e00; padding: 10px; border-radius: 8px; }
.source { font-size: 12px; opacity: 0.8; }
.hint { opacity: 0.75; font-weight: normal; }
/* Glove-friendly: everything you tap is at least 44 px tall. */
button, entry, dropdown > button, spinbutton { min-height: 44px; }
checkbutton > check { min-width: 24px; min-height: 24px; }
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


def open_link(url: str):
    """Felleskatalogen opens in Nettleser, which allows felleskatalogen.no."""
    subprocess.Popen(["medicus-nettleser", url], start_new_session=True)


def number_entry(grid, row, label, example) -> Gtk.Entry:
    grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
    entry = Gtk.Entry(placeholder_text=example, hexpand=True)
    grid.attach(entry, 1, row, 1, 1)
    return entry


CHOOSE = "Velg …"


def choice(grid, row, label, options) -> Gtk.DropDown:
    """A dropdown that starts on "Velg …": nothing is assumed until the clinician picks."""
    grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
    dropdown = Gtk.DropDown.new_from_strings([CHOOSE, *options])
    grid.attach(dropdown, 1, row, 1, 1)
    return dropdown


def picked(dropdown) -> int | None:
    """0-based index of the chosen option, or None while it still says "Velg …"."""
    selected = dropdown.get_selected()
    return None if selected in (0, Gtk.INVALID_LIST_POSITION) else selected - 1


class Missing(Exception):
    """Something isn't filled in yet: show the hint, not an error."""


class ScorePage(Gtk.Box):
    """Shared by the clinical pages: every calculation is shown with its formula and source, and
    updates as you type. Nothing is filled in for you."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.box = page_box()
        scroller.set_child(self.box)
        self.append(scroller)
        warning = Gtk.Label(label=klinisk.DECISION_SUPPORT, xalign=0, wrap=True)
        warning.add_css_class("warning")
        self.box.append(warning)

    def section(self, title, source_key) -> Gtk.Grid:
        self.box.append(heading(title))
        source = Gtk.Label(label=klinisk.SOURCES[source_key], xalign=0, wrap=True, selectable=True)
        source.add_css_class("source")
        self.box.append(source)
        grid = Gtk.Grid(row_spacing=8, column_spacing=12)
        self.box.append(grid)
        return grid

    def result_label(self) -> Gtk.Label:
        label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        label.add_css_class("unit-value")
        self.box.append(label)
        return label

    def watch(self, *widgets):
        for widget in widgets:
            if isinstance(widget, Gtk.Entry):
                widget.connect("changed", lambda *_: self.update())
            elif isinstance(widget, Gtk.DropDown):
                widget.connect("notify::selected", lambda *_: self.update())
            else:
                widget.connect("toggled", lambda *_: self.update())

    @staticmethod
    def number(entry, what) -> float:
        text = entry.get_text()
        if not text.strip():
            raise Missing(f"Fyll inn {what}.")
        return float(parse_number(text))

    @staticmethod
    def chosen(dropdown, what) -> int:
        index = picked(dropdown)
        if index is None:
            raise Missing(f"Velg {what}.")
        return index

    @staticmethod
    def show(label, compute):
        """Run one calculation; show its result, what is missing, or the error, without stopping the others."""
        label.remove_css_class("error")
        label.remove_css_class("hint")
        try:
            label.set_text(compute())
        except Missing as e:
            label.set_text(str(e))
            label.add_css_class("hint")
        except (NumberError, klinisk.ScoreError) as e:
            label.set_text(f"✗ {e}")
            label.add_css_class("error")

    def update(self):
        raise NotImplementedError


def comma(value) -> str:
    return format_number(Decimal(str(value)))


class ClinicalPage(ScorePage):
    """BMI, eGFR and CHA₂DS₂-VASc, with a Felleskatalogen search."""

    RISKS = [("heart_failure", "Hjertesvikt (C)"), ("hypertension", "Hypertensjon (H)"), ("diabetes", "Diabetes (D)"),
             ("stroke_tia", "Hjerneslag, TIA eller tromboemboli (S₂, 2 poeng)"),
             ("vascular", "Karsykdom: hjerteinfarkt, perifer arteriesykdom, aortaplakk (V)")]

    def __init__(self):
        super().__init__()
        self.box.append(heading("Pasient"))
        grid = Gtk.Grid(row_spacing=8, column_spacing=12)
        self.box.append(grid)
        self.age = number_entry(grid, 0, "Alder (år)", "For eksempel 72")
        self.sex = choice(grid, 1, "Kjønn", ["Kvinne", "Mann"])
        self.box.append(Gtk.Label(label="Alder og kjønn brukes av alle skårene på denne siden.", xalign=0))

        grid = self.section("BMI", "bmi")
        self.weight = number_entry(grid, 0, "Vekt (kg)", "For eksempel 80")
        self.height = number_entry(grid, 1, "Høyde (cm)", "For eksempel 175")
        self.bmi = self.result_label()

        grid = self.section("eGFR (CKD-EPI 2021)", "egfr")
        self.creatinine = number_entry(grid, 0, "Kreatinin (µmol/L)", "For eksempel 95")
        self.egfr = self.result_label()

        self.section("CHA₂DS₂-VASc (hjerneslagrisiko ved atrieflimmer)", "cha2ds2")
        self.checks = {}
        for key, text in self.RISKS:
            self.checks[key] = Gtk.CheckButton(label=text)
            self.box.append(self.checks[key])
        # An unticked box could mean "no" or "not checked yet": the clinician confirms they went through all.
        self.reviewed = Gtk.CheckButton(label="Jeg har vurdert alle punktene over for denne pasienten")
        self.box.append(self.reviewed)
        self.stroke = self.result_label()

        self.box.append(heading("Felleskatalogen"))
        row = Gtk.Box(spacing=8)
        self.drug = Gtk.Entry(placeholder_text="Legemiddel, for eksempel apixaban", hexpand=True)
        self.drug.connect("activate", lambda *_: self.look_up())
        button = Gtk.Button(label="Slå opp")
        button.connect("clicked", lambda *_: self.look_up())
        row.append(self.drug)
        row.append(button)
        self.box.append(row)
        self.lookup_message = self.result_label()

        self.watch(self.age, self.sex, self.weight, self.height, self.creatinine, self.reviewed, *self.checks.values())
        self.update()

    def female(self) -> bool:
        return self.chosen(self.sex, "kjønn") == 0

    def update(self):
        def bmi():
            value, group = klinisk.bmi(self.number(self.weight, "vekt"), self.number(self.height, "høyde"))
            return f"BMI {comma(value)} kg/m² · {group}"

        def egfr():
            creatinine = self.number(self.creatinine, "kreatinin")
            value, stage = klinisk.egfr(creatinine, int(self.number(self.age, "alder")), self.female())
            return f"eGFR {value} ml/min/1,73 m² · {stage}"

        def stroke():
            age = int(self.number(self.age, "alder"))
            female = self.female()
            if not self.reviewed.get_active():
                raise Missing("Gå gjennom alle punktene, og kryss av for at du har vurdert dem.")
            risk = klinisk.StrokeRisk(age=age, female=female,
                                      **{key: check.get_active() for key, check in self.checks.items()})
            return (f"CHA₂DS₂-VASc {klinisk.cha2ds2_vasc(risk)} poeng · CHA₂DS₂-VA {klinisk.cha2ds2_va(risk)} poeng "
                    "(ESC 2024 bruker CHA₂DS₂-VA, uten kjønn)")

        self.show(self.bmi, bmi)
        self.show(self.egfr, egfr)
        self.show(self.stroke, stroke)

    def look_up(self):
        def url():
            open_link(klinisk.felleskatalogen(self.drug.get_text()))
            return "Åpnet i Nettleser."
        self.show(self.lookup_message, url)


class AcutePage(ScorePage):
    """NEWS2, GCS and CURB-65: for the ward and the emergency room."""

    def __init__(self):
        super().__init__()
        grid = self.section("NEWS2 (tidlig varsling ved forverring)", "news2")
        self.rr = number_entry(grid, 0, "Respirasjonsfrekvens (/min)", "For eksempel 16")
        self.spo2 = number_entry(grid, 1, "SpO₂ (%)", "For eksempel 96")
        self.scale = choice(grid, 2, "SpO₂-skala", ["Skala 1 (vanlig)", "Skala 2 (mål 88–92 %, bestemt av lege)"])
        self.air = choice(grid, 3, "Luft eller oksygen", ["Romluft", "Får oksygen"])
        self.sbp = number_entry(grid, 4, "Systolisk blodtrykk (mmHg)", "For eksempel 125")
        self.pulse = number_entry(grid, 5, "Puls (/min)", "For eksempel 80")
        self.alert = choice(grid, 6, "Bevissthet", ["Våken (A)", "Ny forvirring, reagerer bare på tiltale, smerte, "
                                                   "eller ingen respons (CVPU)"])
        self.temp = number_entry(grid, 7, "Temperatur (°C)", "For eksempel 37,2")
        self.news = self.result_label()

        grid = self.section("Glasgow Coma Scale", "gcs")
        self.eyes = choice(grid, 0, "Øyeåpning", klinisk.GCS_EYES)
        self.verbal = choice(grid, 1, "Verbal respons", klinisk.GCS_VERBAL)
        self.motor = choice(grid, 2, "Motorisk respons", klinisk.GCS_MOTOR)
        self.gcs = self.result_label()

        grid = self.section("CURB-65 (alvorlighet ved lungebetennelse)", "curb65")
        self.confusion = choice(grid, 0, "Ny forvirring", ["Nei", "Ja"])
        self.urea = number_entry(grid, 1, "Urea (mmol/L)", "For eksempel 6,5")
        self.c_rr = number_entry(grid, 2, "Respirasjonsfrekvens (/min)", "For eksempel 22")
        self.c_sbp = number_entry(grid, 3, "Systolisk blodtrykk", "For eksempel 110")
        self.c_dbp = number_entry(grid, 4, "Diastolisk blodtrykk", "For eksempel 70")
        self.c_age = number_entry(grid, 5, "Alder (år)", "For eksempel 70")
        self.curb = self.result_label()

        self.watch(self.rr, self.spo2, self.scale, self.air, self.sbp, self.pulse, self.alert, self.temp,
                   self.eyes, self.verbal, self.motor,
                   self.confusion, self.urea, self.c_rr, self.c_sbp, self.c_dbp, self.c_age)
        self.update()

    def update(self):
        def news():
            total, points, risk = klinisk.news2(
                self.number(self.rr, "respirasjonsfrekvens"), self.number(self.spo2, "SpO₂"),
                self.chosen(self.scale, "SpO₂-skala") == 1, self.chosen(self.air, "luft eller oksygen") == 1,
                self.number(self.sbp, "systolisk blodtrykk"), self.number(self.pulse, "puls"),
                self.chosen(self.alert, "bevissthet") == 0, self.number(self.temp, "temperatur"))
            details = ", ".join(f"{name} {p}" for name, p in points.items() if p)
            return f"NEWS2 {total} poeng · {risk}" + (f"\n({details})" if details else "")

        def gcs():
            total, severity = klinisk.gcs(self.chosen(self.eyes, "øyeåpning") + 1,
                                          self.chosen(self.verbal, "verbal respons") + 1,
                                          self.chosen(self.motor, "motorisk respons") + 1)
            return f"GCS {total} · {severity}"

        def curb():
            points, risk = klinisk.curb65(
                self.chosen(self.confusion, "om pasienten er forvirret") == 1, self.number(self.urea, "urea"),
                self.number(self.c_rr, "respirasjonsfrekvens"), self.number(self.c_sbp, "systolisk blodtrykk"),
                self.number(self.c_dbp, "diastolisk blodtrykk"), int(self.number(self.c_age, "alder")))
            return f"CURB-65 {points} poeng · {risk}"

        self.show(self.news, news)
        self.show(self.gcs, gcs)
        self.show(self.curb, curb)


class LabPage(ScorePage):
    """Cockcroft-Gault, corrected calcium and QTc."""

    def __init__(self):
        super().__init__()
        grid = self.section("Kreatininclearance (Cockcroft-Gault), for dosegrenser", "cg")
        self.creatinine = number_entry(grid, 0, "Kreatinin (µmol/L)", "For eksempel 110")
        self.age = number_entry(grid, 1, "Alder (år)", "For eksempel 80")
        self.weight = number_entry(grid, 2, "Vekt (kg)", "For eksempel 65")
        self.sex = choice(grid, 3, "Kjønn", ["Kvinne", "Mann"])
        self.cg = self.result_label()

        grid = self.section("Albuminkorrigert kalsium", "ca")
        self.calcium = number_entry(grid, 0, "Kalsium (mmol/L)", "For eksempel 2,15")
        self.albumin = number_entry(grid, 1, "Albumin (g/L)", "For eksempel 32")
        self.ca = self.result_label()

        grid = self.section("QTc", "qtc")
        self.qt = number_entry(grid, 0, "QT (ms)", "For eksempel 420")
        self.hr = number_entry(grid, 1, "Puls (/min)", "For eksempel 75")
        self.qtc_sex = choice(grid, 2, "Kjønn (for grenseverdien)", ["Kvinne", "Mann"])
        self.qtc = self.result_label()

        self.watch(self.creatinine, self.age, self.weight, self.sex, self.calcium, self.albumin,
                   self.qt, self.hr, self.qtc_sex)
        self.update()

    def update(self):
        def cg():
            value = klinisk.cockcroft_gault(self.number(self.creatinine, "kreatinin"),
                                            int(self.number(self.age, "alder")), self.number(self.weight, "vekt"),
                                            self.chosen(self.sex, "kjønn") == 0)
            return f"Kreatininclearance {value} ml/min (ikke justert til 1,73 m²)"

        def ca():
            value = klinisk.corrected_calcium(self.number(self.calcium, "kalsium"), self.number(self.albumin, "albumin"))
            return f"Korrigert kalsium {comma(value)} mmol/L"

        def qtc():
            bazett, fridericia = klinisk.qtc(self.number(self.qt, "QT"), self.number(self.hr, "puls"))
            index = picked(self.qtc_sex)
            female = None if index is None else index == 0
            # Judged on Fridericia, which is more accurate than Bazett at high and low heart rates.
            return (f"QTc Bazett {bazett} ms · Fridericia {fridericia} ms\n"
                    f"{klinisk.qtc_text(fridericia, female)} (vurdert med Fridericia)")

        self.show(self.cg, cg)
        self.show(self.ca, ca)
        self.show(self.qtc, qtc)


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
        self.stack.add_titled(ClinicalPage(), "klinisk", "Kliniske skårer")
        self.stack.add_titled(AcutePage(), "akutt", "Akutt: NEWS2, GCS, CURB-65")
        self.stack.add_titled(LabPage(), "lab", "Lab og EKG")

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
