"""Reading and writing numbers: decimal comma in Norwegian, decimal point in English, space between thousands."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from .sprak import _, english

DISPLAY_DECIMALS = 10
MAX_INPUT = Decimal("1e15")
THIN_SPACE = " "


class NumberError(ValueError):
    pass


def parse_number(text: str) -> Decimal:
    """Accept '1,5', '1.5', '1 500' and '1 500,25'. Reject anything ambiguous.

    In English a comma is refused: '1,500' means 1500 there, and guessing is not safe.
    """
    shown = text.strip()
    cleaned = shown.replace(" ", "").replace(THIN_SPACE, "").replace(" ", "")
    if not cleaned:
        raise NumberError(_("Skriv inn et tall."))
    if english() and "," in cleaned:
        raise NumberError(_("Bruk punktum som desimaltegn, for eksempel 1.5. Komma er ikke tillatt."))
    if cleaned.count(",") + cleaned.count(".") > 1:
        raise NumberError(_("Bruk bare ett desimaltegn, for eksempel 1,5."))
    try:
        value = Decimal(cleaned.replace(",", "."))
    except InvalidOperation:
        raise NumberError(_("«{}» er ikke et tall.").format(shown)) from None
    if not value.is_finite():
        raise NumberError(_("«{}» er ikke et tall.").format(shown))
    if abs(value) >= MAX_INPUT:
        raise NumberError(_("Tallet er for stort."))
    return value


def format_number(value: Decimal) -> str:
    """Round to at most 10 decimals, drop trailing zeros, and group thousands."""
    with localcontext() as ctx:
        ctx.prec = 60
        rounded = value.quantize(Decimal(1).scaleb(-DISPLAY_DECIMALS), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = Decimal(0)
    text = f"{rounded:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    sign = "−" if text.startswith("-") else ""
    whole, _, fraction = text.lstrip("-").partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    result = sign + THIN_SPACE.join(groups)
    decimal_sign = "." if english() else ","
    return f"{result}{decimal_sign}{fraction}" if fraction else result
