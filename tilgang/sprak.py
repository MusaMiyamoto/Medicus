"""Norwegian or English on the login screen, and the language the desktop session starts in.

The login screen is written in Norwegian. A button on it switches to English: the screen's text
(and the messages from the card and PIN check) are then shown in English below, and the person's
session starts with an English locale (en_GB), so the menus and the Medicus apps follow.
"""

import re

LOCALES = {"nb": "nb_NO.UTF-8", "en": "en_GB.UTF-8"}

DAYS = {"nb": ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MONTHS = {"nb": ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
                 "september", "oktober", "november", "desember"],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August",
                 "September", "October", "November", "December"]}

EN = {
    "TRYGG ARBEIDSSTASJON FOR HELSEPERSONELL": "SECURE WORKSTATION FOR HEALTH PERSONNEL",
    "PIN-kode": "PIN",
    "Logg inn": "Log in",
    "Logger inn": "Logging in",
    "Nødtilgang": "Emergency access",
    "Starter nødtilgang": "Starting emergency access",
    "Hva er situasjonen?": "What is the situation?",
    "Avbryt": "Cancel",
    "DEMO": "DEMO",
    "Simulering": "Simulation",
    "Start på nytt": "Restart",
    "Slå av": "Shut down",
    "Ta ut kort": "Remove card",
    "Sett inn kort": "Insert card",
    "Sett inn helsepersonellkortet": "Insert your health-personnel card",
    "Kortleseren står ved siden av skjermen.": "The card reader is next to the screen.",
    "Får ikke kontakt med innloggingstjenesten.": "Cannot reach the login service.",
    "Den åpnes når du logger inn.": "It opens when you log in.",
    "Fristen er ute! ": "The deadline has passed! ",
    "Kunne ikke starte økten.": "Could not start the session.",
    "Innloggingen ble avvist.": "The login was refused.",
    "Kortet er sperret etter for mange feil PIN-forsøk. Kontakt IT-avdelingen for å låse det opp.":
        "The card is blocked after too many wrong PINs. Contact the IT department to unblock it.",
    "Dette kortet er meldt tapt eller erstattet og virker ikke lenger. Kontakt IT-avdelingen.":
        "This card has been reported lost or replaced and no longer works. Contact the IT department.",
    "Kortet er utløpt. Hent nytt kort. Nødtilgang virker fortsatt.":
        "The card has expired. Get a new card. Emergency access still works.",
    "Feil PIN. Kortet er nå sperret.": "Wrong PIN. The card is now blocked.",
    "Kortet er sperret.": "The card is blocked.",
    "Ingen kort i leseren.": "No card in the reader.",
    "Nødtilgang er bare for helsepersonell.": "Emergency access is for health personnel only.",
    "Nødtilgang krever helsepersonellkort, slik at tilgangen kan spores.":
        "Emergency access needs a health-personnel card, so the access can be traced.",
    "Ukjent kort.": "Unknown card.",
    "Sett inn helsepersonellkortet ditt.": "Insert your health-personnel card.",
    "Sett inn kortet ditt.": "Insert your card.",
    "Kortet tilhører en annen bruker.": "The card belongs to another user.",
    "Skriv PIN-koden din.": "Type your PIN.",
    "Logg ut før du bytter arbeidssted.": "Log out before you change workplace.",
    # Roles, positions and situations
    "Lege": "Doctor",
    "Sykepleier": "Nurse",
    "Ambulansearbeider": "Paramedic",
    "Overlege, kardiologi": "Consultant, cardiology",
    "Overlege, indremedisin": "Consultant, internal medicine",
    "Gjesteoverlege, kardiologi": "Visiting consultant, cardiology",
    "Fastlege": "GP",
    "Intensivsykepleier": "Intensive care nurse",
    "Sykepleier, akuttmottak": "Nurse, emergency department",
    "Hjertestans": "Cardiac arrest",
    "Bevisstløs pasient": "Unconscious patient",
    "Alvorlig allergisk reaksjon": "Severe allergic reaction",
    "Alvorlig skade / ulykke": "Serious injury / accident",
    "Annen livstruende situasjon": "Other life-threatening situation",
    # Workplaces: the hospitals' own names, in their usual English form
    "Oslo universitetssykehus, Ullevål": "Oslo University Hospital, Ullevål",
    "Oslo universitetssykehus, Aker": "Oslo University Hospital, Aker",
    "St. Olavs hospital, Trondheim": "St. Olav's Hospital, Trondheim",
    "Medicus legesenter": "Medicus medical centre",
    "Ukjent arbeidssted (kontakt IT)": "Unknown workplace (contact IT)",
}

RULES = [
    (re.compile(r"^Feil PIN\. (\d) forsøk igjen\.$"), r"Wrong PIN. \1 tries left."),
    (re.compile(r"^Hei, (.+)$"), r"Hello, \1"),
    (re.compile(r"^Kortet gikk ut (.+)\. Hent nytt kort\. Nødtilgang virker fortsatt\.$"),
     r"The card expired \1. Get a new card. Emergency access still works."),
    (re.compile(r"^Dette kortet er .+ og virker ikke lenger\. Kontakt IT\.$"),
     "This card has been reported lost or replaced and no longer works. Contact IT."),
    (re.compile(r"^IT-modus · (.+)$"), lambda m: f"IT mode · {t(m[1], 'en')}"),
    (re.compile(r"^Kun livsviktig informasjon i (\d+) min\. Logges med ditt navn\.\nDu skriver en rapport om hvorfor før skiftet er slutt\.$"),
     r"Life-critical information only, for \1 min. Logged with your name.\nYou write a report on why before your shift ends."),
    (re.compile(r"^Du har en nødtilgangsrapport å skrive \(frist kl\. (\d\d:\d\d)\)\.$"),
     r"You have an emergency access report to write (due at \1)."),
]


def t(text: str, lang: str) -> str:
    """The text in this language. Unknown text is shown as it is (in Norwegian)."""
    if lang != "en" or not text:
        return text
    if "\n" in text and text not in EN and not any(p.match(text) for p, _ in RULES):
        return "\n".join(t(line, lang) for line in text.split("\n"))
    if text in EN:
        return EN[text]
    for pattern, english in RULES:
        if pattern.match(text):
            return pattern.sub(english, text)
    if " · " in text:
        return " · ".join(t(part, lang) for part in text.split(" · "))
    return text


def date_text(now, lang: str) -> str:
    if lang == "en":
        return f"{DAYS['en'][now.weekday()]} {now.day} {MONTHS['en'][now.month - 1]}"
    return f"{DAYS['nb'][now.weekday()]} {now.day}. {MONTHS['nb'][now.month - 1]}"
