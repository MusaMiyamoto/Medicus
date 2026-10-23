"""Where in the conversation does each sentence of the note come from?

Checked without the language model: it is plain word matching against the transcript, so the check
can't make things up the way a model could. For every sentence in the draft:

  støttet  most of its words are said in one or two lines of the conversation
  svak     only some of them are: read it against the conversation
  ukjent   it doesn't match anything said: the model may have added it
  mangler  the section says "Ikke nevnt.": fill it in or leave it

Separately, every number in a sentence (fever, dose, days, …) must have been said in the conversation,
also when spoken as a word ("fire dager" = 4). A number that wasn't said is always flagged, because a
wrong dose or value is the most dangerous kind of mistake.

The clinician still reads and approves the note. This only shows where to look.
"""

import re

from .notes import MISSING, SECTIONS

STRONG, WEAK = 0.5, 0.25
STEM = 5

# Spoken numbers. "en"/"ett" are also "a/one", so a conversation with "en" supports 1: harmless.
NUMBER_WORDS = {
    "null": "0", "en": "1", "ett": "1", "én": "1", "to": "2", "tre": "3", "fire": "4", "fem": "5",
    "seks": "6", "sju": "7", "syv": "7", "åtte": "8", "ni": "9", "ti": "10", "elleve": "11", "tolv": "12",
    "tretten": "13", "fjorten": "14", "femten": "15", "seksten": "16", "sytten": "17", "atten": "18",
    "nitten": "19", "tjue": "20", "tretti": "30", "førti": "40", "femti": "50", "hundre": "100",
    "halv": "0.5", "halvannen": "1.5", "dobbel": "2",
}

STOPWORDS = set("""
og i på er det som en et til av for med har ikke at jeg du han hun den de vi dere seg sin sitt sine
om så men eller når fra ved var vil kan skal må blir ble være vært hadde hva hvor hvordan hvis da
nå også bare litt meget veldig mye noe noen alle etter før under over mot inn ut opp ned her der
denne dette disse deg meg oss dem min mitt mine din ditt dine hans hennes deres vår vårt våre
pasienten pasient pas lege legen sier forteller oppgir angir får fått gir gitt tar tatt
ja nei takk hei
""".split())

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
WORD = re.compile(r"[a-zæøåéü]+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÆØÅ0-9])")


def _numbers(text: str) -> set[str]:
    lowered = text.lower()
    found = {n.replace(",", ".") for n in NUMBER.findall(lowered)}
    found |= {NUMBER_WORDS[w] for w in WORD.findall(lowered) if w in NUMBER_WORDS}
    # 38.0 and 38 are the same value.
    return {n[:-2] if n.endswith(".0") else n for n in found}


def _words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS and w not in NUMBER_WORDS and len(w) > 2]


def _same(a: str, b: str) -> bool:
    """Same word, inflection or compound part: "hovne"/"hoven", "penicillinallergi"/"penicillin"."""
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    if a.startswith(b) or b.startswith(a):  # "temp"/"temperaturen"
        return True
    return a[:STEM] == b[:STEM] or (len(b) >= STEM and b[:STEM] in a) or (len(a) >= STEM and a[:STEM] in b)


def transcript_lines(transcript: str) -> list[str]:
    """The conversation as lines (one per speaker turn); long turns are split into sentences."""
    lines = []
    for line in transcript.splitlines():
        line = line.strip()
        if line:
            lines += [part.strip() for part in SENTENCE_END.split(line) if part.strip()]
    return lines


def sentences(text: str) -> list[str]:
    """A section as sentences: bullet lines first, then sentence ends."""
    result = []
    for line in text.splitlines():
        line = line.strip().lstrip("-•* ").strip()
        if line:
            result += [part.strip() for part in SENTENCE_END.split(line) if part.strip()]
    return result


def check_sentence(sentence: str, lines: list[str], said_numbers: set[str]) -> dict:
    result = {"tekst": sentence, "linjer": [], "status": "ukjent", "tall_uten_kilde": []}
    if sentence.strip().rstrip(".").lower() == MISSING.rstrip(".").lower():
        result["status"] = "mangler"
        return result
    result["tall_uten_kilde"] = sorted(_numbers(sentence) - said_numbers)
    words = set(_words(sentence))
    if not words:
        # Only numbers or filler: it stands or falls with its numbers.
        result["status"] = "svak" if result["tall_uten_kilde"] else "støttet"
        return result
    scored = []
    for i, line in enumerate(lines):
        line_words = set(_words(line))
        hits = {w for w in words if any(_same(w, lw) for lw in line_words)}
        if hits:
            scored.append((len(hits), i, hits))
    scored.sort(key=lambda s: (-s[0], s[1]))
    best = scored[:2]
    covered = set().union(*(hits for _, _, hits in best)) if best else set()
    coverage = len(covered) / len(words)
    result["linjer"] = sorted(i for _, i, _ in best)
    result["status"] = "støttet" if coverage >= STRONG else "svak" if coverage >= WEAK else "ukjent"
    if result["status"] == "ukjent":
        result["linjer"] = []
    return result


def check_note(transcript: str, sections: dict[str, str]) -> dict:
    """Every sentence of every section, with its lines in the conversation and a status."""
    lines = transcript_lines(transcript)
    said = _numbers(transcript)
    checked = {key: [check_sentence(s, lines, said) for s in sentences(sections.get(key, ""))]
               for key, _ in SECTIONS}
    flagged = sum(1 for items in checked.values() for item in items
                  if item["status"] == "ukjent" or item["tall_uten_kilde"])
    return {"linjer": lines, "seksjoner": checked, "uten_kilde": flagged}
