"""Clinical scores: BMI, eGFR (CKD-EPI 2021) and CHA₂DS₂-VASc / CHA₂DS₂-VA, plus Felleskatalogen links.

These only calculate. They never suggest a medicine or a dose: the clinician decides, using the
product information (Felleskatalogen / SPC) and current guidelines.
"""

from dataclasses import dataclass
from urllib.parse import quote

from .sprak import _

FELLESKATALOGEN = "https://www.felleskatalogen.no/medisin/sok?sokord="
CREATININE_MG_DL = 88.4  # µmol/L per mg/dL


class ScoreError(ValueError):
    pass


def felleskatalogen(term: str) -> str:
    """A search in Felleskatalogen (opens in Nettleser, where felleskatalogen.no is allowed)."""
    term = " ".join(term.split())[:80]
    if not term:
        raise ScoreError(_("Skriv navnet på legemiddelet."))
    return FELLESKATALOGEN + quote(term)


def _check(value: float, low: float, high: float, what: str) -> float:
    if not low <= value <= high:
        raise ScoreError(_("{} må være mellom {} og {}.").format(_(what), f"{low:g}", f"{high:g}"))
    return value


# --- BMI ---------------------------------------------------------------------------

BMI_CLASSES = [(18.5, "Undervekt"), (25, "Normalvekt"), (30, "Overvekt"), (35, "Fedme grad 1"),
               (40, "Fedme grad 2"), (float("inf"), "Fedme grad 3")]


def bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    """Body mass index (kg/m²) and the WHO class for adults."""
    weight = _check(weight_kg, 2, 400, "Vekt (kg)")
    height = _check(height_cm, 40, 250, "Høyde (cm)") / 100
    value = weight / height**2
    return round(value, 1), next(name for limit, name in BMI_CLASSES if value < limit)


# --- eGFR, CKD-EPI 2021 (without race) ------------------------------------------------

GFR_STAGES = [(90, "G1: normal eller høy"), (60, "G2: lett nedsatt"), (45, "G3a: lett til moderat nedsatt"),
              (30, "G3b: moderat til alvorlig nedsatt"), (15, "G4: alvorlig nedsatt"), (0, "G5: nyresvikt")]


def egfr(creatinine_umol: float, age: int, female: bool) -> tuple[int, str]:
    """eGFR in ml/min/1,73 m² from creatinine (µmol/L), age and sex. Adults (18+) only.

    CKD-EPI 2021: 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^−1,200 × 0,9938^age × 1,012 (women),
    with Scr in mg/dL, κ = 0,7 (women) / 0,9 (men), α = −0,241 (women) / −0,302 (men).
    """
    scr = _check(creatinine_umol, 10, 3000, "Kreatinin (µmol/L)") / CREATININE_MG_DL
    age = int(_check(age, 18, 120, "Alder (år)"))
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    value = 142 * min(scr / kappa, 1) ** alpha * max(scr / kappa, 1) ** -1.200 * 0.9938**age
    if female:
        value *= 1.012
    value = round(value)
    return value, next(name for limit, name in GFR_STAGES if value >= limit)


# --- CHA₂DS₂-VASc ---------------------------------------------------------------------

@dataclass
class StrokeRisk:
    heart_failure: bool = False      # C   1
    hypertension: bool = False       # H   1
    diabetes: bool = False           # D   1
    stroke_tia: bool = False         # S₂  2  (stroke, TIA or thromboembolism)
    vascular: bool = False           # V   1  (heart attack, peripheral artery disease, aortic plaque)
    age: int = 0                     # A₂  2 if 75+, A 1 if 65–74
    female: bool = False             # Sc  1


def cha2ds2_va(r: StrokeRisk) -> int:
    """CHA₂DS₂-VA: the same without sex, used in the ESC guidelines for atrial fibrillation from 2024."""
    _check(r.age, 18, 120, "Alder (år)")
    age_points = 2 if r.age >= 75 else 1 if r.age >= 65 else 0
    return (r.heart_failure + r.hypertension + r.diabetes + 2 * r.stroke_tia + r.vascular + age_points)


def cha2ds2_vasc(r: StrokeRisk) -> int:
    return cha2ds2_va(r) + r.female


# --- Kidney function for drug doses: Cockcroft-Gault ------------------------------------

