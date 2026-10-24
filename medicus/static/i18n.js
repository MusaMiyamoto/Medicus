// Norwegian or English. Every Medicus page is written in Norwegian; in English this file swaps the
// text on the page (and what the server answers) for the English below, as it appears and changes.
// The choice is kept in this browser. Without one, English is used when the browser or the
// Medicus OS session is set to English (LANG=en_GB), Norwegian otherwise.
// Clinical content stays as written: patient records, notes, the conversation and anything typed.

const LANG = (() => {
  try {
    const saved = localStorage.getItem("medicus_lang");
    if (saved === "en" || saved === "nb") return saved;
  } catch (e) { /* storage blocked: fall back to the browser's language */ }
  return (navigator.language || "").toLowerCase().startsWith("en") ? "en" : "nb";
})();

const EN = {
  // Shared
  "Medicus": "Medicus",
  "Laster": "Loading",
  "Nettdemo": "Web demo",
  "– bare syntetiske data.": "– synthetic data only.",
  "Tilbake til demoen / bytt kort": "Back to the demo / switch card",
  "Skriv rapporten nå": "Write the report now",
  "Pasientjournal": "Patient record",
  "Post": "Mail",
  "Journalassistent": "Journal assistant",
  "Journalassistenten": "The journal assistant",
  "Nettleser": "Browser",
  "Overføring": "Transfer",
  "Sikkerhetssenter": "Security centre",
  "Om Medicus": "About Medicus",
  "Avbryt": "Cancel",
  "Lukk": "Close",
  "Send": "Send",
  "Logg inn": "Log in",
  "Logg ut": "Log out",
  "Du er ikke logget inn.": "You are not logged in.",

  // Roles, positions and workplaces (demo cards)
  "Lege": "Doctor",
  "Sykepleier": "Nurse",
  "Ambulansearbeider": "Paramedic",
  "IT": "IT",
  "Overlege, kardiologi": "Consultant, cardiology",
  "Overlege, indremedisin": "Consultant, internal medicine",
  "Gjesteoverlege, kardiologi": "Visiting consultant, cardiology",
  "Fastlege": "GP",
  "Intensivsykepleier": "Intensive care nurse",
  "Sykepleier, akuttmottak": "Nurse, emergency department",
  "Oslo universitetssykehus, Ullevål": "Oslo University Hospital, Ullevål",
  "Oslo universitetssykehus, Aker": "Oslo University Hospital, Aker",
  "Oslo universitetssykehus": "Oslo University Hospital",
  "St. Olavs hospital, Trondheim": "St. Olav's Hospital, Trondheim",
  "Medicus legesenter": "Medicus medical centre",
  "Testby legevakt": "Testby out-of-hours clinic",
  "Ukjent arbeidssted (kontakt IT)": "Unknown workplace (contact IT)",
  "Helsenett (simulert)": "Norwegian Health Network (simulated)",

  // Emergency situations
  "Hjertestans": "Cardiac arrest",
  "Bevisstløs pasient": "Unconscious patient",
  "Alvorlig allergisk reaksjon": "Severe allergic reaction",
  "Alvorlig skade / ulykke": "Serious injury / accident",
  "Annen livstruende situasjon": "Other life-threatening situation",
  "Ikke oppgitt": "Not given",

  // The web demo's card picker
  "Prøv Medicus": "Try Medicus",
  "Demo": "Demo",
  "Dette er en nettdemo av Medicus, med bare oppdiktede (syntetiske) pasienter og personer.":
    "This is a web demo of Medicus, with made-up (synthetic) patients and people only.",
  "Ikke skriv inn ekte pasientopplysninger.": "Do not enter real patient information.",
  "I Medicus OS logger du inn med helsepersonellkortet på innloggingsskjermen. Her velger du et demokort i stedet. Alle demokortene har PIN-kode":
    "In Medicus OS you log in with your health-personnel card at the login screen. Here you pick a demo card instead. Every demo card has PIN",
  ". In English: the button at the top right.": ". På norsk: knappen øverst til høyre.",
  "Sett inn kort": "Insert card",
  "Velg et demokort. Alle har PIN-kode": "Pick a demo card. They all have PIN",
  ". Tre feil PIN sperrer kortet (bare i din nettleser).": ". Three wrong PINs block the card (in your browser only).",
  "Demokort": "Demo cards",
  "Arbeidssted (der PC-en står)": "Workplace (where the PC is)",
  "PIN-kode": "PIN",
  "Nødtilgang …": "Emergency access …",
  "Nødtilgang: kortet uten PIN, i 30 minutter, når liv står på spill. Alt logges, og du må skrive en rapport etterpå. Hva er situasjonen?":
    "Emergency access: the card without a PIN, for 30 minutes, when a life is at stake. Everything is logged, and you must write a report afterwards. What is the situation?",
  "Velkommen": "Welcome",
  "Ta ut kortet (logg ut)": "Remove the card (log out)",
  "Start demoen på nytt": "Start the demo again",
  "I Medicus OS åpnes disse som egne vinduer på skrivebordet. Tar du ut kortet der, låses skjermen og økten holdes i 15 minutter, så du kan fortsette med samme kort og PIN.":
    "In Medicus OS these open as their own windows on the desktop. If you remove the card there, the screen locks and the session is held for 15 minutes, so you can carry on with the same card and PIN.",
  "Om demoen": "About the demo",
  "Ikke med i nettdemoen: innloggingsskjermen med kortleser, skjermlås, sletting av hjemmemappen ved utlogging, journalassistentens opptak (ingen tale- eller språkmodell her: eksempelsamtalen blir et ferdig eksempelnotat) og Kalkulatoren. Sikkerhetssenteret viser her serveren demoen kjører på, ikke en Medicus-PC.":
    "Not in the web demo: the login screen with the card reader, the screen lock, wiping the home folder at logout, recording in the journal assistant (no speech or language model here: the example conversation becomes a ready-made example note) and the Calculator. The security centre shows the server the demo runs on here, not a Medicus PC.",
  "Pasientjournaler, notater og eksempelsamtalen er på norsk: det er klinisk innhold, som i en norsk journal.":
    "Patient records, notes and the example conversation are in Norwegian: they are clinical content, as in a Norwegian record.",
  "Fra samtale til journalnotat, med kildesjekk og samtykke.": "From conversation to journal note, with source check and consent.",
  "Oppdiktede pasienter, med tilgangslogg.": "Made-up patients, with an access log.",
  "Helsenett-post med merking av ekte og falske avsendere.": "Health-network mail that marks genuine and fake senders.",
  "Bare godkjente nettsteder.": "Approved websites only.",
  "Filer inn og ut, med virusskanning.": "Files in and out, with virus scanning.",
  "Helsenorge (simulert)": "Helsenorge (simulated)",
  "Det innbyggeren ser: hvem som har lest journalen.": "What the citizen sees: who has read their record.",
  "Utlevering (simulert)": "Disclosure (simulated)",
  "Innsyn og utlevering av journal.": "Requests for and disclosure of records.",
  "Åpen kildekode og lisenser.": "Open source and licences.",
  "Status for brannmur, oppdateringer, virusskanning og revisjon.": "Status of firewall, updates, virus scanning and audit.",
  "Velg et kort først.": "Pick a card first.",
  "sperret": "blocked",
  "Ukjent kort.": "Unknown card.",
  "Velg et arbeidssted.": "Pick a workplace.",
  "Demoøkten mangler. Last siden på nytt.": "The demo session is missing. Reload the page.",
  "Nødtilgang er bare for helsepersonell.": "Emergency access is for health personnel only.",
  "Feil PIN. Kortet er nå sperret.": "Wrong PIN. The card is now blocked.",
  "Kortet er sperret etter tre feil PIN-forsøk. I Medicus OS må IT låse det opp. I demoen: trykk «Start demoen på nytt».":
    "The card is blocked after three wrong PINs. In Medicus OS, IT must unblock it. In the demo: press \"Start the demo again\".",
  "Opptak er slått av i demoen: her finnes ingen talegjenkjenning. Bruk «Bruk eksempelsamtale».":
    "Recording is switched off in the demo: there is no speech recognition here. Use \"Use example conversation\".",
  "I demoen finnes det ingen språkmodell. Bare eksempelsamtalen kan gjøres om til et notat (et ferdig eksempelnotat). Trykk «Last eksempel» og prøv igjen.":
    "There is no language model in the demo. Only the example conversation can be turned into a note (a ready-made example note). Press \"Use example conversation\" and try again.",
  "Sikkerhetssenteret viser serveren nettdemoen kjører på, ikke en Medicus-PC. Det er derfor mye her er rødt.":
    "The security centre shows the server the web demo runs on, not a Medicus PC. That is why much of it is red.",

  // Journal assistant
  "Prototype. Bruk kun oppdiktede data – ikke ekte pasientopplysninger. Notatet er et utkast og må alltid kontrolleres av helsepersonell.":
    "Prototype. Use made-up data only – no real patient information. The note is a draft and must always be checked by a clinician.",
  "⚠ Du har et notat som ikke ble godkjent": "⚠ You have a note that was not approved",
  "(lagret kl.": "(saved at",
  "), for eksempel fordi økten ble avsluttet. Det ligger bare i minnet på denne PC-en.":
    "), for example because the session ended. It is only in this PC's memory.",
  "Hent utkastet": "Restore the draft",
  "Forkast det": "Discard it",
  "Pasient": "Patient",
  "Søk blant dine pasienter: navn, fødselsdato eller fødselsnummer": "Search your patients: name, date of birth or national ID number",
  "Bytt pasient": "Change patient",
  "1. Konsultasjon": "1. Consultation",
  "● Start opptak": "● Start recording",
  "Start opptak": "Start recording",
  "■ Stopp opptak": "■ Stop recording",
  "Last opp lydfil": "Upload audio file",
  "Bruk eksempelsamtale": "Use example conversation",
  "Opptak": "Recording",
  "Pasienten ombestemte seg – slett opptaket": "The patient changed their mind – delete the recording",
  "Transkripsjon (kan redigeres)": "Transcript (editable)",
  "Ta opp, last opp lyd, eller lim inn tekst her …": "Record, upload audio, or paste text here …",
  "Lag journalnotat": "Create journal note",
  "2. Journalnotat (utkast)": "2. Journal note (draft)",
  "Ingen notat ennå.": "No note yet.",
  "Kildesjekk": "Source check",
  "Under hvert felt står setningene i notatet. Trykk på en setning for å se hvor i samtalen den kommer fra. Sjekken er vanlig ordsammenligning, ikke språkmodellen.":
    "Under each field are the note's sentences. Tap a sentence to see where in the conversation it comes from. The check is plain word matching, not the language model.",
  "✓ Sagt": "✓ Said",
  "står i samtalen": "is in the conversation",
  "◐ Delvis": "◐ Partly",
  "bare delvis – les den mot samtalen": "only partly – read it against the conversation",
  "✗ Ikke funnet": "✗ Not found",
  "ikke i samtalen, eller et tall som ikke ble sagt": "not in the conversation, or a number that was not said",
  "– Ikke nevnt": "– Not mentioned",
  "fyll inn eller la stå": "fill in or leave",
  "Samtalen": "The conversation",
  "Kopier notat": "Copy note",
  "Godkjenn": "Approve",
  "Godkjenn og lagre i journalen": "Approve and save in the record",
  "Før du tar opp samtalen": "Before you record the conversation",
  "Spør pasienten, for eksempel:": "Ask the patient, for example:",
  "«Jeg vil gjerne ta opp samtalen vår, slik at maskinen kan skrive et utkast til journalnotatet. Opptaket blir bare på denne maskinen og slettes så snart teksten er laget. Det er frivillig, og du kan si nei eller ombestemme deg når som helst. Er det greit for deg?»":
    "\"I would like to record our conversation so the computer can write a draft of the journal note. The recording stays on this computer only and is deleted as soon as the text is made. It is voluntary, and you can say no or change your mind at any time. Is that all right with you?\"",
  "Pasienten er informert og har sagt ja": "The patient has been informed and said yes",
  "Pasienten sa nei": "The patient said no",
  "Kontaktårsak": "Reason for contact",
  "Anamnese": "History",
  "Funn": "Findings",
  "Vurdering": "Assessment",
  "Plan": "Plan",
  "Henter pasientlisten fra journalsystemet …": "Fetching the patient list from the record system …",
  "Transkriberer … dette kan ta noen minutter på en vanlig PC.": "Transcribing … this can take a few minutes on an ordinary PC.",
  "Transkripsjon ferdig. Les over og rett eventuelle feil.": "Transcript done. Read it through and correct any mistakes.",
  "Ingen opptak. Skriv samtalen inn selv, eller skriv notatet som vanlig.": "No recording. Type the conversation yourself, or write the note as usual.",
  "Opptaket er slettet og ble aldri sendt. Skriv notatet som vanlig.": "The recording is deleted and was never sent. Write the note as usual.",
  "Tar opp …": "Recording …",
  "Fikk ikke tilgang til mikrofonen.": "Could not get access to the microphone.",
  "Eksempelsamtale lastet inn (oppdiktet).": "Example conversation loaded (made up).",
  "✓ Alle setninger med innhold finnes i samtalen. Les likevel gjennom før du godkjenner.":
    "✓ Every sentence with content is in the conversation. Read it through anyway before you approve.",
  "Denne setningen finnes ikke i samtalen. Sjekk den, eller slett den.": "This sentence is not in the conversation. Check it, or delete it.",
  "Utkastet er hentet. Les gjennom før du godkjenner.": "The draft is restored. Read it through before you approve.",
  "Forkaste utkastet for godt?": "Discard the draft for good?",
  "Utkastet er forkastet.": "The draft is discarded.",
  "Transkripsjonen er tom.": "The transcript is empty.",
  "Lager journalnotat med lokal språkmodell …": "Creating the journal note with the local language model …",
  "Utkast klart. Kontroller alt før du godkjenner.": "Draft ready. Check everything before you approve.",
  "Notatet er kopiert. Lim det inn i journalsystemet.": "The note is copied. Paste it into the record system.",
  "Har du sjekket dem, og vil du godkjenne notatet likevel?": "Have you checked them, and do you want to approve the note anyway?",
  "Notatet er godkjent og loggført. Velg pasient øverst for å lagre det i journalen.":
    "The note is approved and logged. Pick the patient at the top to save it in the record.",
  "Ingen treff. Skriv hele fødselsnummeret for å finne andre pasienter.": "No matches. Type the full national ID number to find other patients.",
  "ikke på din liste": "not on your list",
  "Pasienten må samtykke før samtalen tas opp eller lastes opp.": "The patient must consent before the conversation is recorded or uploaded.",
  "Kunne ikke transkribere lydfilen.": "Could not transcribe the audio file.",
  "Notatet er for langt.": "The note is too long.",

  // Patient record
  "Pasientjournal – Medicus": "Patient record – Medicus",
  "Åpne journal": "Open record",
  "Når du åpner en journal, får pasienten beskjed på Helsenorge om hvem som så den.":
    "When you open a record, the patient is told on Helsenorge who looked at it.",
  "Lukk journal": "Close record",
  "Kritisk informasjon": "Critical information",
  "Legemidler og resepter": "Medicines and prescriptions",
  "Forskriv e-resept": "Prescribe an e-prescription",
  "Legemiddel": "Medicine",
  "Dosering": "Dosage",
  "Indikasjon": "Indication",
  "Send e-resept": "Send e-prescription",
  "Besøk og notater fra alle virksomheter": "Visits and notes from all providers",
  "Nytt notat (deles med fastlege og andre som behandler pasienten)": "New note (shared with the GP and others treating the patient)",
  "Lagre og del notat": "Save and share note",
  "Hvorfor åpner du journalen?": "Why are you opening the record?",
  "Pasienten er ikke på listen din. Begrunnelsen lagres i tilgangsloggen, og pasienten kan se den på Helsenorge sammen med navnet ditt.":
    "The patient is not on your list. The reason is stored in the access log, and the patient can see it on Helsenorge together with your name.",
  "Begrunnelse": "Reason",
  "Forklaring": "Explanation",
  "(valgfri)": "(optional)",
  "(påkrevd)": "(required)",
  "Allergi": "Allergy",
  "Allergier": "Allergies",
  "Tilstand": "Condition",
  "Implantat": "Implant",
  "Pårørende": "Next of kin",
  "Ingen kritisk informasjon registrert.": "No critical information recorded.",
  "Ingen resepter.": "No prescriptions.",
  "Ingen besøk registrert.": "No visits recorded.",
  "Tilgangen er logget. Pasienten kan se den på Helsenorge.": "The access is logged. The patient can see it on Helsenorge.",
  "Journalen ble ikke åpnet.": "The record was not opened.",
  "Velg en begrunnelse.": "Pick a reason.",
  "Notatet er lagret og delt.": "The note is saved and shared.",
  "E-resepten er sendt. Pasienten ser den på Helsenorge.": "The e-prescription is sent. The patient sees it on Helsenorge.",
  "IT-modus har ikke tilgang til pasientdata.": "IT mode has no access to patient data.",
  "Ikke tilgjengelig ved nødtilgang.": "Not available with emergency access.",
  "Bare for IT-personell i IT-modus.": "For IT staff in IT mode only.",
  "Krever nødtilgang.": "Requires emergency access.",
  "Ugyldig fødselsnummer.": "Invalid national ID number.",
  "Velg en begrunnelse fra listen.": "Pick a reason from the list.",
  "Skriv kort hvorfor du åpner journalen (minst 10 tegn).": "Write briefly why you are opening the record (at least 10 characters).",
  "Bare leger kan forskrive resept.": "Only doctors can prescribe.",
  "Akutt behandling": "Emergency treatment",
  "Pasienten er henvist til meg": "The patient has been referred to me",
  "Tilsyn / konsultasjon": "Consultation requested",
  "Vikar for fastlegen": "Covering for the GP",
  "Annet": "Other",

  // Emergency access
  "Nødtilgang – Medicus": "Emergency access – Medicus",
  "NØDTILGANG": "EMERGENCY ACCESS",
  "Kun livsviktig informasjon · logges med ditt navn": "Life-critical information only · logged with your name",
  "Tid igjen": "Time left",
  "Avslutt": "End",
  "Etterpå skriver du en kort rapport om hvorfor, før skiftet ditt er slutt. Den åpnes neste gang du logger inn.":
    "Afterwards you write a short report on why, before your shift ends. It opens the next time you log in.",
  "Finn pasient": "Find patient",
  "Fødselsnummer (11 siffer)": "National ID number (11 digits)",
  "Vis kritisk informasjon": "Show critical information",
  "Syntetiske testpasienter (kun i simulering):": "Synthetic test patients (simulation only):",
  "Ny pasient": "New patient",
  "Kritiske tilstander": "Critical conditions",
  "Legemidler i bruk": "Medicines in use",
  "Implantater og pårørende": "Implants and next of kin",
  "Ingen registrert.": "None recorded.",
  "Oppslaget er logget med ditt navn. Pasienten blir varslet.": "The lookup is logged with your name. The patient is notified.",
  "Nødtilgangen er avsluttet.": "Emergency access has ended.",

  // Emergency report
  "Nødtilgangsrapport – Medicus": "Emergency access report – Medicus",
  "Nødtilgangsrapport": "Emergency access report",
  "Du åpnet nødtilgang. Skriv kort hva som skjedde og hvorfor du trengte tilgangen. Rapporten må være skrevet":
    "You opened emergency access. Write briefly what happened and why you needed access. The report must be written",
  "før skiftet ditt er slutt": "before your shift ends",
  ". Den leses av personvernombudet.": ". It is read by the data protection officer.",
  "Du har ingen rapporter å skrive. Takk!": "You have no reports to write. Thank you!",
  "Hva skjedde, og hvorfor trengtes nødtilgang?": "What happened, and why was emergency access needed?",
  "F.eks.: Pasient funnet bevisstløs i korridoren. Trengte allergier og faste legemidler før behandling.":
    "E.g.: Patient found unconscious in the corridor. Needed allergies and regular medicines before treatment.",
  "Send rapport": "Send report",
  "Takk! Rapporten er sendt.": "Thank you! The report is sent.",
  "forsinket": "late",
  "Rapporten er for kort. Skriv minst 20 tegn.": "The report is too short. Write at least 20 characters.",

  // About
  "Medicus er en sikker arbeidsstasjon for helsepersonell. Den skal bare brukes på maskiner som eies og driftes av helseforetaket, kommunen eller annen offentlig virksomhet, aldri på private PC-er.":
    "Medicus is a secure workstation for health personnel. It may only be used on machines owned and run by the health trust, the municipality or another public body, never on private PCs.",
  "Prototype med syntetiske data. Ikke godkjent for ekte pasientopplysninger.": "Prototype with synthetic data. Not approved for real patient information.",
  "Åpen kildekode": "Open source",
  "Medicus er bygget på fri programvare. Vi takker utviklerne bak disse prosjektene. Lisensene gir deg rett til å få kildekoden; kontakt IT eller leverandøren.":
    "Medicus is built on free software. We thank the developers behind these projects. The licences give you the right to the source code; contact IT or the supplier.",
  "Komponent": "Component",
  "Brukes til": "Used for",
  "Lisens": "Licence",
  "Grunnsystemet": "The base system",
  "Flere fri lisenser, mest GPL": "Several free licences, mostly GPL",
  "Linux-kjernen": "The Linux kernel",
  "Kjernen": "The kernel",
  "Skrivebordet": "The desktop",
  "Innloggingsskjermen": "The login screen",
  "GTK og GLib": "GTK and GLib",
  "Vinduer og knapper": "Windows and buttons",
  "Motoren i Nettleser": "The engine in Browser",
  "Dokumenter (PDF)": "Documents (PDF)",
  "Oppstartsanimasjonen": "The boot animation",
  "Virusskanning": "Virus scanning",
  "Sikkerhet": "Security",
  "Nettfilteret": "The web filter",
  "Medicus-appene": "The Medicus apps",
  "Røntgen- og MR-bilder": "X-ray and MRI images",
  "faster-whisper og Ollama": "faster-whisper and Ollama",
  "Arc-tema, Papirus-ikoner, Noto-skrift": "Arc theme, Papirus icons, Noto fonts",
  "Utseendet": "The look",
  "Den fullstendige lisensteksten for hver pakke ligger på maskinen i": "The full licence text for each package is on the machine in",
  ". Medicus-logoen, bakgrunnsbildene og Medicus-appene er laget for dette prosjektet.":
    ". The Medicus logo, the backgrounds and the Medicus apps were made for this project.",

  // Browser start page
  "Godkjente nettsteder": "Approved websites",
  "Nettleseren åpner bare godkjente nettsteder. Sporing blokkeres, alle forbindelser er krypterte, og nettstedene ser ikke hvilket system du bruker. Mangler du et nettsted? Spør IT.":
    "The browser opens approved websites only. Tracking is blocked, every connection is encrypted, and the sites cannot see which system you use. Missing a website? Ask IT.",
  "Helse": "Health",
  "Offentlige tjenester": "Public services",
  "Nyheter": "News",
  "Innbyggertjenester og informasjon om helse": "Services for citizens and health information",
  "Informasjon om legemidler": "Information about medicines",
  "Legemidler og behandling": "Medicines and treatment",
  "Nasjonale faglige retningslinjer": "National clinical guidelines",
  "Smittevern og vaksinasjon": "Infection control and vaccination",
  "Oppslagsverk for helsepersonell": "Reference works for health personnel",
  "Akuttmedisin": "Emergency medicine",
  "Legemidler og medisinsk utstyr": "Medicines and medical devices",
  "Tilsyn og veiledere": "Supervision and guidance",
  "Helsenettet og nasjonale e-helsetjenester": "The health network and national e-health services",
  "Departementene og regjeringens arbeid": "The ministries and the government's work",
  "Veiviser til offentlige tjenester": "Guide to public services",
  "Arbeid, trygd og sykmelding": "Work, welfare and sick leave",
  "Skatt og folkeregister": "Tax and the population register",
  "Skjema og tjenester for virksomheter": "Forms and services for organisations",
  "Innlogging til offentlige tjenester": "Login to public services",
  "Politiets tjenester": "Police services",
  "Virksomhetsregistre": "Business registers",
  "Personvern": "Data protection",
  "Digitale fellesløsninger": "Shared digital services",
  "Råd om digital sikkerhet": "Advice on digital security",
  "Statens representant i fylkene": "The state's representative in the counties",
  "Lover og vedtak": "Laws and decisions",
  "Arbeidsmiljø": "Working environment",
  "Samfunnssikkerhet og beredskap": "Civil protection and preparedness",
  "Alle kommunenes nettsider": "Every municipality's website",
  "Lover og forskrifter": "Laws and regulations",
  "Nyheter, radio og TV": "News, radio and TV",
  "Nyhetsbyrået": "The news agency",
  "Økonomi": "Business",
  "Nyheter fra Vestland": "News from Vestland",
  "Nyheter fra Rogaland": "News from Rogaland",
  "Nyheter fra Trøndelag": "News from Trøndelag",
  "Nyheter fra Nord-Norge": "News from Northern Norway",
  "Medisinsk fagtidsskrift": "Medical journal",
  "Fagtidsskrift for sykepleiere": "Journal for nurses",
  "Nyheter for leger": "News for doctors",

  // Transfer
  "Overføring – Medicus": "Transfer – Medicus",
  "Prototype. Bruk kun oppdiktede data – ikke ekte pasientopplysninger.": "Prototype. Use made-up data only – no real patient information.",
  "Overføring av journal fra Epic": "Transferring a record from Epic",
  "For pasienter som kommer fra et sykehus eller en kommune som bruker Epic. Medicus leser eksporten, viser deg hva som er med, og lagrer det i pasientens journal først når du har kontrollert det.":
    "For patients coming from a hospital or municipality that uses Epic. Medicus reads the export, shows you what it contains, and saves it in the patient's record only once you have checked it.",
  "Fra eksportfil": "From an export file",
  "Velg eller slipp eksportfilen her (FHIR, .json)": "Pick or drop the export file here (FHIR, .json)",
  "Eksempel med oppdiktet pasient:": "Example with a made-up patient:",
  "Direkte fra Epic": "Directly from Epic",
  "Pasientens fødselsnummer": "The patient's national ID number",
  "Hent fra Epic": "Fetch from Epic",
  "Krever at virksomheten har koblet Medicus til Epic.": "Requires the organisation to have connected Medicus to Epic.",
  "Kontroller før overføring": "Check before transferring",
  "Diagnoser og problemer": "Diagnoses and problems",
  "Legemidler": "Medicines",
  "Dokumenter": "Documents",
  "Allergier og legemidler blir lagt inn som tekst i journalen, merket «må kontrolleres». De blir ikke kritisk informasjon før du selv har registrert dem.":
    "Allergies and medicines are added to the record as text, marked \"must be checked\". They do not become critical information until you have recorded them yourself.",
  "Overfør til journalen": "Transfer to the record",
  "Leser eksporten …": "Reading the export …",
  "Henter fra Epic …": "Fetching from Epic …",
  "Avbrutt. Ingenting ble overført.": "Cancelled. Nothing was transferred.",
  "Pasienten ser overføringen på Helsenorge.": "The patient sees the transfer on Helsenorge.",
  "Filen er for stor (over 20 MB).": "The file is too large (over 20 MB).",
  "Filen er ikke en gyldig FHIR-eksport (JSON).": "The file is not a valid FHIR export (JSON).",
  "Forhåndsvisningen er utløpt. Last inn eksporten på nytt.": "The preview has expired. Load the export again.",
  "Pasienten du bekreftet stemmer ikke med eksporten.": "The patient you confirmed does not match the export.",

  // Mail
  "Post – Medicus": "Mail – Medicus",
  "✓ Verifisert": "✓ Verified",
  "fra helsepersonell i helsenettet": "from health personnel in the health network",
  "↗ Ekstern": "↗ External",
  "fra utenfor – vær forsiktig": "from outside – be careful",
  "⚠ Mistenkelig": "⚠ Suspicious",
  "trolig svindel – ikke klikk, ikke svar": "probably a scam – don't click, don't reply",
  "Ny melding": "New message",
  "Innboks": "Inbox",
  "Sendt": "Sent",
  "Velg en melding.": "Pick a message.",
  "Ny melding i helsenettet": "New message in the health network",
  "Sendes kryptert til mottakere i adresseregisteret. Mottakeren ser at meldingen er fra deg.":
    "Sent encrypted to recipients in the address register. The recipient sees that the message is from you.",
  "Til": "To",
  "Emne": "Subject",
  "Gjelder pasient (valgfritt – pasienten får beskjed på Helsenorge)": "Concerns patient (optional – the patient is told on Helsenorge)",
  "Ingen pasient": "No patient",
  "Melding": "Message",
  "Vedlegg: røntgen, CT, MR (DICOM), bilder eller PDF – maks 50 MB per fil": "Attachments: X-ray, CT, MRI (DICOM), images or PDF – at most 50 MB per file",
  "Lysstyrke": "Brightness",
  "Kontrast": "Contrast",
  "Inverter": "Invert",
  "Har vedlegg": "Has attachments",
  "Ingen meldinger.": "No messages.",
  "✓ Verifisert avsender": "✓ Verified sender",
  "⚠ Dette ser ut som svindel (phishing)": "⚠ This looks like a scam (phishing)",
  "Ikke klikk på noe, ikke svar, og ikke oppgi opplysninger.": "Don't click anything, don't reply, and don't give out any information.",
  "Trykk «Rapporter» nedenfor.": "Press \"Report\" below.",
  "Ekstern e-post": "External email",
  "– fra utenfor helsenettet. Vi fant ingen tegn på svindel, men lenker og vedlegg er blokkert. Ekte helsetjenester ber aldri om passord, PIN eller BankID på e-post.":
    "– from outside the health network. We found no sign of a scam, but links and attachments are blocked. Real health services never ask for passwords, PINs or BankID by email.",
  "Lenker i e-posten (ikke klikkbare):": "Links in the email (not clickable):",
  "Vedlegg blokkert:": "Attachments blocked:",
  "✓ Virusskannet": "✓ Virus scanned",
  "Ikke virusskannet": "Not virus scanned",
  "Rapportert til IT-sikkerhet": "Reported to IT security",
  "Rapporter til IT-sikkerhet": "Report to IT security",
  "Takk! E-posten er rapportert. IT-sikkerhet får beskjed.": "Thank you! The email is reported. IT security is told.",
  "Sender …": "Sending …",
  "Meldingen er sendt gjennom helsenettet.": "The message is sent through the health network.",

  // Security centre
  "Sikkerhetssenter – Medicus": "Security centre – Medicus",
  "IT-modus. Sjekker beskyttelsen på denne maskinen akkurat nå. Hver sjekk har et symbol og et ord: ✓ OK, ! Bør sjekkes, ✕ Må følges opp.":
    "IT mode. Checks this machine's protection right now. Every check has a symbol and a word: ✓ OK, ! Should be checked, ✕ Must be followed up.",
  "Slik holder du deg trygg": "How to stay safe",
  "Ta alltid ut kortet når du går fra maskinen. Da låses skjermen med en gang.":
    "Always remove your card when you leave the machine. The screen locks at once.",
  "Ekte helsetjenester ber aldri om passord, PIN eller BankID på e-post.": "Real health services never ask for passwords, PINs or BankID by email.",
  "E-post merket": "Email marked",
  ": ikke svar, trykk «Rapporter».": ": don't reply, press \"Report\".",
  "Del pasientbilder bare gjennom Post, aldri på vanlig e-post eller minnepinne.": "Share patient images through Mail only, never by ordinary email or USB stick.",
  "✓ Alt er i orden. Maskinen er beskyttet.": "✓ All is well. The machine is protected.",
  "OK": "OK",
  "Bør sjekkes": "Should be checked",
  "Må følges opp": "Must be followed up",
  "Info": "Info",
  "Brannmur": "Firewall",
  "USB-lås": "USB lock",
  "Øktvakt": "Session guard",
  "Sikkerhetslogg": "Security log",
  "Sikkerhetsoppdateringer": "Security updates",
  "Kjøring av programmer fra hjemmemappen": "Running programs from the home folder",
  "Virusbeskyttelse": "Virus protection",
  "Kjernebeskyttelse": "Kernel protection",
  "VPN til helsenettet": "VPN to the health network",
  "Nødtilgangsrapporter": "Emergency access reports",
  "Medisinsk USB-utstyr": "Medical USB devices",
  "Maskinsertifikat (TPM) og WLAN": "Machine certificate (TPM) and Wi-Fi",
  "Svartid journalsystem": "Record system response time",
  "Revisjonslogg": "Audit log",
  "Revisjonskjede": "Audit chain",
  "Arbeidssted": "Workplace",
  "Brannmuren kjører ikke. Kontakt IT.": "The firewall is not running. Contact IT.",
  "USB-låsen kjører ikke. Kontakt IT.": "The USB lock is not running. Contact IT.",
  "Øktvakten kjører ikke. Kontakt IT.": "The session guard is not running. Contact IT.",
  "Sikkerhetsloggen kjører ikke.": "The security log is not running.",
  "Automatiske oppdateringer er av.": "Automatic updates are off.",
  "Hjemmemappen er ikke låst for programkjøring.": "The home folder is not locked against running programs.",
  "Virusskanneren kjører ikke. Vedlegg blir merket «ikke virusskannet».": "The virus scanner is not running. Attachments are marked \"not virus scanned\".",
  "Kjernelåsen (lockdown) er ikke på.": "Kernel lockdown is not on.",
  "AppArmor er ikke slått på.": "AppArmor is not switched on.",
  "Ikke satt opp ennå. Krever avtale med Norsk helsenett eller IT-avdelingen.": "Not set up yet. Requires an agreement with Norsk helsenett or the IT department.",
  "Alle nødtilganger er forklart innen fristen.": "Every emergency access is explained within the deadline.",
  "Får ikke kontakt med innloggingstjenesten.": "Cannot reach the login service.",
  "Maskinen har ingen TPM 2.0. Bruk kablet nett eller VPN.": "The machine has no TPM 2.0. Use a wired network or VPN.",
  "Loggene er beskyttet med nøkler som byttes for hver linje. Ankrene er flyttet bort fra maskinen.":
    "The logs are protected with keys that change for every line. The anchors are moved off the machine.",
  "Loggkjeden var hel da Medicus startet.": "The log chain was intact when Medicus started.",
  "Ingen kall til journalsystemet siden start ennå.": "No calls to the record system since start yet.",

  // Helsenorge simulator
  "Innbyggerportal (simulert)": "Citizen portal (simulated)",
  "Innbyggerportal": "Citizen portal",
  "Slik ser pasienten det på Helsenorge – simulert": "How the patient sees it on Helsenorge – simulated",
  "Simulering med syntetiske testpersoner. Ikke koblet til ekte Helsenorge.": "Simulation with synthetic test people. Not connected to the real Helsenorge.",
  "Logg inn (simulert BankID)": "Log in (simulated BankID)",
  "Velg en syntetisk testperson.": "Pick a synthetic test person.",
  "Hvem har sett journalen min": "Who has seen my record",
  "Resepter": "Prescriptions",
  "Besøk og notater": "Visits and notes",
  "Utleveringer til myndigheter": "Disclosures to authorities",
  "Ingen har åpnet journalen din.": "Nobody has opened your record.",
  "Nødtilgang blir alltid kontrollert i etterkant.": "Emergency access is always reviewed afterwards.",
  "Du har ingen resepter.": "You have no prescriptions.",
  "Ingen registrerte besøk.": "No recorded visits.",
  "Opplysninger utlevert med lovhjemmel, etter vurdering hos virksomheten.": "Information disclosed under a legal basis, after assessment by the provider.",
  "Ingen opplysninger er utlevert.": "No information has been disclosed.",

  // Disclosure simulator
  "Utleveringsforespørsler (simulert)": "Disclosure requests (simulated)",
  "Utlevering av helseopplysninger": "Disclosure of health information",
  "Forespørsler fra myndigheter – vurderes alltid av et menneske før noe utleveres": "Requests from authorities – always assessed by a person before anything is disclosed",
  "Simulering. Lovhjemlene er eksempler og må kvalitetssikres juridisk.": "Simulation. The legal bases are examples and must be checked by a lawyer.",
  "Virksomheten: behandle": "Provider: handle",
  "Myndighet: ny forespørsel": "Authority: new request",
  "Ny forespørsel": "New request",
  "Helsepersonell har taushetsplikt. Forespørselen må ha gyldig lovhjemmel og et konkret formål, og ber bare om de opplysningene som er nødvendige.":
    "Health personnel have a duty of confidentiality. The request must have a valid legal basis and a specific purpose, and ask only for the information that is needed.",
  "Type myndighet": "Type of authority",
  "Myndighet og kontor": "Authority and office",
  "F.eks. Testby politistasjon": "E.g. Testby police station",
  "Saksbehandler og kontaktinformasjon": "Case officer and contact details",
  "11 siffer": "11 digits",
  "Lovhjemmel (bare de som gjelder for denne myndigheten)": "Legal basis (only those that apply to this authority)",
  "Formål og begrunnelse": "Purpose and reasons",
  "Hvilke opplysninger (minst mulig)": "Which information (as little as possible)",
  "Tidsrom (valgfritt, f.eks. 2026-06 eller 2026-06-18)": "Period (optional, e.g. 2026-06 or 2026-06-18)",
  "Send forespørsel": "Send request",
  "Til behandling": "Pending",
  "Godkjent": "Approved",
  "Avslått": "Refused",
  "Pasienten er varslet på Helsenorge.": "The patient is notified on Helsenorge.",
  "Varsel til pasienten er utsatt. Hjemmel:": "Notifying the patient is postponed. Legal basis:",
  "Begrunnelse for vedtaket": "Reasons for the decision",
  "Behandlet av": "Handled by",
  "Navn og stilling (behandlingsansvarlig eller ansvarlig helsepersonell)": "Name and position (controller or responsible clinician)",
  "Varsle pasienten på Helsenorge": "Notify the patient on Helsenorge",
  "Hjemmel for å utsette varsel (bare hvis varsel ikke sendes)": "Legal basis for postponing the notice (only if no notice is sent)",
  "Godkjenn utlevering": "Approve disclosure",
  "Avslå": "Refuse",
  "Ingen forespørsler.": "No requests.",
  "Pasient:": "Patient:",
  "Hjemmel:": "Legal basis:",
  "Ber om:": "Asks for:",
  "Kontakter og notater": "Contacts and notes",
  // Authorities and legal bases (Norwegian law; the act and section names are kept)
  "Politiet / påtalemyndigheten": "Police / prosecuting authority",
  "Domstol / barneverns- og helsenemnda": "Court / child welfare and health board",
  "Barnevernstjenesten": "Child welfare service",
  "Statens helsetilsyn / Statsforvalteren": "Norwegian Board of Health Supervision / County Governor",
  "Kommunens helse- og omsorgstjeneste": "Municipal health and care service",
  "Smittevernmyndighet (kommuneoverlege, FHI)": "Infection control authority (municipal chief medical officer, NIPH)",
  "Utlendingsmyndighetene": "Immigration authorities",
  "Annen myndighet eller virksomhet": "Other authority or organisation",
  "Pasientens samtykke (helsepersonelloven § 22)": "The patient's consent (helsepersonelloven § 22)",
  "Helsepersonelloven § 31 (avverge alvorlig skade på person eller eiendom)": "Helsepersonelloven § 31 (preventing serious harm to people or property)",
  "Helsepersonelloven § 23 nr. 4 (tungtveiende private eller offentlige interesser)": "Helsepersonelloven § 23 no. 4 (weighty private or public interests)",
  "Annen uttrykkelig lovhjemmel (helsepersonelloven § 23 nr. 5) – oppgi paragraf i formål":
    "Other explicit legal basis (helsepersonelloven § 23 no. 5) – give the section under purpose",
  "Fritak fra taushetsplikt gitt av Statsforvalteren (tvisteloven § 22-5)": "Release from confidentiality by the County Governor (tvisteloven § 22-5)",
  "Vitneplikt for barneverns- og helsenemnda (barnevernsloven § 13-4)": "Duty to testify before the child welfare and health board (barnevernsloven § 13-4)",
  "Pålegg fra barnevernstjenesten (helsepersonelloven § 33, barnevernsloven § 13-2)": "Order from the child welfare service (helsepersonelloven § 33, barnevernsloven § 13-2)",
  "Nødvendige opplysninger for krav om eller kontroll av ytelse (folketrygdloven § 21-4)": "Information needed for a claim or check of a benefit (folketrygdloven § 21-4)",
  "Tilsynssak (helsepersonelloven § 30, helsetilsynsloven § 7)": "Supervision case (helsepersonelloven § 30, helsetilsynsloven § 7)",
  "Pålegg fra kommunen i saker etter helse- og omsorgstjenesteloven (helsepersonelloven § 32)":
    "Order from the municipality in cases under the health and care services act (helsepersonelloven § 32)",
  "Opplysningsplikt ved allmennfarlig smittsom sykdom (smittevernloven §§ 2-2 og 2-3)": "Duty to report a dangerous communicable disease (smittevernloven §§ 2-2 and 2-3)",
  "Utvisningssak for særskilt sanksjonert utlending (helsepersonelloven § 29 d)": "Expulsion case for a specially sanctioned foreign national (helsepersonelloven § 29 d)",
  "Politiet kan ikke kreve journalen bare fordi det etterforsker en sak. Leger og sykepleiere har vitneforbud (straffeprosessloven § 119), og journaler kan som hovedregel ikke beslaglegges (straffeprosessloven § 204).":
    "The police cannot demand the record just because they are investigating a case. Doctors and nurses may not testify (straffeprosessloven § 119), and records can as a rule not be seized (straffeprosessloven § 204).",
  "Vitneforbudet i straffeprosessloven § 119 kan bare oppheves med pasientens samtykke.": "The ban on testifying in straffeprosessloven § 119 can only be lifted with the patient's consent.",
  "Barnevernet må konkretisere hvilke opplysninger det trenger, og kan ikke kreve hele journalen.": "The child welfare service must specify the information it needs, and cannot demand the whole record.",
  "Gjelder bare opplysninger som er nødvendige for den konkrete ytelsen.": "Covers only the information needed for the specific benefit.",
  "Tilsynsmyndigheten har rett til innsyn i tilsynssaker uten hinder av taushetsplikt.": "The supervisory authority has a right of access in supervision cases notwithstanding confidentiality.",
  "Gjelder bare opplysninger som trengs for smittevernet.": "Covers only the information needed for infection control.",
  "For eksempel Skatteetaten, arbeidsgiver eller forsikringsselskap. Uten samtykke eller en uttrykkelig lovhjemmel får de ingen helseopplysninger.":
    "For example the tax administration, an employer or an insurer. Without consent or an explicit legal basis they get no health information.",
};

