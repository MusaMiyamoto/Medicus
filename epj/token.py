"""Access tokens for journal systems.

A real connection gets its token from HelseID (client credentials with private_key_jwt, issued to
this Medicus installation). That needs an agreement first, so for now a token can only come from a
file that IT puts there in a test environment. Without one, every call says what is missing.
"""

from pathlib import Path

from helsenett.client import IkkeTilkoblet

MISSING = ("Medicus er ikke koblet til {system} ennå. Det krever avtale med virksomheten og leverandøren, "
           "og en HelseID-klient med tilgang. Se docs/journalsystemer.md.")


def from_file(path: str, system: str):
    def token() -> str:
        try:
            value = Path(path).read_text().strip() if path else ""
        except OSError:
            value = ""
        if not value:
            raise IkkeTilkoblet(MISSING.format(system=system))
        return value
    return token