def cockcroft_gault(creatinine_umol: float, age: int, weight_kg: float, female: bool) -> int:
    """Creatinine clearance in ml/min (not per 1,73 m²), which many product texts use for dose limits.
    (140 − age) × weight × 0,85 (women) / (72 × creatinine in mg/dL)."""
    scr = _check(creatinine_umol, 10, 3000, "Kreatinin (µmol/L)") / CREATININE_MG_DL
    age = int(_check(age, 18, 120, "Alder (år)"))
    weight = _check(weight_kg, 20, 400, "Vekt (kg)")
    value = (140 - age) * weight / (72 * scr)
    return round(value * 0.85 if female else value)


# --- Corrected calcium ---------------------------------------------------------------------

def corrected_calcium(calcium_mmol: float, albumin_g_l: float) -> float:
    """Albumin-corrected calcium (mmol/L): calcium + 0,02 × (40 − albumin). Ionised calcium is better
    when it can be measured; labs may use a slightly different factor."""
    calcium = _check(calcium_mmol, 0.5, 5, "Kalsium (mmol/L)")
    albumin = _check(albumin_g_l, 5, 70, "Albumin (g/L)")
    return round(calcium + 0.02 * (40 - albumin), 2)


# --- QTc ---------------------------------------------------------------------------------------

def qtc(qt_ms: float, heart_rate: float) -> tuple[int, int]:
    """QT corrected for heart rate, in ms: (Bazett QT/√RR, Fridericia QT/∛RR), RR = 60 / puls seconds.
    Bazett overcorrects at high heart rates; Fridericia is better there."""
    qt = _check(qt_ms, 150, 800, "QT (ms)")
    rr = 60 / _check(heart_rate, 20, 250, "Puls (/min)")
    return round(qt / rr ** 0.5), round(qt / rr ** (1 / 3))


def qtc_text(value: int, female: bool | None) -> str:
    if value >= 500:
        return "Markert forlenget (≥ 500 ms)"
    if female is None:
        return "Velg kjønn for grensen for forlenget QTc"
    limit = 460 if female else 450
    return f"Forlenget (> {limit} ms)" if value > limit else "Innenfor normalområdet"


# --- Glasgow Coma Scale ---------------------------------------------------------------------

GCS_EYES = ["Ingen (1)", "Ved smerte (2)", "Ved tiltale (3)", "Spontant (4)"]
GCS_VERBAL = ["Ingen (1)", "Uforståelige lyder (2)", "Usammenhengende ord (3)", "Forvirret (4)", "Orientert (5)"]
GCS_MOTOR = ["Ingen (1)", "Strekker (2)", "Bøyer unormalt (3)", "Trekker unna ved smerte (4)",
             "Lokaliserer smerte (5)", "Følger oppfordring (6)"]


def gcs(eyes: int, verbal: int, motor: int) -> tuple[int, str]:
    _check(eyes, 1, 4, "Øyeåpning")
    _check(verbal, 1, 5, "Verbal respons")
    _check(motor, 1, 6, "Motorisk respons")
    total = eyes + verbal + motor
    return total, "Lett (13–15)" if total >= 13 else "Moderat (9–12)" if total >= 9 else "Alvorlig (3–8)"


# --- CURB-65 (pneumonia) ----------------------------------------------------------------------

def curb65(confusion: bool, urea_mmol: float, resp_rate: float, systolic: float, diastolic: float,
           age: int) -> tuple[int, str]:
    """Confusion, urea > 7 mmol/L, respiratory rate ≥ 30, systolic < 90 or diastolic ≤ 60, age ≥ 65."""
    _check(urea_mmol, 0.5, 100, "Urea (mmol/L)")
    _check(resp_rate, 3, 80, "Respirasjonsfrekvens")
    _check(systolic, 40, 300, "Systolisk blodtrykk")
    _check(diastolic, 20, 200, "Diastolisk blodtrykk")
    _check(age, 18, 120, "Alder (år)")
    points = (confusion + (urea_mmol > 7) + (resp_rate >= 30) + (systolic < 90 or diastolic <= 60) + (age >= 65))
    risk = "Lav risiko (0–1)" if points <= 1 else "Moderat risiko (2)" if points == 2 else "Høy risiko (3–5)"
    return points, risk


# --- NEWS2 (National Early Warning Score 2, Royal College of Physicians 2017) ------------------

