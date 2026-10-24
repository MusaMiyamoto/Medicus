"""Clinical scores in Kalkulator. Reference values worked out by hand from the published formulas."""

import pytest

from kalkulator import klinisk
from kalkulator.klinisk import StrokeRisk


@pytest.mark.parametrize("weight, height, value, group", [
    (80, 180, 24.7, "Normalvekt"), (50, 170, 17.3, "Undervekt"), (95, 175, 31.0, "Fedme grad 1"),
    (130, 170, 45.0, "Fedme grad 3"),
])
def test_bmi(weight, height, value, group):
    assert klinisk.bmi(weight, height) == (value, group)


@pytest.mark.parametrize("creatinine, age, female, value", [
    (88.4, 60, False, 86),       # 1,0 mg/dL
    (0.8 * 88.4, 50, True, 90),  # 0,8 mg/dL
    (61.88, 40, True, 112),      # 0,7 mg/dL: exactly κ for women, so only age and sex count
    (300, 80, False, 18),
])
def test_egfr_ckd_epi_2021(creatinine, age, female, value):
    assert klinisk.egfr(creatinine, age, female)[0] == value


def test_egfr_stages():
    assert klinisk.egfr(300, 80, False)[1].startswith("G4")
    assert klinisk.egfr(60, 30, False)[1].startswith("G1")


@pytest.mark.parametrize("args", [(5, 50, False), (88, 10, True), (88, 130, False)])
def test_egfr_refuses_impossible_values_and_children(args):
    with pytest.raises(klinisk.ScoreError):
        klinisk.egfr(*args)


def test_cha2ds2_vasc_points():
    assert klinisk.cha2ds2_vasc(StrokeRisk(age=50)) == 0
    assert klinisk.cha2ds2_vasc(StrokeRisk(age=50, female=True)) == 1
    assert klinisk.cha2ds2_vasc(StrokeRisk(age=70)) == 1
    assert klinisk.cha2ds2_vasc(StrokeRisk(age=75)) == 2
    everything = StrokeRisk(True, True, True, True, True, 80, True)
    assert klinisk.cha2ds2_vasc(everything) == 9 and klinisk.cha2ds2_va(everything) == 8


def test_bad_input_is_refused():
    with pytest.raises(klinisk.ScoreError):
        klinisk.bmi(80, 18)
    with pytest.raises(klinisk.ScoreError):
        klinisk.felleskatalogen("   ")


def test_felleskatalogen_search_is_encoded():
    assert klinisk.felleskatalogen("apixaban 5 mg&x") == \
        "https://www.felleskatalogen.no/medisin/sok?sokord=apixaban%205%20mg%26x"


# --- The second set: reference values worked out by hand from the published formulas ---

def test_cockcroft_gault():
    assert klinisk.cockcroft_gault(88.4, 60, 60, True) == 57    # (80 × 60) / 72 × 0,85
    assert klinisk.cockcroft_gault(100, 40, 70, False) == 86    # 7000 / (72 × 1,131)
    with pytest.raises(klinisk.ScoreError):
        klinisk.cockcroft_gault(100, 40, 5, False)


def test_corrected_calcium():
    assert klinisk.corrected_calcium(2.10, 30) == 2.30
    assert klinisk.corrected_calcium(2.40, 40) == 2.40
    assert klinisk.corrected_calcium(2.50, 45) == 2.40


def test_qtc():
    assert klinisk.qtc(400, 60) == (400, 400)       # RR 1 s: no correction
    assert klinisk.qtc(400, 100) == (516, 474)      # Bazett overcorrects at high heart rate
    assert klinisk.qtc_text(510, None).startswith("Markert")
    assert klinisk.qtc_text(455, True) == "Innenfor normalområdet"
    assert klinisk.qtc_text(455, False).startswith("Forlenget")
    assert "Velg kjønn" in klinisk.qtc_text(455, None)


def test_gcs():
    assert klinisk.gcs(4, 5, 6) == (15, "Lett (13–15)")
    assert klinisk.gcs(1, 1, 1) == (3, "Alvorlig (3–8)")
    assert klinisk.gcs(3, 3, 4)[1] == "Moderat (9–12)"
    with pytest.raises(klinisk.ScoreError):
        klinisk.gcs(5, 5, 6)
    assert len(klinisk.GCS_EYES) == 4 and len(klinisk.GCS_VERBAL) == 5 and len(klinisk.GCS_MOTOR) == 6


def test_curb65():
    assert klinisk.curb65(False, 5, 18, 130, 80, 40) == (0, "Lav risiko (0–1)")
    assert klinisk.curb65(True, 8, 32, 85, 50, 70) == (5, "Høy risiko (3–5)")
    assert klinisk.curb65(False, 7, 29, 120, 61, 64)[0] == 0   # limits: urea must be > 7, RR ≥ 30, DBP ≤ 60
    assert klinisk.curb65(False, 7.1, 30, 120, 60, 65)[0] == 4


NORMAL = dict(resp_rate=16, spo2=97, scale2=False, oxygen=False, systolic=120, pulse=70, alert=True, temperature=37)


def test_news2_normal_and_very_ill():
    assert klinisk.news2(**NORMAL)[0] == 0
    total, points, risk = klinisk.news2(26, 90, False, True, 88, 135, False, 39.5)
    assert total == 19 and risk.startswith("Høy") and points["Oksygentilførsel"] == 2


@pytest.mark.parametrize("change, points", [
    ({"resp_rate": 8}, 3), ({"resp_rate": 9}, 1), ({"resp_rate": 20}, 0), ({"resp_rate": 21}, 2), ({"resp_rate": 25}, 3),
    ({"spo2": 91}, 3), ({"spo2": 92}, 2), ({"spo2": 95}, 1), ({"spo2": 96}, 0),
    ({"systolic": 90}, 3), ({"systolic": 100}, 2), ({"systolic": 110}, 1), ({"systolic": 219}, 0), ({"systolic": 220}, 3),
    ({"pulse": 40}, 3), ({"pulse": 50}, 1), ({"pulse": 91}, 1), ({"pulse": 111}, 2), ({"pulse": 131}, 3),
    ({"temperature": 35.0}, 3), ({"temperature": 35.1}, 1), ({"temperature": 38.1}, 1), ({"temperature": 39.1}, 2),
    ({"alert": False}, 3),
])
def test_news2_band_limits(change, points):
    assert klinisk.news2(**{**NORMAL, **change})[0] == points


@pytest.mark.parametrize("spo2, oxygen, points", [
    (83, False, 3), (85, False, 2), (87, False, 1), (90, False, 0), (95, False, 0),  # on air ≥ 88: no points
    (93, True, 1 + 2), (95, True, 2 + 2), (97, True, 3 + 2),                           # high SpO₂ on oxygen is a risk
])
def test_news2_scale_2(spo2, oxygen, points):
    assert klinisk.news2(**{**NORMAL, "spo2": spo2, "scale2": True, "oxygen": oxygen})[0] == points


def test_news2_single_three_is_flagged_even_when_total_is_low():
    assert klinisk.news2(**{**NORMAL, "alert": False})[2].startswith("Lav–middels")


def test_every_calculator_shows_its_source():
    assert set(klinisk.SOURCES) >= {"bmi", "egfr", "cha2ds2", "cg", "ca", "qtc", "gcs", "curb65", "news2"}
    assert "MDR" in klinisk.DECISION_SUPPORT
