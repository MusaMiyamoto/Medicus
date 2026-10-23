"""The parts of the Text editor that don't need a window: titles and reading files."""

from pathlib import Path

APP_NAME = "Text"
UNTITLED = "Uten tittel"
MAX_BYTES = 20 * 1024 * 1024  # bigger files are almost never notes, and would freeze the editor


class OpenError(ValueError):
    pass


def window_title(path: Path | None, modified: bool) -> str:
    name = path.name if path else UNTITLED
    return f"{'*' if modified else ''}{name} – {APP_NAME}"


def read_text(path: Path) -> str:
    """UTF-8 first, then Windows' Western European encoding, so old files from Windows open too."""
    if path.stat().st_size > MAX_BYTES:
        raise OpenError("Filen er for stor til å åpnes i Text.")
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        raise OpenError("Dette er ikke en tekstfil.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def write_text(path: Path, text: str) -> None:
    """Write to a temporary file first, so a full disk can't leave half a file behind."""
    tmp = path.with_name(f".{path.name}.lagres")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