// Text with numbers or names in it: [pattern, English]. $1, $2 … are kept from the Norwegian.
const RULES = [
  [/^Feil PIN\. 1 forsøk igjen\.$/, "Wrong PIN. 1 try left."],
  [/^Feil PIN\. (\d) forsøk igjen\.$/, "Wrong PIN. $1 tries left."],
  [/^Velkommen, (.+)$/, "Welcome, $1"],
  [/^(\d+) pasienter på listen din, fra (.+?)\.( Det tok ([\d,]+) s\.)? Notatet lagres i pasientens journal når du godkjenner\.$/,
    (m, n, sys, slow, s) => `${n} patients on your list, from ${tr(sys) || sys}.${slow ? ` It took ${s} s.` : ""} The note is saved in the patient's record when you approve.`],
  [/^(.*) Du kan fortsatt skrive notat og kopiere det\.$/, (m, msg) => `${tr(msg) || msg} You can still write a note and copy it.`],
  [/^født (.+)$/, "born $1"],
  [/^Født (.+)$/, "Born $1"],
  [/^fra (\d.+)$/, "since $1"],
  [/^\(tall ikke sagt: (.+)\)$/, "(numbers not said: $1)"],
  [/^⚠ (\d+) setning\(er\) har ikke kilde i samtalen\. Sjekk dem før du godkjenner\.$/,
    "⚠ $1 sentence(s) have no source in the conversation. Check them before you approve."],
  [/^Notatet er skrevet for (.+)\. Vil du virkelig bytte pasient\?$/, "The note is written for $1. Do you really want to change patient?"],
  [/^Fant ikke pasienten fra utkastet igjen: (.+)$/, (m, e) => `Could not find the draft's patient again: ${tr(e) || e}`],
  [/^Notatet er godkjent og lagret i journalen til (.+) \((.+)\)\.$/, (m, p, s) => `The note is approved and saved in ${p}'s record (${tr(s) || s}).`],
  [/^Du har (en nødtilgangsrapport|(\d+) nødtilgangsrapporter) å skrive$/,
    (m, a, n) => n ? `You have ${n} emergency access reports to write` : "You have an emergency access report to write"],
  [/^– frist kl\. (\d\d:\d\d)\.$/, "– due at $1."],
  [/^startet (.+) kl\. (\d\d:\d\d)$/, "started $1 at $2"],
  [/^frist (.+) kl\. (\d\d:\d\d)$/, "due $1 at $2"],
  [/^Situasjon: (.+)\.$/, (m, s) => `Situation: ${tr(s) || s}.`],
  [/^✕ (\d+) ting må følges opp\.$/, "✕ $1 thing(s) must be followed up."],
  [/^! (\d+) ting bør sjekkes\.$/, "! $1 thing(s) should be checked."],
  [/^Median ([\d,]+) s\. 9 av 10 kall tar høyst ([\d,]+) s \((\d+) kall\)\.(.*)$/,
    (m, a, b, n, rest) => `Median ${a} s. 9 in 10 calls take at most ${b} s (${n} calls).${rest ? " " + (tr(rest.trim()) || rest.trim()) : ""}`],
  [/^(\d+) godkjent\(e\)\. Endres med «Medisinsk utstyr \(USB\)» i IT-menyen\.$/,
    "$1 approved. Changed with \"Medical devices (USB)\" in the IT menu."],
  [/^Ukjent arbeidssted \(kontakt IT\)\. Ikke bekreftet ennå: (.*)$/,
    "Unknown workplace (contact IT). Not confirmed yet: the machine certificate is missing or older than the workplace sign-in (make a new one with \"medicus-wlan foresporsel\")."],
  [/^(.+)\. Bekreftet av maskinsertifikatet\.$/, (m, s) => `${tr(s) || s}. Confirmed by the machine certificate.`],
  [/^Pasienten finnes ikke i (.+)\. Registrer pasienten først\.$/, "The patient is not in $1. Register the patient first."],
  [/^Navnet i (.+) er «(.+)»\. Kontroller at det er samme person\.$/, "The name in $1 is \"$2\". Check that it is the same person."],
  [/^Jeg har kontrollert at dette er (.+), født (.+), og vil overføre opplysningene til (.+)\.$/,
    "I have checked that this is $1, born $2, and want to transfer the information to $3."],
  [/^Ferdig: (\d+) notater er lagret i journalen til (.+) \((.+)\)\.$/, "Done: $1 notes are saved in $2's record ($3)."],
  [/^Forespørsel #(\d+) er sendt og venter på behandling\.$/, "Request #$1 is sent and awaits handling."],
  [/^(\d+) forespørsler$/, "$1 requests"],
  [/^Lydfilen er for stor \(over (\d+) MB\)\.$/, "The audio file is too large (over $1 MB)."],
  [/^Feil (\d+)$/, "Error $1"],
  [/^Fra: (.*)$/, "From: $1"],
  [/^Til: (.*)$/, "To: $1"],
  [/^Hjemmel: (.*)$/, "Legal basis: $1"],
  [/^Utlevert: (.*)$/, "Disclosed: $1"],
  [/^Vedtak: (.+)$/, (m, s) => `Decision: ${tr(s) || s}`],
  [/^(.+) – fra (.+)$/, (m, a, b) => `${a} – from ${b}`],
  [/^Forskrevet av$/, "Prescribed by"],
  [/^åpnet (.+)$/, (m, what) => `opened ${tr(what) || what}`],
  [/^(.*)Begrunnelse: (.*)$/, (m, a, b) => `${a}Reason: ${tr(b) || b}`],
];

// Pieces inside longer text (several values joined into one line).
const PIECES = [
  [/Sendt kryptert gjennom helsenettet\./g, "Sent encrypted through the health network."],
  [/, tlf\. /g, ", tel. "],
  [/ · tidsrom /g, " · period "],
  [/\bVurdert av\b/g, "Assessed by"],
];

const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "PRE", "CODE"]);

