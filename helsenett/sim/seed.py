"""Synthetic test patients. Names are Norwegian placeholder names; numbers are synthetic (month + 80)."""

from ..fnr import make_synthetic

LEGESENTER = "Medicus legesenter (simulert)"
LEGEVAKT = "Testby legevakt (simulert)"
SYKEHUS = "Sykehuset Testby (simulert)"

OLA = make_synthetic(12, 3, 80, 123)
KARI = make_synthetic(4, 7, 58, 211)
SOFIE = make_synthetic(20, 11, 15, 512)
ERIK = make_synthetic(30, 1, 42, 307)


def actor(name, role, org, hpr):
    return {"navn": name, "rolle": role, "virksomhet": org, "hpr": hpr}


BERG = actor("Ingrid Berg", "Lege", LEGESENTER, "999000101")
LIE = actor("Jonas Lie", "Sykepleier", LEGEVAKT, "999000202")
DAHL = actor("Sara Dahl", "Lege", SYKEHUS, "999000404")


def visit(time, org, who, kind, note):
    return {"tid": time, "virksomhet": org, "aktor": who, "type": kind, "notat": note}


def rx(time, who, drug, dose, reason, status="Aktiv"):
    return {"tid": time, "aktor": who, "legemiddel": drug, "dosering": dose, "indikasjon": reason, "status": status}


def access(time, who, reason, what):
    return {"tid": time, "aktor": who, "modus": "normal", "begrunnelse": reason, "hva": what}


def patients() -> dict:
    return {
        OLA: {
            "fnr": OLA, "navn": "Ola Nordmann", "fodt": "1980-03-12", "kjonn": "Mann",
            "fastlege": BERG,
            "allergier": [{"stoff": "Penicillin", "reaksjon": "Anafylaksi", "alvorlighet": "Livstruende"}],
            "tilstander": [{"navn": "Diabetes type 1", "merknad": "Insulinbehandlet. Fare for alvorlig hypoglykemi."}],
            "implantater": [],
            "parorende": [{"navn": "Kari Nordmann", "relasjon": "Ektefelle", "telefon": "400 00 001"}],
            "kontakter": [
                visit("2026-09-02T09:15", LEGESENTER, BERG, "Kontroll",
                      "Diabeteskontroll. HbA1c 58. Justert insulin glargin til 22 E. Ny kontroll om 3 mnd."),
                visit("2026-06-18T23:40", LEGEVAKT, LIE, "Legevakt",
                      "Hypoglykemi, BS 2,1. Gitt glukose. Våken og orientert ved utreise. Fastlege orientert."),
            ],
            "resepter": [
                rx("2026-09-02T09:30", BERG, "Insulin glargin", "22 E subkutant om kvelden", "Diabetes type 1"),
                rx("2026-09-02T09:30", BERG, "Insulin aspart", "Etter skjema til måltider", "Diabetes type 1"),
            ],
            "innsyn": [access("2026-09-02T09:12", BERG, "Konsultasjon", "Journal")],
            "utleveringer": [],
        },
        KARI: {
            "fnr": KARI, "navn": "Kari Nordmann", "fodt": "1958-07-04", "kjonn": "Kvinne",
            "fastlege": BERG,
            "allergier": [{"stoff": "Jodholdig kontrastmiddel", "reaksjon": "Urtikaria og bronkospasme", "alvorlighet": "Alvorlig"}],
            "tilstander": [{"navn": "Atrieflimmer", "merknad": "Antikoagulasjonsbehandling – økt blødningsfare."}],
            "implantater": [{"navn": "Pacemaker", "merknad": "Innsatt 2021. Ikke MR uten avklaring."}],
            "parorende": [{"navn": "Ola Nordmann", "relasjon": "Ektefelle", "telefon": "400 00 002"}],
            "kontakter": [
                visit("2026-08-11T13:00", SYKEHUS, DAHL, "Poliklinikk kardiologi",
                      "Pacemakerkontroll uten anmerkning. Fortsetter warfarin, INR-mål 2–3."),
                visit("2026-07-01T10:20", LEGESENTER, BERG, "Konsultasjon", "INR 2,6. Uendret dosering."),
            ],
            "resepter": [rx("2026-07-01T10:30", BERG, "Warfarin", "Etter INR-skjema", "Atrieflimmer")],
            "innsyn": [access("2026-08-11T12:55", DAHL, "Poliklinisk time", "Journal")],
            "utleveringer": [],
        },
        SOFIE: {
            "fnr": SOFIE, "navn": "Sofie Hansen", "fodt": "2015-11-20", "kjonn": "Jente",
            "fastlege": BERG,
            "allergier": [{"stoff": "Peanøtter", "reaksjon": "Anafylaksi", "alvorlighet": "Livstruende"}],
            "tilstander": [],
            "implantater": [],
            "parorende": [{"navn": "Mona Hansen", "relasjon": "Mor", "telefon": "400 00 003"}],
            "kontakter": [
                visit("2026-05-14T16:05", LEGEVAKT, LIE, "Legevakt",
                      "Allergisk reaksjon etter peanøtter i skolen. Adrenalin gitt av skolen. Observert 4 timer."),
            ],
            "resepter": [rx("2026-05-14T16:30", BERG, "Adrenalin autoinjektor", "0,3 mg i.m. ved anafylaksi", "Peanøttallergi")],
            "innsyn": [],
            "utleveringer": [],
        },
        ERIK: {
            "fnr": ERIK, "navn": "Erik Johansen", "fodt": "1942-01-30", "kjonn": "Mann",
            "fastlege": BERG,
            "allergier": [],
            "tilstander": [
                {"navn": "Malign hypertermi (arvelig disposisjon)",
                 "merknad": "Ikke gi suksameton eller inhalasjonsanestesi."},
                {"navn": "Demens, moderat", "merknad": "Trenger hjelp til å forklare symptomer."},
            ],
            "implantater": [],
            "parorende": [{"navn": "Lise Johansen", "relasjon": "Datter", "telefon": "400 00 004"}],
            "kontakter": [
                visit("2026-10-01T11:00", LEGESENTER, BERG, "Hjemmebesøk", "Stabil. Hjemmesykepleien følger opp medisiner."),
            ],
            "resepter": [
                rx("2026-10-01T11:20", BERG, "Metformin", "500 mg x 2", "Diabetes type 2"),
                rx("2026-10-01T11:20", BERG, "Donepezil", "10 mg om kvelden", "Demens"),
            ],
            "innsyn": [],
            "utleveringer": [],
        },
    }


