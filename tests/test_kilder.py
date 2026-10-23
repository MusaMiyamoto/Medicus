"""Source check: each sentence of a draft note against the conversation (no language model)."""

from pathlib import Path

import pytest

from medicus import kilder

TRANSCRIPT = (Path(__file__).parent.parent / "samples" / "konsultasjon_eksempel.txt").read_text(encoding="utf-8")


def check(sentence):
    lines = kilder.transcript_lines(TRANSCRIPT)
    return kilder.check_sentence(sentence, lines, kilder._numbers(TRANSCRIPT))


@pytest.mark.parametrize("sentence", [
    "Sår hals og feber i 4 dager.",            # "fire dager" was said
    "Feber opptil 38,8.",
    "Penicillinallergi (utslett som barn).",   # compound word vs "allergisk mot penicillin"
    "Røde, hovne tonsiller med belegg bilateralt.",
    "Temp 38,4.",
    "Strep A-hurtigtest positiv.",
    "Klaritromycin 250 mg x 2 i 5 dager.",     # "to ganger", "fem dager"
    "Ny kontakt om 3 dager ved manglende bedring.",
])
def test_what_was_said_is_supported(sentence):
    result = check(sentence)
    assert result["status"] == "støttet" and result["tall_uten_kilde"] == [] and result["linjer"]


@pytest.mark.parametrize("sentence", [
    "Lungene auskultatorisk normale.",          # never examined in the conversation
    "Hjertelyd uten bilyd.",
])
def test_invented_findings_are_flagged(sentence):
    result = check(sentence)
    assert result["status"] == "ukjent" and result["linjer"] == []


@pytest.mark.parametrize("sentence, number", [
    ("Klaritromycin 500 mg x 2 i 5 dager.", "500"),  # 250 was said: a wrong dose
    ("Temp 39,4.", "39.4"),
    ("Røyker 10 sigaretter daglig.", "10"),
])
def test_numbers_that_were_not_said_are_always_flagged(sentence, number):
    assert number in check(sentence)["tall_uten_kilde"]


def test_not_mentioned_is_its_own_status():
    assert check("Ikke nevnt.")["status"] == "mangler"


def test_numbers_said_as_words_and_with_decimal_commas():
    assert kilder._numbers("fire dager, 38,8 grader og to ganger") == {"4", "38.8", "2"}
    assert kilder._numbers("38,0") == kilder._numbers("38")


def test_whole_note_counts_what_needs_checking():
    note = {"kontaktarsak": "Sår hals og feber.", "anamnese": "- Ingen hoste\n- Røyker 10 sigaretter daglig",
            "funn": "Lungene auskultatorisk normale.", "vurdering": "Ikke nevnt.", "plan": ""}
    result = kilder.check_note(TRANSCRIPT, note)
    assert result["uten_kilde"] == 2
    assert [s["tekst"] for s in result["seksjoner"]["anamnese"]] == ["Ingen hoste", "Røyker 10 sigaretter daglig"]
    assert result["seksjoner"]["plan"] == [] and result["linjer"][0].startswith("Lege: Hei")


def test_empty_and_odd_input_does_not_crash():
    assert kilder.check_note("", {"funn": "Feber."})["uten_kilde"] == 1  # no conversation: nothing is supported
    assert kilder.check_note(TRANSCRIPT, {})["uten_kilde"] == 0
    assert check("...")["status"] == "støttet"  # no words and no numbers: nothing to check
