"""Offline test harness: every upstream call is served from fixtures."""

import json
from pathlib import Path

import pytest

from app.clients import cwfis, eccc, openmeteo
from app.clients.http import UpstreamError

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def fake_get_json(url, params=None, cache=True):
    params = params or {}
    layer = params.get("typeNames", "")
    if "firewx_stns_current" in layer:
        return _load("cwfis_stations.json")
    if "cwfif_national_activefires" in layer:
        raise UpstreamError("simulated: new GeoServer unavailable")
    if "activefires_current" in layer:
        return _load("cwfis_activefires.json")
    if "hotspots" in layer:
        if "CQL_FILTER" in params:
            raise UpstreamError("simulated: layer has no lat/lon attributes")
        return _load("cwfis_hotspots.json")
    if "aqhi-observations-realtime" in url:
        return _load("aqhi_observations.json")
    if "aqhi-forecasts-realtime" in url:
        return _load("aqhi_forecasts.json")
    if "open-meteo" in url:
        return {"current": {"wind_speed_10m": 6.0, "wind_direction_10m": 270.0}}
    raise AssertionError(f"unexpected upstream call {url} {params}")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for mod in (cwfis, eccc, openmeteo):
        monkeypatch.setattr(mod, "get_json", fake_get_json)
    monkeypatch.setattr("app.config.GEMINI_API_KEY", "")
    yield
