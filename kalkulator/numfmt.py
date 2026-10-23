"""Reading and writing numbers the Norwegian way: decimal comma, space between thousands."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

DISPLAY_DECIMALS = 10
MAX_INPUT = Decimal("1e15")
THIN_SPACE = " "


class NumberError(ValueError):
    pass


def parse_number(text: str) -> Decimal:
    """Accept '1,5', '1.5', '1 500' and '1 500,25'. Reject anything ambiguous."""
    shown = text.strip()
    cleaned = shown.replace(" ", "").replace(THIN_SPACE, "").replace(" ", "")
    if not cleaned:
        raise NumberError("Skriv inn et tall.")
    if cleaned.count(",") + cleaned.count(".") > 1:
        raise NumberError("Bruk bare ett desimaltegn, for eksempel 1,5.")
    try:
        value = Decimal(cleaned.replace(",", "."))
    except InvalidOperation:
        raise NumberError(f"«{shown}» er ikke et tall.") from None
    if not value.is_finite():
        raise NumberError(f"«{shown}» er ikke et tall.")
    if abs(value) >= MAX_INPUT:
        raise NumberError("Tallet er for stort.")
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
    return f"{result},{fraction}" if fraction else result
