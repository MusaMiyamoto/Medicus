from decimal import Decimal

import pytest

from kalkulator import units
from kalkulator.calc import CalcError, calculate
from kalkulator.numfmt import NumberError, format_number, parse_number


@pytest.mark.parametrize(
    "text, expected",
    [("1,5", "1.5"), ("1.5", "1.5"), (" 250 ", "250"), ("1 500", "1500"), ("1 500,25", "1500.25"), ("-2", "-2")],
)
def test_parse_number(text, expected):
    assert parse_number(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "abc", "1.000,5", "1,2,3", "inf", "nan", "1e20"])
def test_parse_number_rejects(text):
    with pytest.raises(NumberError):
        parse_number(text)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0.25", "0,25"),
        ("2.50", "2,5"),
        ("1000", "1 000"),
        ("1234567.5", "1 234 567,5"),
        ("0.000001", "0,000001"),
        ("-0.5", "−0,5"),
        ("-0.00000000001", "0"),
        ("1E+3", "1 000"),
    ],
)
def test_format_number(value, expected):
    assert format_number(Decimal(value)) == expected


def by_symbol(table, symbol):
    return next(u for u in table if u.symbol == symbol)


@pytest.mark.parametrize(
    "amount, source, target, expected",
    [
        ("250", "ml", "dl", "2.5"),
        ("250", "ml", "l", "0.25"),
        ("1.5", "l", "dl", "15"),
        ("3", "dl", "ml", "300"),
    ],
)
def test_volume(amount, source, target, expected):
    v = units.VOLUME
    assert units.convert(Decimal(amount), by_symbol(v, source), by_symbol(v, target)) == Decimal(expected)


@pytest.mark.parametrize(
    "amount, source, target, expected",
    [
        ("500", "mg", "g", "0.5"),
        ("1", "kg", "hg", "10"),
        ("2.5", "hg", "g", "250"),
        ("1", "mg", "kg", "0.000001"),
        ("0.75", "kg", "mg", "750000"),
    ],
)
def test_mass(amount, source, target, expected):
    m = units.MASS
    assert units.convert(Decimal(amount), by_symbol(m, source), by_symbol(m, target)) == Decimal(expected)


def test_convert_to_all_keeps_table_order():
    rows = units.convert_to_all(Decimal("1"), by_symbol(units.VOLUME, "l"), units.VOLUME)
    assert [u.symbol for u, _ in rows] == ["µl", "ml", "cl", "dl", "l", "ts", "ss"]
    assert [v for _, v in rows][:5] == [1000000, 1000, 100, 10, 1]


@pytest.mark.parametrize(
    "amount, source, target, expected",
    [
        ("250", "µg", "mg", "0.25"),
        ("2", "ss", "ml", "30"),
        ("10", "ml", "ts", "2"),
        ("5", "µl", "ml", "0.005"),
        ("33", "cl", "dl", "3.3"),
    ],
)
def test_small_and_spoon_units(amount, source, target, expected):
    table = units.VOLUME + units.MASS
    assert units.convert(Decimal(amount), by_symbol(table, source), by_symbol(table, target)) == Decimal(expected)


@pytest.mark.parametrize(
    "amount, source, target, density, expected",
    [
        ("1", "l", "kg", "1.00", "1"),            # 1 liter water weighs 1 kg
        ("2", "kg", "l", "1.00", "2"),
        ("450", "ml", "g", "1.06", "477"),        # blood
        ("1.06", "kg", "l", "1.06", "1"),
        ("5", "dl", "hg", "1.00", "5"),
        ("10", "mg", "µl", "1.00", "10"),
    ],
)
def test_mass_volume_in_any_units(amount, source, target, density, expected):
    table = units.VOLUME + units.MASS
    value = units.across(Decimal(amount), by_symbol(table, source), by_symbol(table, target), Decimal(density))
    assert value == Decimal(expected)


def test_across_to_all_lists_the_other_kind():
    rows = units.across_to_all(Decimal("1"), by_symbol(units.VOLUME, "l"), Decimal("1"))
    assert [u.symbol for u, _ in rows] == ["µg", "mg", "g", "hg", "kg"]


def test_across_needs_one_mass_and_one_volume():
    with pytest.raises(ValueError):
        units.across(Decimal("1"), units.ML, units.VOLUME[4], Decimal("1"))


def test_water_is_default_and_one_to_one():
    water = units.SUBSTANCES[0]
    assert water.name == "Vann"
    assert units.grams_to_ml(Decimal("250"), water.density) == Decimal("250")


def test_density_conversions():
    honey = Decimal("1.42")
    assert units.ml_to_grams(Decimal("100"), honey) == Decimal("142")
    assert units.grams_to_ml(Decimal("142"), honey) == Decimal("100")


@pytest.mark.parametrize("density", ["0", "-1", "30"])
def test_bad_density_is_rejected(density):
    with pytest.raises(units.DensityError):
        units.grams_to_ml(Decimal("10"), Decimal(density))


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2+3", "5"),
        ("2,5 × 4", "10"),
        ("10 ÷ 4", "2.5"),
        ("0,1 + 0,2", "0.3"),
        ("(1+2)×3", "9"),
        ("−3 + 1", "-2"),
        ("7 − 2 − 1", "4"),
        ("1 500 + 1", "1501"),
    ],
)
def test_calculate(expression, expected):
    assert calculate(expression) == Decimal(expected)


@pytest.mark.parametrize(
    "expression",
    ["", "2 +", "1/0", "0/0", "2**8", "__import__('os')", "abs(1)", "x", "9" * 201, "999999999999999 * 10"],
)
def test_calculate_rejects(expression):
    with pytest.raises(CalcError):
        calculate(expression)
