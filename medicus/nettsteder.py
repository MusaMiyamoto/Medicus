"""Websites Medicus Nettleser may open. Everything else is blocked.

This one list is used for three things, so they can never disagree:
  - the start page of Medicus Nettleser (/nettsteder)
  - the browser's own allowlist (nettleser/regler.py)
  - the web filter (tinyproxy) that all browser traffic goes through

Each entry also allows its subdomains, so "kommune.no" covers every municipality (oslo.kommune.no …).
"""

import re

HEALTH = [
    ("helsenorge.no", "Helsenorge", "Innbyggertjenester og informasjon om helse"),
    ("felleskatalogen.no", "Felleskatalogen", "Informasjon om legemidler"),
    ("legemiddelhandboka.no", "Norsk legemiddelhåndbok", "Legemidler og behandling"),
    ("helsedirektoratet.no", "Helsedirektoratet", "Nasjonale faglige retningslinjer"),
    ("fhi.no", "Folkehelseinstituttet", "Smittevern og vaksinasjon"),
    ("helsebiblioteket.no", "Helsebiblioteket", "Oppslagsverk for helsepersonell"),
    ("legevakthandboka.no", "Legevakthåndboken", "Akuttmedisin"),
    ("dmp.no", "Direktoratet for medisinske produkter", "Legemidler og medisinsk utstyr"),
    ("helsetilsynet.no", "Statens helsetilsyn", "Tilsyn og veiledere"),
    ("nhn.no", "Norsk helsenett", "Helsenettet og nasjonale e-helsetjenester"),
]

GOVERNMENT = [
    ("regjeringen.no", "Regjeringen", "Departementene og regjeringens arbeid"),
    ("norge.no", "Norge.no", "Veiviser til offentlige tjenester"),
    ("nav.no", "NAV", "Arbeid, trygd og sykmelding"),
    ("skatteetaten.no", "Skatteetaten", "Skatt og folkeregister"),
    ("altinn.no", "Altinn", "Skjema og tjenester for virksomheter"),
    ("idporten.no", "ID-porten", "Innlogging til offentlige tjenester"),
    ("politiet.no", "Politiet", "Politiets tjenester"),
    ("brreg.no", "Brønnøysundregistrene", "Virksomhetsregistre"),
    ("datatilsynet.no", "Datatilsynet", "Personvern"),
    ("digdir.no", "Digitaliseringsdirektoratet", "Digitale fellesløsninger"),
    ("nsm.no", "Nasjonal sikkerhetsmyndighet", "Råd om digital sikkerhet"),
    ("statsforvalteren.no", "Statsforvalteren", "Statens representant i fylkene"),
    ("stortinget.no", "Stortinget", "Lover og vedtak"),
    ("arbeidstilsynet.no", "Arbeidstilsynet", "Arbeidsmiljø"),
    ("dsb.no", "DSB", "Samfunnssikkerhet og beredskap"),
    ("kommune.no", "Kommunene", "Alle kommunenes nettsider"),
    ("lovdata.no", "Lovdata", "Lover og forskrifter"),
]

GROUPS = [("Helse", HEALTH), ("Offentlige tjenester", GOVERNMENT)]
SITES = HEALTH + GOVERNMENT


def proxy_filter() -> str:
    """tinyproxy filter (extended regex), one line per site, matching the site and its subdomains."""
    return "".join(f"^(.*\\.)?{re.escape(domain)}$\n" for domain, _, _ in SITES)
