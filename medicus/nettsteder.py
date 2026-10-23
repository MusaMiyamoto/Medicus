"""Websites Medicus Nettleser may open. Everything else is blocked.

This one list is used for three things, so they can never disagree:
  - the start page of Medicus Nettleser (/nettsteder)
  - the web filter (tinyproxy) that the browser's traffic goes through
  - the browser's own allowlist (Firefox enterprise policy)
"""

import re

SITES = [
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
    ("lovdata.no", "Lovdata", "Lover og forskrifter"),
]


def proxy_filter() -> str:
    """tinyproxy filter (extended regex), one line per site, matching the site and its subdomains."""
    return "".join(f"^(.*\\.)?{re.escape(domain)}$\n" for domain, _, _ in SITES)


def firefox_exceptions() -> list[str]:
    return [f"https://*.{domain}/*" for domain, _, _ in SITES]
