"""Phishing check for email arriving from outside the health network.

Messages sent inside the network are verified by the sender's card login and never need this.
External email gets a risk level and plain-Norwegian reasons a normal employee can act on:

    "ekstern"     from outside, nothing suspicious found – still be careful
    "mistenkelig" one or more warning signs – don't click, don't answer, report it
"""

import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Real domains people in Norwegian healthcare expect mail from. Look-alikes of these are the
# classic phishing trick (helsen0rge.no, nhn-no.com, helsenorge-sikkerhet.com).
TRUSTED_DOMAINS = {
    "helsenorge.no", "nhn.no", "helsedirektoratet.no", "fhi.no", "dmp.no", "helsetilsynet.no",
    "regjeringen.no", "nav.no", "skatteetaten.no", "politiet.no", "legeforeningen.no",
}

URGENT = ["innen 24 timer", "umiddelbart", "haster", "stengt", "sperret", "suspendert", "siste varsel",
          "utløper", "frist i dag", "unngå at"]
CREDENTIALS = ["passord", "bankid", "pin-kode", "pinkode", "logg inn", "bekreft identitet",
               "bekreft kontoen", "kortnummer", "personnummer", "fødselsnummer", "brukernavn"]
DANGEROUS_ATTACHMENTS = {".exe", ".scr", ".js", ".vbs", ".bat", ".cmd", ".ps1", ".msi", ".jar",
                         ".html", ".htm", ".zip", ".rar", ".7z", ".iso", ".img", ".docm", ".xlsm", ".pptm", ".lnk"}
HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a",
                            "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "і": "i"})

LINK = re.compile(r"\[([^\]]+)\]\((\S+?)\)|(https?://\S+)")


@dataclass
class Verdict:
    level: str = "ekstern"
    reasons: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)

    def warn(self, reason: str):
        self.level = "mistenkelig"
        if reason not in self.reasons:
            self.reasons.append(reason)

    def as_dict(self) -> dict:
        return {"nivå": self.level, "grunner": self.reasons, "lenker": self.links}


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower().rstrip(">")


def registrable(domain: str) -> str:
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def skeleton(text: str) -> str:
    """Fold look-alike characters so 'he1sen0rge' and 'helsenorge' compare equal."""
    text = unicodedata.normalize("NFKC", text.lower()).translate(HOMOGLYPHS)
    return re.sub(r"[^a-zæøå]", "", text)


def distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def imitates(domain: str) -> str | None:
    """The trusted domain this one pretends to be, or None."""
    reg = registrable(domain)
    if reg in TRUSTED_DOMAINS:
        return None
    for trusted in TRUSTED_DOMAINS:
        name = trusted.split(".")[0]
        if name in skeleton(domain) or distance(skeleton(reg.split(".")[0]), name) <= 2:
            return trusted
    return None


def check_email(sender_name: str, sender_address: str, subject: str, body: str,
                attachments: list[str] = (), reply_to: str = "") -> Verdict:
    verdict = Verdict()
    domain = domain_of(sender_address)

    target = imitates(domain)
    if target:
        verdict.warn(f"Avsenderadressen «{domain}» ligner på «{target}», men er ikke den ekte.")

    named_after = next((d for d in TRUSTED_DOMAINS if d.split(".")[0] in skeleton(sender_name)), None)
    if named_after and registrable(domain) != named_after:
        verdict.warn(f"Avsendernavnet sier «{sender_name}», men e-posten kommer fra «{domain}».")

    if reply_to and registrable(domain_of(reply_to)) != registrable(domain):
        verdict.warn(f"Svar går til en annen adresse («{domain_of(reply_to)}») enn avsenderen.")

    text = f"{subject}\n{body}".lower()
    urgent = [w for w in URGENT if w in text]
    asks = [w for w in CREDENTIALS if w in text]
    if urgent and asks:
        verdict.warn("E-posten lager tidspress og ber deg logge inn eller oppgi opplysninger. "
                     "Ekte tjenester ber aldri om dette på e-post.")
    elif asks:
        verdict.warn("E-posten ber om innlogging eller personlige opplysninger.")

    for match in LINK.finditer(body):
        shown, href = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(3))
        real = urlparse(href).hostname or ""
        link = {"tekst": shown, "går_til": real}
        verdict.links.append(link)
        shown_host = urlparse(shown).hostname if shown.startswith("http") else None
        if shown_host and registrable(shown_host) != registrable(real):
            verdict.warn(f"En lenke viser «{shown_host}», men går egentlig til «{real}».")
        elif imitates(real):
            verdict.warn(f"En lenke går til «{real}», som etterligner «{imitates(real)}».")
        if urlparse(href).scheme == "http":
            verdict.warn("En lenke bruker ukryptert forbindelse (http).")
        if re.fullmatch(r"[\d.]+", real or ""):
            verdict.warn("En lenke går til en IP-adresse i stedet for et navn.")

    for name in attachments:
        lower = name.lower()
        ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
        if ext in DANGEROUS_ATTACHMENTS or re.search(r"\.(pdf|docx?|jpe?g)\.\w+$", lower):
            verdict.warn(f"Vedlegget «{name}» kan inneholde skadelig programvare.")

    return verdict
