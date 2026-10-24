"""The Task Manager in Norwegian or English (English when the session was started in English)."""

import os


def english() -> bool:
    return os.environ.get("LANG", "").startswith("en")


def _(text: str) -> str:
    """The text in the session's language. Text with {} is formatted by the caller after this."""
    return EN.get(text, text) if english() else text


EN = {
    # Window
    "Oppgavebehandling": "Task Manager",
    "IT-modus. Å stoppe et program bekreftes med PIN for IT-kortet og skrives i revisjonsloggen.":
        "IT mode. Stopping a program is confirmed with the IT card PIN and written to the audit log.",
    "Søk etter program, bruker eller PID": "Search by program, user or PID",
    "Sorter: CPU": "Sort: CPU",
    "Sorter: minne": "Sort: memory",
    "Sorter: navn": "Sort: name",
    "Program": "Program",
    "PID": "PID",
    "Bruker": "User",
    "Status": "Status",
    "CPU": "CPU",
    "Minne": "Memory",
    "{} prosesser · CPU {} % · minne {} av {} brukt": "{} processes · CPU {} % · memory {} of {} used",
    "Velg et program i listen.": "Choose a program in the list.",
    "Avslutt": "Close",
    "Tving avslutning": "Force close",
    "Avbryt": "Cancel",
    "Beskyttet": "Protected",
    "PID {} · bruker {} · {}": "PID {} · user {} · {}",
    # Protection reasons (oppgaver/prosesser.py)
    "Del av operativsystemets kjerne.": "Part of the operating system kernel.",
    "Dette er Oppgavebehandling selv.": "This is the Task Manager itself.",
    "Systemtjeneste. Start den på nytt med systemctl i terminalen i stedet.":
        "System service. Restart it with systemctl in the terminal instead.",
    "Skrivebordet trenger denne. Logg ut i stedet.": "The desktop needs this. Log out instead.",
    # Status (oppgaver/prosesser.py)
    "Kjører": "Running",
    "Venter": "Waiting",
    "Venter på disk": "Waiting for disk",
    "Inaktiv": "Idle",
    "Stoppet": "Stopped",
    "Avsluttet (zombie)": "Ended (zombie)",
    "Avsluttet": "Ended",
    # Program names (oppgaver/prosesser.py)
    "Kortinnlogging": "Card login",
    "Kortvakt": "Card watch",
    "Forhåndshenting": "Prefetch",
    "Pasientjournal (tjeneste)": "Patient record (service)",
    "Helsenett": "Health network",
    "Nettleser": "Browser",
    "Journalsystem": "Record system",
    "Text": "Text",
    "Journalassistent": "Journal assistant",
    "Pasientjournal": "Patient record",
    "Post": "Mail",
    "Om Medicus": "About Medicus",
    "Nødtilgang": "Emergency access",
    "Rapport om nødtilgang": "Emergency access report",
    "Innbyggerportal": "Citizen portal",
    "Utleveringsforespørsler": "Disclosure requests",
    "Files": "Files",
    "Pictures": "Pictures",
    "Dokumenter": "Documents",
    # Lukk program som henger (health personnel)
    "Lukk program som henger": "Close a frozen program",
    "Her ser du bare programmene du jobber i. Lukk et program som har hengt seg opp. Utkast i journalen lagres automatisk.":
        "Only the programs you work in are shown here. Close a program that has frozen. Drafts in the record are saved automatically.",
    "Søk etter program": "Search for a program",
    "{} programmer åpne": "{} programs open",
    "Lukker …": "Closing …",
    "Kalkulator": "Calculator",
    # Confirmation
    "Avslutte {}?": "Close {}?",
    "Tvinge {} til å avslutte?": "Force {} to close?",
    "Programmet blir bedt om å lukke, slik at det kan lagre først.":
        "The program is asked to close, so it can save first.",
    "Programmet stoppes med en gang. Alt som ikke er lagret, går tapt.":
        "The program is stopped at once. Anything not saved is lost.",
    "Dette programmet kan ha journalnotater som ikke er lagret. Utkast lagres automatisk, men det siste "
    "du skrev kan gå tapt.":
        "This program may have record notes that are not saved. Drafts are saved automatically, but the "
        "last thing typed may be lost.",
    "Programmet tilhører en annen bruker ({}).": "The program belongs to another user ({}).",
    "Bekreft med PIN for IT-kortet": "Confirm with the IT card PIN",
    "Stopper …": "Stopping …",
    # Results
    "{} er avsluttet.": "{} has closed.",
    "Feil PIN, eller IT-kortet er sperret.": "Wrong PIN, or the IT card is blocked.",
    "Programmet var allerede avsluttet.": "The program had already closed.",
    "{} svarer ikke. Prøv «Tving avslutning».": "{} is not responding. Try “Force close”.",
    "Dette programmet er beskyttet og kan ikke stoppes her.": "This program is protected and can't be stopped here.",
    "Noe gikk galt: {}": "Something went wrong: {}",
}