def _band(value: float, bands: list[tuple[float, int]], above: int) -> int:
    """Points for the first band whose upper limit the value is at or below."""
    for upper, points in bands:
        if value <= upper:
            return points
    return above


def news2(resp_rate: float, spo2: float, scale2: bool, oxygen: bool, systolic: float, pulse: float,
          alert: bool, temperature: float) -> tuple[int, dict, str]:
    """NEWS2 total, the points per parameter, and the clinical risk. Scale 2 (SpO₂ target 88–92 %) only
    for patients with hypercapnic respiratory failure, decided by a clinician."""
    _check(resp_rate, 0, 80, "Respirasjonsfrekvens")
    _check(spo2, 50, 100, "SpO₂ (%)")
    _check(systolic, 40, 300, "Systolisk blodtrykk")
    _check(pulse, 20, 250, "Puls")
    _check(temperature, 25, 45, "Temperatur")
    if scale2:
        if spo2 <= 87:
            spo2_points = _band(spo2, [(83, 3), (85, 2), (87, 1)], 0)
        elif spo2 <= 92 or not oxygen:
            spo2_points = 0
        else:
            spo2_points = _band(spo2, [(94, 1), (96, 2)], 3)
    else:
        spo2_points = _band(spo2, [(91, 3), (93, 2), (95, 1)], 0)
    points = {
        "Respirasjonsfrekvens": _band(resp_rate, [(8, 3), (11, 1), (20, 0), (24, 2)], 3),
        "SpO₂": spo2_points,
        "Oksygentilførsel": 2 if oxygen else 0,
        "Systolisk blodtrykk": _band(systolic, [(90, 3), (100, 2), (110, 1), (219, 0)], 3),
        "Puls": _band(pulse, [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2)], 3),
        "Bevissthet": 0 if alert else 3,
        "Temperatur": _band(temperature, [(35.0, 3), (36.0, 1), (38.0, 0), (39.0, 1)], 2),
    }
    total = sum(points.values())
    if total >= 7:
        risk = "Høy klinisk risiko (7 eller mer): akutt vurdering"
    elif total >= 5:
        risk = "Middels klinisk risiko (5–6): rask vurdering"
    elif 3 in points.values():
        risk = "Lav–middels risiko: én parameter gir 3 poeng, rask vurdering på posten"
    else:
        risk = "Lav klinisk risiko (0–4)"
    return total, points, risk


# What each calculator is based on, shown on screen under it. The words here and in the lists above
# stay Norwegian; the window translates them with sprak._ when it shows them.
SOURCES = {
    "bmi": "Vekt / høyde². Klasser: WHO, voksne.",
    "egfr": "CKD-EPI 2021 uten etnisitet (Inker m.fl., NEJM 2021). Sjekk hvilken ligning laboratoriet ditt "
            "rapporterer; mange norske laboratorier oppgir eGFR selv.",
    "cha2ds2": "CHA₂DS₂-VASc (Lip m.fl., Chest 2010). CHA₂DS₂-VA uten kjønn: ESC-retningslinjene for atrieflimmer 2024.",
    "cg": "Cockcroft-Gault (Nephron 1976): (140 − alder) × vekt × 0,85 (kvinner) / (72 × kreatinin i mg/dL). "
          "Brukes i mange preparatomtaler for dosegrenser.",
    "ca": "Kalsium + 0,02 × (40 − albumin). Ionisert kalsium er bedre når det kan måles.",
    "qtc": "Bazett: QT / √RR. Fridericia: QT / ∛RR (RR = 60 / puls, i sekunder).",
    "gcs": "Glasgow Coma Scale (Teasdale og Jennett, Lancet 1974).",
    "curb65": "CURB-65 (Lim m.fl., Thorax 2003): forvirring, urea > 7, RF ≥ 30, BT < 90/≤ 60, alder ≥ 65.",
    "news2": "NEWS2 (Royal College of Physicians, 2017). Skala 2 bare når lege har bestemt SpO₂-mål 88–92 %.",
}
DECISION_SUPPORT = ("Beslutningsstøtte, ikke en beslutning. Kontroller alle verdier, og bruk retningslinjer og "
                    "preparatomtale. Må vurderes etter MDR (medisinsk utstyr) før klinisk bruk.")
