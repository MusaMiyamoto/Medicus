"""The Calculator in English: same numbers, English words, a decimal point, and commas refused."""

import ast
import re
from decimal import Decimal
from pathlib import Path

import pytest

from kalkulator import klinisk, sprak, units
from kalkulator.calc import CalcError, calculate
from kalkulator.numfmt import THIN_SPACE, NumberError, format_number, parse_number

ROOT = Path(__file__).parent.parent


@pytest.fixture
def en(monkeypatch):
    monkeypatch.setenv("LANG", "en_GB.UTF-8")


def test_decimal_point_in_english(en):
    assert format_number(Decimal("1234.5")) == f"1{THIN_SPACE}234.5"
    assert parse_number("1.5") == Decimal("1.5")
    assert calculate("2.5 × 4") == 10


def test_a_comma_is_refused_in_english_not_guessed(en):
    """'1,500' is 1500 to an English reader and 1.5 to a Norwegian one: never pick silently."""
    with pytest.raises(NumberError, match="decimal sign"):
        parse_number("1,500")
    with pytest.raises(CalcError, match="decimal sign"):
        calculate("1,5 + 1")


def test_norwegian_keeps_the_comma(monkeypatch):
    monkeypatch.setenv("LANG", "nb_NO.UTF-8")
    assert format_number(Decimal("1234.5")) == f"1{THIN_SPACE}234,5"
    assert parse_number("1,5") == Decimal("1.5")
    with pytest.raises(CalcError, match="dele på null"):
        calculate("1 ÷ 0")


def test_errors_in_english(en):
    with pytest.raises(CalcError, match="Cannot divide by zero"):
        calculate("1 ÷ 0")
    with pytest.raises(units.AmountError, match="negative"):
        units.check_amount(Decimal(-1))
    with pytest.raises(klinisk.ScoreError, match="Weight \\(kg\\) must be between 2 and 400"):
        klinisk.bmi(1, 170)


def test_every_word_the_window_shows_has_english():
    """Lists, results and labels in klinisk.py and units.py are translated when shown."""
    shown = [name for _, name in klinisk.BMI_CLASSES] + [name for _, name in klinisk.GFR_STAGES]
    shown += klinisk.GCS_EYES + klinisk.GCS_VERBAL + klinisk.GCS_MOTOR + list(klinisk.SOURCES.values())
    shown += [u.name for u in units.VOLUME + units.MASS if u.name not in ("milligram", "gram", "kilogram")]
    shown += [s.name for s in units.SUBSTANCES] + [klinisk.DECISION_SUPPORT]
    shown += ["Lett (13–15)", "Lav risiko (0–1)", "Høy klinisk risiko (7 eller mer): akutt vurdering",
              "Markert forlenget (≥ 500 ms)", "Respirasjonsfrekvens", "Oksygentilførsel", "Bevissthet"]
    for text in shown:
        assert text in sprak.EN, text


def test_every_string_in_the_window_is_translated():
    """Each Norwegian string literal passed to _() in app.py has an English entry."""
    source = (ROOT / "kalkulator/app.py").read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("_", "example")
             and node.args and isinstance(node.args[0], ast.Constant)]
    assert len(calls) > 30
    for call in calls:
        text = call.args[0].value
        if call.func.id == "example" and text.startswith("For eksempel "):
            continue
        assert text in sprak.EN, text
    # Labels handed to number_entry / choice / heading / section are translated inside them.
    for label in re.findall(r'(?:number_entry|choice)\(grid, \d, "([^"]+)"', source):
        assert label in sprak.EN or label in ("QT (ms)",), label