function tr(text) {
  const key = text.replace(/\s+/g, " ").trim();
  if (!key || !/[A-Za-zÆØÅæøå]/.test(key)) return null;
  if (Object.prototype.hasOwnProperty.call(EN, key)) return EN[key];
  for (const [pattern, english] of RULES) {
    if (pattern.test(key)) return key.replace(pattern, english);
  }
  if (key.includes(" · ")) {  // "Overlege, kardiologi · Oslo universitetssykehus, Ullevål"
    const parts = key.split(" · ").map((part) => tr(part) || part);
    const joined = parts.join(" · ");
    if (joined !== key) return joined;
  }
  let out = key;
  for (const [pattern, english] of PIECES) out = out.replace(pattern, english);
  return out !== key ? out : null;
}

function translateText(node) {
  const english = tr(node.nodeValue);
  if (english == null) return;
  const lead = node.nodeValue.match(/^\s*/)[0];
  const trail = node.nodeValue.match(/\s*$/)[0];
  const value = lead + english + trail;
  if (value !== node.nodeValue) node.nodeValue = value;
}

function skipped(element) {
  for (let e = element; e; e = e.parentElement) {
    if (SKIP.has(e.tagName) || (e.dataset && "noI18n" in e.dataset)) return true;
  }
  return false;
}

