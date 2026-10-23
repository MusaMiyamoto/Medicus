"""Unit conversions. Decimal arithmetic, so 0,1 l is exactly 100 ml."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Unit:
    symbol: str
    name: str
    factor: Decimal  # size of one unit, in the table's base unit


# Base unit: liter. Teskje and spiseskje are the standard 5 ml and 15 ml measuring spoons
# used on medicine labels.
VOLUME = [
    Unit("µl", "mikroliter", Decimal("0.000001")),
    Unit("ml", "milliliter", Decimal("0.001")),
    Unit("cl", "centiliter", Decimal("0.01")),
    Unit("dl", "desiliter", Decimal("0.1")),
    Unit("l", "liter", Decimal("1")),
    Unit("ts", "teskje (5 ml)", Decimal("0.005")),
    Unit("ss", "spiseskje (15 ml)", Decimal("0.015")),
]

# Base unit: gram.
MASS = [
    Unit("µg", "mikrogram", Decimal("0.000001")),
    Unit("mg", "milligram", Decimal("0.001")),
    Unit("g", "gram", Decimal("1")),
    Unit("hg", "hektogram", Decimal("100")),
    Unit("kg", "kilogram", Decimal("1000")),
]

ML = VOLUME[1]
GRAM = MASS[2]


def convert(value: Decimal, source: Unit, target: Unit) -> Decimal:
    return value * source.factor / target.factor


def convert_to_all(value: Decimal, source: Unit, table: list[Unit]) -> list[tuple[Unit, Decimal]]:
    return [(unit, convert(value, source, unit)) for unit in table]


@dataclass(frozen=True)
class Substance:
    name: str
    density: Decimal | None  # g/ml; None means the user types their own


# Approximate values at room or body temperature. Water is the default.
SUBSTANCES = [
    Substance("Vann", Decimal("1.00")),
    Substance("Blod", Decimal("1.06")),
    Substance("Natriumklorid 0,9 %", Decimal("1.005")),
    Substance("Glukose 5 %", Decimal("1.02")),
    Substance("Morsmelk / melk", Decimal("1.03")),
    Substance("Etanol 70 % (desinfeksjon)", Decimal("0.885")),
    Substance("Etanol (ren sprit)", Decimal("0.789")),
    Substance("Olivenolje", Decimal("0.92")),
    Substance("Egendefinert tetthet", None),
]

MAX_DENSITY = Decimal("25")  # denser than any element; anything above is a typo


class DensityError(ValueError):
    pass


def check_density(density: Decimal) -> None:
    if density <= 0:
        raise DensityError("Tettheten må være større enn 0.")
    if density > MAX_DENSITY:
        raise DensityError("Tettheten virker urimelig høy. Sjekk tallet (g/ml).")


def grams_to_ml(grams: Decimal, density: Decimal) -> Decimal:
    check_density(density)
    return grams / density


def ml_to_grams(ml: Decimal, density: Decimal) -> Decimal:
    check_density(density)
    return ml * density


def other_table(unit: Unit) -> list[Unit]:
    """Mass converts to volume and volume to mass."""
    return VOLUME if unit in MASS else MASS


def across(value: Decimal, source: Unit, target: Unit, density: Decimal) -> Decimal:
    """Mass ↔ volume in any units, e.g. liter → kilogram, through gram and milliliter."""
    if source in MASS and target in VOLUME:
        return convert(grams_to_ml(convert(value, source, GRAM), density), ML, target)
    if source in VOLUME and target in MASS:
        return convert(ml_to_grams(convert(value, source, ML), density), GRAM, target)
    raise ValueError("Velg én vektenhet og én volumenhet.")


def across_to_all(value: Decimal, source: Unit, density: Decimal) -> list[tuple[Unit, Decimal]]:
    return [(unit, across(value, source, unit, density)) for unit in other_table(source)]
