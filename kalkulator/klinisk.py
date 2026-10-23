"""Clinical scores: BMI, eGFR (CKD-EPI 2021) and CHA₂DS₂-VASc / CHA₂DS₂-VA, plus Felleskatalogen links.

These only calculate. They never suggest a medicine or a dose: the clinician decides, using the
product information (Felleskatalogen / SPC) and current guidelines.
"""

from dataclasses import dataclass
from urllib.parse import quote

FELLESKATALOGEN = "https://www.felleskatalogen.no/medisin/sok?sokord="
CREATININE_MG_DL = 88.4  # µmol/L per mg/dL


class ScoreError(ValueError):
    pass


def felleskatalogen(term: str) -> str:
    """A search in Felleskatalogen (opens in Nettleser, where felleskatalogen.no is allowed)."""
    term = " ".join(term.split())[:80]
    if not term:
        raise ScoreError("Skriv navnet på legemiddelet.")
    return FELLESKATALOGEN + quote(term)


def _check(value: float, low: float, high: float, what: str) -> float:
    if not low <= value <= high:
        raise ScoreError(f"{what} må være mellom {low:g} og {high:g}.")
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