function translateElement(element) {
  if (skipped(element)) return;
  for (const name of ["placeholder", "title", "aria-label", "alt"]) {
    const value = element.getAttribute && element.getAttribute(name);
    const english = value && tr(value);
    if (english && english !== value) element.setAttribute(name, english);
  }
  if (element.tagName === "INPUT" && ["button", "submit"].includes(element.type) && element.value) {
    const english = tr(element.value);
    if (english && english !== element.value) element.value = english;
  }
}

function translateTree(root) {
  if (root.nodeType === Node.TEXT_NODE) {
    if (!skipped(root.parentElement)) translateText(root);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE || skipped(root)) return;
  translateElement(root);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === Node.ELEMENT_NODE && SKIP.has(n.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) translateText(n);
    else translateElement(n);
  }
}

function languageButton() {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "lang-switch";
  button.dataset.noI18n = "";
  button.lang = LANG === "en" ? "nb" : "en";
  button.textContent = LANG === "en" ? "Norsk" : "English";
  button.setAttribute("aria-label", LANG === "en" ? "Bytt til norsk" : "Switch to English");
  button.addEventListener("click", () => {
    try { localStorage.setItem("medicus_lang", LANG === "en" ? "nb" : "en"); } catch (e) { /* not kept */ }
    location.reload();
  });
  const bar = document.querySelector(".topbar, body > header");
  if (bar) bar.append(button);
  else { button.classList.add("floating"); document.body.append(button); }
}

