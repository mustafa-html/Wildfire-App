# Respira Canada

Wildfire danger, reported fires, smoke and air quality for any Canadian province or territory, on one map with a chat assistant. A port of Respira (originally New York / US Forest Service data) to Canadian public data.

## Data sources

| Feature | Original (US) | This version (Canada) |
|---|---|---|
| Fire danger at stations | FEMS GraphQL: weather + NFDRS (Burning Index, fuel moisture), one query each per station | Natural Resources Canada CWFIS WFS `firewx_stns_current`: local-noon weather and the full Fire Weather Index System (FFMC, DMC, DC, ISI, BUI, FWI) for every station in one request |
| Risk levels | Home-made weighted score | FWI danger classes (CWFIS national map breaks), shown on the same 0–100 scale: each class is one 20-point band |
| Coverage | New York | Any province/territory, or all of Canada (`DEFAULT_REGION`, default `AB`) |
| Fire locations | None (stations used as stand-in origins) | Agency-reported active fires (CWFIS / CIFFC) and 24 h satellite hotspots |
| Air quality | Planned AQI | Environment and Climate Change Canada AQHI, observations and forecasts |
| Wind for smoke plumes | Station wind, assumed mph | Current wind from ECCC's GEM model (via Open-Meteo, no key), falling back to station noon wind |
| Smoke forecast | None | Optional ECCC FireWork overlay (`RAQDPS-FW.EATM_PM2.5-DIFF`, MSC GeoMet WMS) |
| Units | °F, mph | °C, km/h, mm, hectares |
| Assistant | Gemini via deprecated `google-generativeai` | Gemini via `google-genai`; without a key it replies with a plain summary of the live data |

When displaying CWFIS data, Natural Resources Canada must be credited. The sidebar footer does this; keep it if you change the UI.

## Run it

Backend (Python 3.11+):

```bash
cd backend
cp .env.example .env              # GEMINI_API_KEY is optional
pip install -r requirements-dev.txt
pytest                            # 26 offline tests
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/api/health to confirm CWFIS is reachable, and http://localhost:8000/docs for every route.

Frontend (Node 18+):

```bash
cd frontend
cp .env.example .env              # add REACT_APP_GOOGLE_MAPS_API_KEY
npm install
npm start                         # http://localhost:3000
```

Or run the backend in Docker: `docker compose up --build`.

## API

| Route | What it returns |
|---|---|
| `GET /api/regions` | Provinces/territories with bounds and map centres |
| `GET /api/stations?region=AB` | Fire-weather stations |
| `GET /api/weather/observations?station_ids=…` | Noon weather (°C, %, km/h, mm) |
| `GET /api/fwi/observations?station_ids=…` | FFMC, DMC, DC, ISI, BUI, FWI and danger class |
| `GET /api/fire-risk/assessment?region=AB` | Every station scored, highest first, with a regional summary |
| `POST /api/fire-risk/calculate` | Score and class from FWI values (fills ISI/BUI/FWI from the moisture codes if needed) |
| `GET /api/fires/active?region=AB` | Reported wildfires, largest first (`include_out=true` adds extinguished fires) |
| `GET /api/fires/hotspots?region=AB` | Satellite hotspots from the last 24 h, with fire radiative power |
| `GET /api/air/aqhi?lat=…&lon=…` | Nearest AQHI reading and its forecast |
| `GET /api/air/aqhi/observations?region=AB` | Latest AQHI for every reporting community |
| `POST /api/plume`, `POST /api/plume_dynamic` | Smoke cone from a point or polygon (`fwi`, `ffmc`, `frp_mw`, `hectares` replace `burning_index`, `one_hr_fm`, `viirs_frp`) |
| `GET /api/stations/{id}/plume` | Smoke cone as if a fire started at a station |
| `POST /api/llm/chat` and session routes | Assistant, given FWI, AQHI and nearby fires for the selected place |

Dropped: `/api/fire-danger/percentiles` (FEMS climatology, no CWFIS equivalent) and `/api/graphql/query` (FEMS-specific).

## Things to know

- **Check field names on first run.** Station fields were confirmed against a working 2026 CWFIS client. Active-fire and hotspot parsing accepts several attribute names and falls back to the geometry, because CWFIS is moving layers to a new GeoServer. The active-fire client tries the new `cwfif_national_activefires` layer first, then the legacy `activefires_current`. Layer names and URLs are environment variables (see `backend/.env.example`).
- **Station data is daily.** CWFIS publishes one local-noon observation per station per day. Stations in seasonal shutdown report no FWI and are shown grey.
- **Danger classes are the national map's**, not a provincial rating. BC Wildfire Service and others use different breaks; override with `FWI_CLASS_BREAKS`.
- **Plumes are a visual heuristic**, not a dispersion model. Use the FireWork overlay for ECCC's actual smoke forecast.
- **No fake data.** The original silently showed random mock stations when the API failed; this version shows the error instead.

## Fixed from the original

- The FastAPI app could not start: modules imported `fems_endpoints` as a top-level module, and `fems_fastapi.py` contained unresolved git merge-conflict markers.
- Plumes vanished at some coordinates: the zero-radius origin point created a self-intersecting polygon that was then discarded.
- "Add fire location" never worked after the first render (the map click handler held a stale value), and the button sat under the legend.
- Chat history endpoint crashed with a `KeyError` (it read `content`, but stored `parts`).
- A Google Maps API key was hard-coded in `frontend/src/app/WildfireMap.tsx`. It is now read from `.env`; rotate the old key if it was yours.
- CORS used `https://*.vercel.app` in `allow_origins`, which Starlette does not treat as a wildcard; now a regex.
- The unused, non-building Next.js stub in `frontend/src/app` was removed; `frontend/` is the React app.

## License

Apache 2.0, as in the original project.
