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

# Norwegian-owned news, so staff can follow the news at work. Ads and trackers from other companies
# stay blocked, because only these domains (and the image servers below) get through.
NEWS = [
    ("nrk.no", "NRK", "Nyheter, radio og TV"),
    ("ntb.no", "NTB", "Nyhetsbyrået"),
    ("vg.no", "VG", "Nyheter"),
    ("aftenposten.no", "Aftenposten", "Nyheter"),
    ("nettavisen.no", "Nettavisen", "Nyheter"),
    ("e24.no", "E24", "Økonomi"),
    ("bt.no", "Bergens Tidende", "Nyheter fra Vestland"),
    ("aftenbladet.no", "Stavanger Aftenblad", "Nyheter fra Rogaland"),
    ("adressa.no", "Adresseavisen", "Nyheter fra Trøndelag"),
    ("nordlys.no", "Nordlys", "Nyheter fra Nord-Norge"),
    ("tidsskriftet.no", "Tidsskrift for Den norske legeforening", "Medisinsk fagtidsskrift"),
    ("sykepleien.no", "Sykepleien", "Fagtidsskrift for sykepleiere"),
    ("legeforeningen.no", "Legeforeningen", "Nyheter for leger"),
]

# The news groups' own image and content servers. They can't be opened as pages; the web filter
# only lets the news sites load pictures and page code from them. Ad, tracking and video
# services the sites also use (Google, Microsoft, OneTrust, JW Player ...) are not here.
SUPPORT = [
    "vgc.no", "sacdn.no", "esm.schibsted.tech", "images.stream.schibsted.media",  # Schibsted
    "acdn.no", "api.no",                                                         # Amedia
    "polarismedia.no",                                                           # Polaris Media
]
# Not here: Dagens Næringsliv. dn.no sends every visitor through a foreign sign-in service
# (zephr.com) first, so it can't be opened without that company seeing each visit.

GROUPS = [("Helse", HEALTH), ("Offentlige tjenester", GOVERNMENT), ("Nyheter", NEWS)]
SITES = HEALTH + GOVERNMENT + NEWS


def proxy_filter() -> str:
    """tinyproxy filter (extended regex), one line per domain, matching the domain and its subdomains."""
    domains = [domain for domain, _, _ in SITES] + SUPPORT
    return "".join(f"^(.*\\.)?{re.escape(domain)}$\n" for domain in domains)
