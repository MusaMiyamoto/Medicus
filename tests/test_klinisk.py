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
