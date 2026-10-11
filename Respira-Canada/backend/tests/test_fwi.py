import pytest

from app.science import fwi


def test_van_wagner_pickett_reference_day():
    # First day of the standard test set in Van Wagner & Pickett (1985).
    r = fwi.calc_fwi_day(temp=17, rh=42, wind=25, rain=0, month=4).rounded()
    assert r["ffmc"] == 87.7
    assert r["dmc"] == 8.5
    assert r["dc"] == 19.0
    assert r["isi"] == 10.9
    assert r["bui"] == 8.5
    assert r["fwi"] == 10.1


def test_rain_wets_fuels():
    dry = fwi.calc_ffmc(20, 30, 10, 0, 90)
    wet = fwi.calc_ffmc(20, 30, 10, 15, 90)
    assert wet < dry
    assert fwi.calc_dc(20, 25, 7, 400) < fwi.calc_dc(20, 0, 7, 400)


def test_moisture_round_trip():
    # The two FF-scale conversions are approximate inverses by design.
    for code in (60, 85, 92.5, 99):
        assert fwi.moisture_to_ffmc(fwi.ffmc_to_moisture(code)) == pytest.approx(code, abs=0.1)


def test_complete_indices_fills_missing():
    out = fwi.complete_indices(ffmc=88, dmc=30, dc=400, wind=12)
    assert out["isi"] == pytest.approx(fwi.calc_isi(88, 12))
    assert out["bui"] == pytest.approx(fwi.calc_bui(30, 400))
    assert out["fwi"] == pytest.approx(fwi.calc_fwi(out["isi"], out["bui"]))


def test_complete_indices_winter_station_stays_empty():
    out = fwi.complete_indices(ffmc=None, dmc=None, dc=None, wind=10)
    assert out["fwi"] is None and out["isi"] is None
