"""Unit conversions. Decimal arithmetic, so 0,1 l is exactly 100 ml."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Unit:
    symbol: str
    name: str
    factor: Decimal  # size of one unit, in the table's base unit


# Base unit: liter.
VOLUME = [
    Unit("ml", "milliliter", Decimal("0.001")),
    Unit("dl", "desiliter", Decimal("0.1")),
    Unit("l", "liter", Decimal("1")),
]

# Base unit: gram.
MASS = [
    Unit("mg", "milligram", Decimal("0.001")),
    Unit("g", "gram", Decimal("1")),
    Unit("hg", "hektogram", Decimal("100")),
    Unit("kg", "kilogram", Decimal("1000")),
]


def convert(value: Decimal, source: Unit, target: Unit) -> Decimal:
    return value * source.factor / target.factor


def convert_to_all(value: Decimal, source: Unit, table: list[Unit]) -> list[tuple[Unit, Decimal]]:
    return [(unit, convert(value, source, unit)) for unit in table]


@dataclass(frozen=True)
class Substance:
    name: str
    density: Decimal | None  # g/ml; None means the user types their own


# Approximate values at room temperature. Water is the default.
SUBSTANCES = [
    Substance("Vann", Decimal("1.00")),
    Substance("Melk", Decimal("1.03")),
    Substance("Olivenolje", Decimal("0.92")),
    Substance("Honning", Decimal("1.42")),
    Substance("Etanol (ren sprit)", Decimal("0.789")),
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
