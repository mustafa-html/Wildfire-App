from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_regions():
    r = client.get("/api/regions").json()
    assert r["default"] == "AB"
    assert {x["code"] for x in r["regions"]} >= {"AB", "BC", "ON", "CA"}


def test_unknown_region_is_400():
    assert client.get("/api/fire-risk/assessment?region=ZZ").status_code == 400


def test_assessment_alberta():
    r = client.get("/api/fire-risk/assessment?region=AB").json()
    names = [a["station_name"] for a in r["assessments"]]
    assert "KAMLOOPS" not in names                       # BC station filtered out
    assert names[0] == "CALGARY INTL"                    # highest FWI first, '+' cleaned
    assert r["total_stations"] == 3 and r["reporting_fwi"] == 2
    calgary = r["assessments"][0]
    assert calgary["risk_level"] == "VERY HIGH" and 60 <= calgary["risk_score"] < 80
    winter = next(a for a in r["assessments"] if a["station_name"] == "FORT CHIPEWYAN")
    assert winter["risk_score"] is None
    assert r["summary"]["highest_risk"]["station_id"] == "71877"


def test_fwi_filled_in_when_station_omits_it():
    r = client.get("/api/fwi/observations?station_ids=71879&region=AB").json()
    row = r["data"][0]
    assert row["fwi"] is not None and row["isi"] is not None and row["danger_class"]


def test_weather_units_are_metric():
    r = client.get("/api/weather/observations?station_ids=71877&region=AB").json()
    assert r["units"]["wind_speed"] == "km/h"
    assert r["data"][0]["temperature"] == 24.1


def test_active_fires_fall_back_and_drop_out_fires():
    r = client.get("/api/fires/active?region=AB").json()
    assert [f["name"] for f in r["fires"]] == ["CWF045", "SWF101"]   # largest first, EX and BC removed
    assert r["fires"][0]["stage_label"] == "Out of control"
    assert r["fires"][0]["agency"] == "AB"
    assert client.get("/api/fires/active?region=AB&include_out=true").json()["count"] == 3


def test_hotspots_use_geometry_and_fix_axis_order():
    r = client.get("/api/fires/hotspots?region=AB").json()
    assert r["count"] == 2
    swapped = next(h for h in r["hotspots"] if h["sensor"] == "MODIS")
    assert swapped["latitude"] == 55.21 and swapped["longitude"] == -116.02


def test_aqhi_nearest_with_latest_forecast_only():
    r = client.get("/api/air/aqhi?lat=51.04&lon=-114.06").json()
    assert r["location_name"] == "Calgary" and r["aqhi"] == 7.2 and r["category"] == "HIGH"
    assert [f["aqhi"] for f in r["forecast"]] == [8, 6]      # past and superseded forecasts dropped


def test_fire_risk_calculate():
    r = client.post("/api/fire-risk/calculate", json={"fwi_data": {"ffmc": 92, "dmc": 60, "dc": 500},
                                                      "weather_data": {"wind_speed": 25}}).json()
    assert r["indices"]["fwi"] > 20 and r["risk_level"] in {"VERY HIGH", "EXTREME"}


def test_plume_uses_gem_wind_and_station_fwi():
    r = client.post("/api/plume", json={"lat": 51.4, "lon": -114.8, "hours": [1, 2], "hectares": 850}).json()
    assert len(r["frames"]) == 2
    assert r["inputs"]["wind_source"].startswith("ECCC GEM")
    assert r["inputs"]["station_name"] == "CALGARY INTL"
    assert r["inputs"]["area_m2"] == 8_500_000


def test_plume_dynamic_union():
    r = client.post("/api/plume_dynamic", json={"lat": 51.4, "lon": -114.8, "hours": [1, 2],
                                                 "simulation_mode": "cumulative_union", "only_target_frames": True}).json()
    assert [f["hours"] for f in r["frames"]] == [1.0, 2.0]


def test_station_plume():
    r = client.get("/api/stations/71877/plume?region=AB&hours=1&hours=3").json()
    assert [f["hours"] for f in r["frames"]] == [1.0, 3.0]
    assert client.get("/api/stations/99999/plume?region=AB").status_code == 404


def test_chat_without_api_key_summarises_live_data():
    body = {"message": "Is it safe to go hiking?", "session_id": "t1",
            "location": {"latitude": 51.05, "longitude": -114.07, "name": "Calgary, AB"}}
    r = client.post("/api/llm/chat", json=body).json()
    assert "very high" in r["response"].lower() and "AQHI" in r["response"]
    assert r["nearby_fires"][0]["name"] == "CWF045"
    hist = client.get("/api/llm/sessions/t1/history").json()["messages"]
    assert [m["role"] for m in hist] == ["user", "assistant"]