def requests() -> list:
    return [{
        "id": 1,
        "tid": "2026-10-20T10:00",
        "myndighet": "Politiet (simulert), Testby politistasjon",
        "saksbehandler": "Politiadvokat (simulert)",
        "fnr": OLA,
        "hjemmel": "Rettens kjennelse/beslutning",
        "formal": "Etterforskning av trafikkulykke 18.06.2026. Kjennelse fra Testby tingrett vedlagt.",
        "data": ["Kontakter og notater"],
        "periode": "2026-06-18",
        "status": "Til behandling",
    }]


AMBULANSE = "Ambulansetjenesten (simulert)"
HADDAD = actor("Amir Haddad", "Ambulansearbeider", AMBULANSE, "999000303")
MOE = actor("Per Moe", "Radiolog", SYKEHUS, "999000505")


def addresses() -> list:
    """The address register: everyone you can send to inside the health network."""
    return [{"id": f"hpr:{a['hpr']}", **a} for a in (BERG, LIE, HADDAD, DAHL, MOE)]


def message(time, sender, to, subject, text, fnr="", attachments=()):
    return {"tid": time, "kanal": "helsenett", "fra": sender, "til": [f"hpr:{t['hpr']}" for t in to],
            "emne": subject, "tekst": text, "fnr": fnr, "vedlegg": list(attachments), "lest_av": []}


def external(time, name, address, to, subject, text, attachments=(), reply_to=""):
    return {"tid": time, "kanal": "ekstern", "fra": {"navn": name, "adresse": address, "svar_til": reply_to},
            "til": [f"hpr:{t['hpr']}" for t in to], "emne": subject, "tekst": text, "fnr": "",
            "vedlegg_navn": list(attachments), "vedlegg": [], "lest_av": []}


def mail() -> list:
    """Messages for the demo inbox. Images are attached by the simulator at start-up."""
    return [
        message("2026-10-23T08:05", MOE, [BERG], "Røntgen thorax – Ola Nordmann",
                "Hei. Røntgen thorax tatt i dag, se vedlegg. Ingen fortetninger, normal hjertestørrelse. "
                "Fullstendig svar kommer i journalen.\n\nPer Moe, radiolog", OLA, ["xray"]),
        message("2026-10-22T14:30", DAHL, [BERG], "Epikrise – Kari Nordmann",
                "Pasienten var til pacemakerkontroll. Uendret behandling. Ber fastlege følge opp INR som før.", KARI),
        message("2026-10-21T19:10", MOE, [BERG, DAHL], "MR caput – Erik Johansen",
                "MR caput er gjort, se vedlegg. Moderat atrofi forenlig med kjent demens. Ingen akutte funn.",
                ERIK, ["mr"]),
        external("2026-10-23T07:41", "Helsenorge", "varsel@helsenorge-sikkerhet.com", [BERG],
                 "Kontoen din blir stengt – handling kreves",
                 "Kjære bruker,\n\nVi har oppdaget uvanlig aktivitet. Kontoen din blir stengt innen 24 timer "
                 "hvis du ikke bekrefter identiteten din.\n\nLogg inn med BankID her: "
                 "[https://helsenorge.no/logginn](http://helsen0rge-login.xyz/verify)\n\nMvh Helsenorge",
                 ["Bekreftelse.pdf.exe"]),
        external("2026-10-22T11:02", "Norsk helsenett (NHN) IT-support", "it-support@nhn-no.com", [BERG],
                 "Passordet ditt utløper i dag",
                 "Passordet ditt utløper i dag. Oppdater passord og PIN-kode umiddelbart: http://185.0.2.44/nhn",
                 reply_to="nhn.support@gmail.com"),
        external("2026-10-20T09:15", "Medisinutstyr AS", "salg@medisinutstyr.no", [BERG],
                 "Nye nitrilhansker på lager",
                 "Hei! Vi har fått inn nye nitrilhansker i alle størrelser. Se katalogen: "
                 "https://medisinutstyr.no/katalog\n\nMed vennlig hilsen\nMedisinutstyr AS",
                 ["katalog.pdf"]),
    ]


def state() -> dict:
    return {"pasienter": patients(), "utleveringer": requests(), "adresser": addresses(), "post": mail()}
