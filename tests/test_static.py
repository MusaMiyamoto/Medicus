import re
from pathlib import Path

STATIC = Path(__file__).parent.parent / "medicus/static"


def test_hidden_wins_over_display_rules():
    """A recording bar or patient box marked `hidden` must not show because its class sets display:flex."""
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}", css)
