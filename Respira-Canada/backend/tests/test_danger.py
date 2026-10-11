from app.science.danger import aqhi_category, fwi_danger_class, fwi_to_score, score_to_level


def test_fwi_classes_match_cwfis_legend():
    assert fwi_danger_class(5) == "LOW"
    assert fwi_danger_class(6) == "MODERATE"
    assert fwi_danger_class(15) == "MODERATE"
    assert fwi_danger_class(16) == "HIGH"
    assert fwi_danger_class(22) == "HIGH"
    assert fwi_danger_class(23) == "VERY HIGH"
    assert fwi_danger_class(29) == "VERY HIGH"
    assert fwi_danger_class(30) == "EXTREME"
    assert fwi_danger_class(None) is None


def test_score_level_always_agrees_with_fwi_class():
    for tenth in range(0, 800):
        v = tenth / 10
        assert score_to_level(fwi_to_score(v)) == fwi_danger_class(v), v


def test_score_is_monotonic_and_capped():
    scores = [fwi_to_score(v / 4) for v in range(0, 400)]
    assert scores == sorted(scores)
    assert fwi_to_score(500) == 100.0
    assert fwi_to_score(0) == 0.0


def test_aqhi_categories():
    assert [aqhi_category(v) for v in (1, 3, 4, 6, 7, 10, 11)] == [
        "LOW", "LOW", "MODERATE", "MODERATE", "HIGH", "HIGH", "VERY HIGH"]
