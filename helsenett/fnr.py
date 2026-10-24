"""Norwegian national identity numbers (fødselsnummer), including synthetic test numbers.

Synthetic numbers (used by Skatteetaten's test data) add 80 to the month, so they can
never belong to a real person. Medicus' simulator only ever creates synthetic numbers.
"""

K1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
K2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _control(digits: list[int], weights: tuple[int, ...]) -> int | None:
    rest = 11 - sum(d * w for d, w in zip(digits, weights)) % 11
    if rest == 11:
        return 0
    return None if rest == 10 else rest


def is_valid(fnr: str) -> bool:
    if len(fnr) != 11 or not fnr.isdigit():
        return False
    digits = [int(c) for c in fnr]
    return _control(digits[:9], K1) == digits[9] and _control(digits[:10], K2) == digits[10]


def is_synthetic(fnr: str) -> bool:
    return is_valid(fnr) and int(fnr[2:4]) > 80


def make_synthetic(day: int, month: int, year2: int, individual: int) -> str:
    """Build a valid synthetic number. Tries individual numbers upward until the checksum works."""
    for ind in range(individual, individual + 100):
        base = f"{day:02d}{month + 80:02d}{year2:02d}{ind % 1000:03d}"
        digits = [int(c) for c in base]
        k1 = _control(digits, K1)
        if k1 is None:
            continue
        k2 = _control(digits + [k1], K2)
        if k2 is None:
            continue
        return f"{base}{k1}{k2}"
    raise ValueError("Fant ikke gyldig syntetisk fødselsnummer")


def mask(fnr: str) -> str:
    """Show only the birth date part, e.g. for lists: 010180 *****."""
    return f"{fnr[:6]} *****"
