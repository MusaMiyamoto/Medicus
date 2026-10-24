"""The Calculator in Norwegian or English.

English when the session was started in English on the login screen (LANG=en_GB…). The calculations
are the same; only the words and the decimal sign change. In English the decimal sign is a point, and
a comma is refused instead of guessed at: "1,500" would mean 1.5 in Norwegian but 1500 in English,
and a clinical calculator must never pick one silently.
"""

import os


def english() -> bool:
    return os.environ.get("LANG", "").startswith("en")


def _(text: str) -> str:
    """The text in the session's language. Text with {} is formatted by the caller after this."""
    return EN.get(text, text) if english() else text


EN = {
    # Window and pages
    "Kalkulator": "Calculator",
    "Volum": "Volume",
    "Volum (µl – l)": "Volume (µl – l)",
    "Vekt": "Weight",
    "Vekt (µg – kg)": "Weight (µg – kg)",
    "Vekt ↔ volum": "Weight ↔ volume",
    "Kliniske skårer": "Clinical scores",
    "Akutt: NEWS2, GCS, CURB-65": "Acute: NEWS2, GCS, CURB-65",
    "Lab og EKG": "Lab and ECG",
    # Calculator and units
    "For eksempel 2,5 × 4": "For example 2.5 × 4",
    "Skriv inn et regnestykke.": "Type a calculation.",
    "Regnestykket er for langt.": "The calculation is too long.",
    "Regnestykket er ikke fullstendig.": "The calculation is not complete.",
    "Bare tall, + − × ÷ og parenteser er tillatt.": "Only numbers, + − × ÷ and parentheses are allowed.",
    "Kan ikke dele på null.": "Cannot divide by zero.",
    "Svaret er for stort.": "The answer is too large.",
    "Skriv inn et tall.": "Type a number.",
    "Bruk bare ett desimaltegn, for eksempel 1,5.": "Use only one decimal sign, for example 1.5.",
    "«{}» er ikke et tall.": "\"{}\" is not a number.",
    "Tallet er for stort.": "The number is too large.",
    "Mengden kan ikke være negativ.": "The amount cannot be negative.",
    "Tettheten må være større enn 0.": "The density must be greater than 0.",
    "Tettheten virker urimelig høy. Sjekk tallet (g/ml).": "The density seems unreasonably high. Check the number (g/ml).",
    "Velg én vektenhet og én volumenhet.": "Choose one weight unit and one volume unit.",
    "mikroliter": "microlitre", "milliliter": "millilitre", "centiliter": "centilitre", "desiliter": "decilitre",
    "liter": "litre", "teskje à 5 ml": "teaspoon of 5 ml", "spiseskje à 15 ml": "tablespoon of 15 ml",
    "mikrogram": "microgram", "milligram": "milligram", "gram": "gram", "hektogram": "hectogram",
    "kilogram": "kilogram", "ts": "tsp", "ss": "tbsp",
    "Vann": "Water", "Blod": "Blood", "Natriumklorid 0,9 %": "Sodium chloride 0.9 %", "Glukose 5 %": "Glucose 5 %",
    "Morsmelk / melk": "Breast milk / milk", "Etanol 70 % (desinfeksjon)": "Ethanol 70 % (disinfection)",
    "Etanol (ren sprit)": "Ethanol (pure)", "Olivenolje": "Olive oil", "Egendefinert tetthet": "Custom density",
    "egendefinert tetthet": "custom density",
    "Ikke bruk til legemiddeldosering. Bruk alltid preparatomtalen (SPC) og gjeldende rutiner.\n"
    "Omregningen gjelder bare når tettheten er riktig.":
        "Do not use for medicine dosing. Always use the product information (SPC) and current procedures.\n"
        "The conversion is only right when the density is right.",
    "For eksempel 250": "For example 250",
    "For eksempel 500": "For example 500",
    "g/ml, for eksempel 1,2": "g/ml, for example 1.2",
    "Mengde": "Amount",
    "Stoff": "Substance",
    "Tetthet (g/ml)": "Density (g/ml)",
    "{} (ca. {} g/ml)": "{} (approx. {} g/ml)",
    "{} {}, beregnet med tetthet {} g/ml ({}).": "{} {}, calculated with a density of {} g/ml ({}).",
    # Clinical scores: the page
    "Velg …": "Choose …",
    "Fyll inn {}.": "Fill in {}.",
    "Velg {}.": "Choose {}.",
    "Pasient": "Patient",
    "Alder (år)": "Age (years)",
    "Kjønn": "Sex",
    "Kvinne": "Female",
    "Mann": "Male",
    "Alder og kjønn brukes av alle skårene på denne siden.": "Age and sex are used by every score on this page.",
    "Vekt (kg)": "Weight (kg)",
    "Høyde (cm)": "Height (cm)",
    "Kreatinin (µmol/L)": "Creatinine (µmol/L)",
    "CHA₂DS₂-VASc (hjerneslagrisiko ved atrieflimmer)": "CHA₂DS₂-VASc (stroke risk in atrial fibrillation)",
    "Hjertesvikt (C)": "Heart failure (C)",
    "Hypertensjon (H)": "Hypertension (H)",
    "Diabetes (D)": "Diabetes (D)",
    "Hjerneslag, TIA eller tromboemboli (S₂, 2 poeng)": "Stroke, TIA or thromboembolism (S₂, 2 points)",
    "Karsykdom: hjerteinfarkt, perifer arteriesykdom, aortaplakk (V)":
        "Vascular disease: heart attack, peripheral artery disease, aortic plaque (V)",
    "Jeg har vurdert alle punktene over for denne pasienten": "I have assessed every item above for this patient",
    "Gå gjennom alle punktene, og kryss av for at du har vurdert dem.": "Go through every item, and tick that you have assessed them.",
    "Legemiddel, for eksempel apixaban": "Medicine, for example apixaban",
    "Slå opp": "Look up",
    "Åpnet i Nettleser.": "Opened in Browser.",
    "vekt": "weight", "høyde": "height", "kreatinin": "creatinine", "alder": "age", "kjønn": "sex",
    "BMI {} kg/m² · {}": "BMI {} kg/m² · {}",
    "eGFR {} ml/min/1,73 m² · {}": "eGFR {} ml/min/1.73 m² · {}",
    "CHA₂DS₂-VASc {} poeng · CHA₂DS₂-VA {} poeng (ESC 2024 bruker CHA₂DS₂-VA, uten kjønn)":
        "CHA₂DS₂-VASc {} points · CHA₂DS₂-VA {} points (ESC 2024 uses CHA₂DS₂-VA, without sex)",
    "Skriv navnet på legemiddelet.": "Type the name of the medicine.",
    "{} må være mellom {} og {}.": "{} must be between {} and {}.",
    # Acute
    "NEWS2 (tidlig varsling ved forverring)": "NEWS2 (early warning of deterioration)",
    "Respirasjonsfrekvens (/min)": "Respiratory rate (/min)",
    "SpO₂ (%)": "SpO₂ (%)",
    "SpO₂-skala": "SpO₂ scale",
    "Skala 1 (vanlig)": "Scale 1 (usual)",
    "Skala 2 (mål 88–92 %, bestemt av lege)": "Scale 2 (target 88–92 %, decided by a doctor)",
    "Luft eller oksygen": "Air or oxygen",
    "Romluft": "Room air",
    "Får oksygen": "On oxygen",
    "Systolisk blodtrykk (mmHg)": "Systolic blood pressure (mmHg)",
    "Puls (/min)": "Pulse (/min)",
    "Bevissthet": "Consciousness",
    "Våken (A)": "Alert (A)",
    "Ny forvirring, reagerer bare på tiltale, smerte, eller ingen respons (CVPU)":
        "New confusion, responds only to voice, to pain, or not at all (CVPU)",
    "Temperatur (°C)": "Temperature (°C)",
    "Øyeåpning": "Eye opening",
    "Verbal respons": "Verbal response",
    "Motorisk respons": "Motor response",
    "CURB-65 (alvorlighet ved lungebetennelse)": "CURB-65 (severity of pneumonia)",
    "Ny forvirring": "New confusion",
    "Nei": "No",
    "Ja": "Yes",
    "Urea (mmol/L)": "Urea (mmol/L)",
    "Systolisk blodtrykk": "Systolic blood pressure",
    "Diastolisk blodtrykk": "Diastolic blood pressure",
    "respirasjonsfrekvens": "respiratory rate", "SpO₂": "SpO₂", "luft eller oksygen": "air or oxygen",
    "systolisk blodtrykk": "systolic blood pressure", "diastolisk blodtrykk": "diastolic blood pressure",
    "puls": "pulse", "bevissthet": "consciousness", "temperatur": "temperature", "øyeåpning": "eye opening",
    "verbal respons": "verbal response", "motorisk respons": "motor response",
    "om pasienten er forvirret": "whether the patient is confused", "urea": "urea",
    "NEWS2 {} poeng · {}": "NEWS2 {} points · {}",
    "GCS {} · {}": "GCS {} · {}",
    "CURB-65 {} poeng · {}": "CURB-65 {} points · {}",
    "Respirasjonsfrekvens": "Respiratory rate",
    "Oksygentilførsel": "Supplemental oxygen",
    "Puls": "Pulse",
    "Temperatur": "Temperature",
    "Høy klinisk risiko (7 eller mer): akutt vurdering": "High clinical risk (7 or more): emergency assessment",
    "Middels klinisk risiko (5–6): rask vurdering": "Medium clinical risk (5–6): urgent assessment",
    "Lav–middels risiko: én parameter gir 3 poeng, rask vurdering på posten":
        "Low–medium risk: one parameter scores 3, urgent assessment on the ward",
    "Lav klinisk risiko (0–4)": "Low clinical risk (0–4)",
    "Ingen (1)": "None (1)", "Ved smerte (2)": "To pain (2)", "Ved tiltale (3)": "To voice (3)",
    "Spontant (4)": "Spontaneous (4)", "Uforståelige lyder (2)": "Incomprehensible sounds (2)",
    "Usammenhengende ord (3)": "Inappropriate words (3)", "Forvirret (4)": "Confused (4)",
    "Orientert (5)": "Oriented (5)", "Strekker (2)": "Extension (2)", "Bøyer unormalt (3)": "Abnormal flexion (3)",
    "Trekker unna ved smerte (4)": "Withdraws from pain (4)", "Lokaliserer smerte (5)": "Localises pain (5)",
    "Følger oppfordring (6)": "Obeys commands (6)",
    "Lett (13–15)": "Mild (13–15)", "Moderat (9–12)": "Moderate (9–12)", "Alvorlig (3–8)": "Severe (3–8)",
    "Lav risiko (0–1)": "Low risk (0–1)", "Moderat risiko (2)": "Moderate risk (2)", "Høy risiko (3–5)": "High risk (3–5)",
    # Lab and ECG
    "Kreatininclearance (Cockcroft-Gault), for dosegrenser": "Creatinine clearance (Cockcroft-Gault), for dose limits",
    "Albuminkorrigert kalsium": "Albumin-corrected calcium",
    "Kalsium (mmol/L)": "Calcium (mmol/L)",
    "Albumin (g/L)": "Albumin (g/L)",
    "Kjønn (for grenseverdien)": "Sex (for the limit)",
    "kalsium": "calcium", "albumin": "albumin", "QT": "QT",
    "Kreatininclearance {} ml/min (ikke justert til 1,73 m²)": "Creatinine clearance {} ml/min (not adjusted to 1.73 m²)",
    "Korrigert kalsium {} mmol/L": "Corrected calcium {} mmol/L",
    "{} (vurdert med Fridericia)": "{} (judged on Fridericia)",
    "Markert forlenget (≥ 500 ms)": "Markedly prolonged (≥ 500 ms)",
    "Velg kjønn for grensen for forlenget QTc": "Choose sex for the prolonged-QTc limit",
    "Forlenget (> {} ms)": "Prolonged (> {} ms)",
    "Innenfor normalområdet": "Within the normal range",
    # Classes and stages
    "Undervekt": "Underweight", "Normalvekt": "Normal weight", "Overvekt": "Overweight",
    "Fedme grad 1": "Obesity class 1", "Fedme grad 2": "Obesity class 2", "Fedme grad 3": "Obesity class 3",
    "G1: normal eller høy": "G1: normal or high", "G2: lett nedsatt": "G2: mildly decreased",
    "G3a: lett til moderat nedsatt": "G3a: mildly to moderately decreased",
    "G3b: moderat til alvorlig nedsatt": "G3b: moderately to severely decreased",
    "G4: alvorlig nedsatt": "G4: severely decreased", "G5: nyresvikt": "G5: kidney failure",
    # Sources and the warning
    "Vekt / høyde². Klasser: WHO, voksne.": "Weight / height². Classes: WHO, adults.",
    "CKD-EPI 2021 uten etnisitet (Inker m.fl., NEJM 2021). Sjekk hvilken ligning laboratoriet ditt "
    "rapporterer; mange norske laboratorier oppgir eGFR selv.":
        "CKD-EPI 2021 without ethnicity (Inker et al., NEJM 2021). Check which equation your laboratory "
        "reports; many Norwegian laboratories give eGFR themselves.",
    "CHA₂DS₂-VASc (Lip m.fl., Chest 2010). CHA₂DS₂-VA uten kjønn: ESC-retningslinjene for atrieflimmer 2024.":
        "CHA₂DS₂-VASc (Lip et al., Chest 2010). CHA₂DS₂-VA without sex: the ESC atrial fibrillation guidelines 2024.",
    "Cockcroft-Gault (Nephron 1976): (140 − alder) × vekt × 0,85 (kvinner) / (72 × kreatinin i mg/dL). "
    "Brukes i mange preparatomtaler for dosegrenser.":
        "Cockcroft-Gault (Nephron 1976): (140 − age) × weight × 0.85 (women) / (72 × creatinine in mg/dL). "
        "Used in many product texts for dose limits.",
    "Kalsium + 0,02 × (40 − albumin). Ionisert kalsium er bedre når det kan måles.":
        "Calcium + 0.02 × (40 − albumin). Ionised calcium is better when it can be measured.",
    "Bazett: QT / √RR. Fridericia: QT / ∛RR (RR = 60 / puls, i sekunder).":
        "Bazett: QT / √RR. Fridericia: QT / ∛RR (RR = 60 / pulse, in seconds).",
    "Glasgow Coma Scale (Teasdale og Jennett, Lancet 1974).": "Glasgow Coma Scale (Teasdale and Jennett, Lancet 1974).",
    "CURB-65 (Lim m.fl., Thorax 2003): forvirring, urea > 7, RF ≥ 30, BT < 90/≤ 60, alder ≥ 65.":
        "CURB-65 (Lim et al., Thorax 2003): confusion, urea > 7, RR ≥ 30, BP < 90/≤ 60, age ≥ 65.",
    "NEWS2 (Royal College of Physicians, 2017). Skala 2 bare når lege har bestemt SpO₂-mål 88–92 %.":
        "NEWS2 (Royal College of Physicians, 2017). Scale 2 only when a doctor has set an SpO₂ target of 88–92 %.",
    "Beslutningsstøtte, ikke en beslutning. Kontroller alle verdier, og bruk retningslinjer og "
    "preparatomtale. Må vurderes etter MDR (medisinsk utstyr) før klinisk bruk.":
        "Decision support, not a decision. Check every value, and use guidelines and the product "
        "information. Must be assessed under the MDR (medical devices) before clinical use.",
    # Only in English: a comma is refused, not guessed
    "Bruk punktum som desimaltegn, for eksempel 1.5. Komma er ikke tillatt.":
        "Use a point as the decimal sign, for example 1.5. Commas are not allowed.",
}