const style = document.createElement("style");
style.textContent = `.lang-switch { margin-left: auto; font: inherit; font-size: 0.85rem; font-weight: 600; padding: 4px 12px;
  border-radius: 99px; border: 1px solid rgba(255,255,255,0.6); background: transparent; color: inherit; cursor: pointer; }
  .topbar .who + .lang-switch { margin-left: 0; }
  .lang-switch.floating { position: fixed; right: 12px; bottom: 12px; background: #0f4f2f; color: #fff; z-index: 10; }`;
document.head.append(style);

if (LANG === "en") {
  document.documentElement.lang = "en";
  const dialogs = { alert: window.alert, confirm: window.confirm };
  window.alert = (message) => dialogs.alert.call(window, translateMessage(message));
  window.confirm = (message) => dialogs.confirm.call(window, translateMessage(message));
  new MutationObserver((changes) => {
    for (const change of changes) {
      if (change.type === "characterData") translateTree(change.target);
      else if (change.type === "attributes") translateElement(change.target);
      else change.addedNodes.forEach(translateTree);
    }
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["placeholder", "title", "aria-label"] });
}

function translateMessage(message) {
  return String(message).split("\n").map((line) => (line.trim() ? tr(line) || line : line)).join("\n");
}

document.addEventListener("DOMContentLoaded", () => {
  if (LANG === "en") {
    translateTree(document.body);
    document.title = tr(document.title) || document.title;
  }
  languageButton();
});
