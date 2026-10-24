"""Which authorities may ask for health information, and on which legal basis.

The main rule is confidentiality (helsepersonelloven § 21). An authority only gets information
when a law says so or the patient consents, and a person always reviews the request first.
Each authority type below lists only the legal bases that apply to it, so for example the tax
office or an employer cannot pick a police or child-welfare provision.

NB: Examples for the simulator, based on helsepersonelloven chapters 5 and 6 and the laws they
refer to. They must be quality-assured by a lawyer before real use.
"""

CONSENT = "Pasientens samtykke (helsepersonelloven § 22)"
OTHER_LAW = "Annen uttrykkelig lovhjemmel (helsepersonelloven § 23 nr. 5) – oppgi paragraf i formål"

AUTHORITIES = [
    {
        "type": "Politiet / påtalemyndigheten",
        "hjemler": [
            CONSENT,
            "Helsepersonelloven § 31 (avverge alvorlig skade på person eller eiendom)",
            "Helsepersonelloven § 23 nr. 4 (tungtveiende private eller offentlige interesser)",
            OTHER_LAW,
        ],
        "merknad": "Politiet kan ikke kreve journalen bare fordi det etterforsker en sak. Leger og "
                   "sykepleiere har vitneforbud (straffeprosessloven § 119), og journaler kan som "
                   "hovedregel ikke beslaglegges (straffeprosessloven § 204).",
    },
    {
        "type": "Domstol / barneverns- og helsenemnda",
        "hjemler": [
            CONSENT,
            "Fritak fra taushetsplikt gitt av Statsforvalteren (tvisteloven § 22-5)",
            "Vitneplikt for barneverns- og helsenemnda (barnevernsloven § 13-4)",
            OTHER_LAW,
        ],
        "merknad": "Vitneforbudet i straffeprosessloven § 119 kan bare oppheves med pasientens samtykke.",
    },
    {
        "type": "Barnevernstjenesten",
        "hjemler": [
            CONSENT,
            "Pålegg fra barnevernstjenesten (helsepersonelloven § 33, barnevernsloven § 13-2)",
        ],
        "merknad": "Barnevernet må konkretisere hvilke opplysninger det trenger, og kan ikke kreve hele journalen.",
    },
    {
        "type": "NAV",
        "hjemler": [
            CONSENT,
            "Nødvendige opplysninger for krav om eller kontroll av ytelse (folketrygdloven § 21-4)",
        ],
        "merknad": "Gjelder bare opplysninger som er nødvendige for den konkrete ytelsen.",
    },
    {
        "type": "Statens helsetilsyn / Statsforvalteren",
        "hjemler": [
            "Tilsynssak (helsepersonelloven § 30, helsetilsynsloven § 7)",
        ],
        "merknad": "Tilsynsmyndigheten har rett til innsyn i tilsynssaker uten hinder av taushetsplikt.",
    },
    {
        "type": "Kommunens helse- og omsorgstjeneste",
        "hjemler": [
            CONSENT,
            "Pålegg fra kommunen i saker etter helse- og omsorgstjenesteloven (helsepersonelloven § 32)",
        ],
        "merknad": "",
    },
    {
        "type": "Smittevernmyndighet (kommuneoverlege, FHI)",
        "hjemler": [
            "Opplysningsplikt ved allmennfarlig smittsom sykdom (smittevernloven §§ 2-2 og 2-3)",
        ],
        "merknad": "Gjelder bare opplysninger som trengs for smittevernet.",
    },
    {
        "type": "Utlendingsmyndighetene",
        "hjemler": [
            "Utvisningssak for særskilt sanksjonert utlending (helsepersonelloven § 29 d)",
        ],
        "merknad": "",
    },
    {
        "type": "Annen myndighet eller virksomhet",
        "hjemler": [CONSENT, OTHER_LAW],
        "merknad": "For eksempel Skatteetaten, arbeidsgiver eller forsikringsselskap. Uten samtykke "
                   "eller en uttrykkelig lovhjemmel får de ingen helseopplysninger.",
    },
]

BY_TYPE = {a["type"]: a for a in AUTHORITIES}


def allowed(authority_type: str, basis: str) -> bool:
    """True only if this kind of authority may use this legal basis."""
    entry = BY_TYPE.get(authority_type)
    return entry is not None and basis in entry["hjemler"]
