"""Chat assistant. Same endpoints as the original; the context it is given is
now Canadian: FWI danger from the nearest CWFIS station, the local AQHI and
its forecast, and agency-reported fires nearby.

Uses the Google Gen AI SDK (``google-genai``), which replaced the deprecated
``google-generativeai`` package the original imported. Without a
GEMINI_API_KEY the endpoint still works and answers from the live data with a
plain summary, so the app runs end to end with no keys at all.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config, services

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["Assistant"])

DEFAULT_LOCATION = {"latitude": 53.5461, "longitude": -113.4938, "name": "Edmonton, AB"}
MAX_TURNS = 20

chat_sessions: Dict[str, List[Dict[str, str]]] = {}
_client = None


def _get_client():
    global _client
    if _client is not None or not config.GEMINI_API_KEY:
        return _client
    try:
        from google import genai

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Gemini client unavailable: %s", exc)
    return _client


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    location: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    location_used: Dict[str, Any]
    fire_risk_data: Optional[Dict[str, Any]] = None
    air_quality: Optional[Dict[str, Any]] = None
    nearby_fires: List[Dict[str, Any]] = []
    sources: List[str] = []
    model: Optional[str] = None


def _fmt(value: Any, unit: str = "", digits: int = 0) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}{unit}" if isinstance(value, (int, float)) else f"{value}{unit}"


def build_context_text(ctx: Optional[Dict[str, Any]]) -> str:
    if not ctx:
        return "## Live data\nNo location was provided. Answer from general knowledge only.\n"
    loc = ctx["location"]
    lines = ["## Live data for the user's location",
             f"Location: {loc['name']} ({loc['latitude']:.3f}, {loc['longitude']:.3f})"]

    risk = ctx.get("fire_risk") or {}
    if "error" in risk:
        lines.append(f"Fire danger: unavailable ({risk['error']})")
    else:
        w, f = risk.get("weather_conditions") or {}, risk.get("fire_indices") or {}
        lines.append(
            f"Fire danger: {risk.get('risk_level') or 'no FWI reported'} "
            f"(FWI {_fmt(f.get('fwi'), digits=1)}) from station {risk.get('station_name')} "
            f"~{_fmt(risk.get('distance_km'), ' km')} away, observed {risk.get('observation_time') or 'n/a'}"
        )
        lines.append(
            f"Noon weather: {_fmt(w.get('temperature'), ' °C', 1)}, RH {_fmt(w.get('relative_humidity'), '%')}, "
            f"wind {_fmt(w.get('wind_speed'), ' km/h')} from {_fmt(w.get('wind_direction'), '°')}, "
            f"24 h rain {_fmt(w.get('precip_24h'), ' mm', 1)}"
        )
        lines.append(
            f"FWI System: FFMC {_fmt(f.get('ffmc'), digits=1)}, DMC {_fmt(f.get('dmc'), digits=1)}, "
            f"DC {_fmt(f.get('dc'), digits=0)}, ISI {_fmt(f.get('isi'), digits=1)}, BUI {_fmt(f.get('bui'), digits=1)}"
        )

    aq = ctx.get("air_quality")
    if aq:
        nxt = (aq.get("forecast") or [])[:3]
        fc = "; ".join(f"{x.get('label') or x.get('forecast_for')}: {x.get('aqhi')}" for x in nxt) or "none issued"
        lines.append(
            f"Air Quality Health Index: {aq['aqhi']} ({aq['category']} risk) at {aq['location_name']} "
            f"~{_fmt(aq.get('distance_km'), ' km')} away. Forecast: {fc}"
        )
    else:
        lines.append("Air Quality Health Index: no reporting community within 150 km")

    fires = ctx.get("nearby_fires") or []
    if fires:
        lines.append("Reported wildfires within 150 km:")
        for fire in fires:
            lines.append(
                f"- {fire['name']} ({fire.get('agency') or 'agency n/a'}): {_fmt(fire.get('hectares'), ' ha', 1)}, "
                f"{fire['stage_label'].lower()}, {fire['distance_km']} km away"
            )
    else:
        lines.append("Reported wildfires within 150 km: none")
    return "\n".join(lines) + "\n"


def create_system_prompt(ctx: Optional[Dict[str, Any]]) -> str:
    return (
        "You are Respira, an assistant for wildfire and smoke safety in Canada. Be clear, direct and calm.\n\n"
        "Rules:\n"
        "1. When live data is given and the user asks about current conditions, state the fire danger class "
        "and the AQHI in one or two sentences with the main reason, then offer more detail. Do not list every number.\n"
        "2. Use Canadian terms and units: Fire Weather Index (FWI) danger classes, AQHI (1-10+), °C, km/h, hectares.\n"
        "3. For evacuation orders, fire bans and alerts, tell the user to check their provincial or territorial "
        "wildfire agency, Alberta Emergency Alert / Alertable, or local authorities. Never invent an order or ban.\n"
        "4. If someone describes an emergency or fire nearby, tell them to call 911 first.\n"
        "5. If there is no data for their location, say so and answer general safety questions.\n\n"
        + build_context_text(ctx)
    )


def _fallback_answer(ctx: Optional[Dict[str, Any]]) -> str:
    if not ctx:
        return ("The AI assistant isn't configured on this server (no GEMINI_API_KEY). "
                "Pick a station or location on the map to see live fire danger and air quality.")
    parts = []
    risk = ctx.get("fire_risk") or {}
    if "error" not in risk and risk.get("risk_level"):
        parts.append(f"Fire danger near {ctx['location']['name']} is {risk['risk_level'].lower()} "
                     f"(FWI {_fmt((risk.get('fire_indices') or {}).get('fwi'), digits=1)} at {risk['station_name']}).")
    aq = ctx.get("air_quality")
    if aq:
        parts.append(f"The AQHI at {aq['location_name']} is {aq['aqhi']}, a {aq['category'].lower()} health risk. {aq['advice']}")
    fires = ctx.get("nearby_fires") or []
    if fires:
        parts.append(f"{len(fires)} reported wildfire(s) within 150 km; the closest is {fires[0]['name']}, "
                     f"{fires[0]['distance_km']} km away and {fires[0]['stage_label'].lower()}.")
    parts.append("(Plain summary: the AI assistant is not configured on this server.)")
    return " ".join(parts)


def build_chat_response(message: str, session_id: str, location: Optional[Dict[str, Any]]) -> ChatResponse:
    history = chat_sessions.setdefault(session_id, [])
    loc = location or DEFAULT_LOCATION
    ctx = None
    if location and "latitude" in location and "longitude" in location:
        ctx = services.location_context(float(location["latitude"]), float(location["longitude"]), location.get("name"))

    client = _get_client()
    model_used = None
    if client is None:
        answer = _fallback_answer(ctx)
    else:
        from google.genai import types

        contents = [{"role": m["role"], "parts": [{"text": m["text"]}]} for m in history[-MAX_TURNS * 2:]]
        contents.append({"role": "user", "parts": [{"text": message}]})
        result = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=create_system_prompt(ctx), temperature=0.4),
        )
        answer = (result.text or "").strip() or "I couldn't generate a reply. Please try again."
        model_used = config.GEMINI_MODEL

    now = datetime.now(timezone.utc).isoformat()
    history.append({"role": "user", "text": message, "timestamp": now})
    history.append({"role": "model", "text": answer, "timestamp": now})

    risk = (ctx or {}).get("fire_risk")
    sources = []
    if ctx:
        if risk and "error" not in risk:
            sources.append("Natural Resources Canada — CWFIS fire weather")
        if ctx.get("air_quality"):
            sources.append("Environment and Climate Change Canada — AQHI")
        if ctx.get("nearby_fires"):
            sources.append("CWFIS / CIFFC reported fires")

    return ChatResponse(
        response=answer,
        session_id=session_id,
        location_used=loc,
        fire_risk_data=risk if risk and "error" not in risk else None,
        air_quality=(ctx or {}).get("air_quality"),
        nearby_fires=(ctx or {}).get("nearby_fires") or [],
        sources=sources,
        model=model_used,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return build_chat_response(request.message, request.session_id or "default", request.location)
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {exc}") from exc


@router.get("/sessions/{session_id}/history")
def get_chat_history(session_id: str):
    messages = [
        {"role": "assistant" if m["role"] == "model" else "user", "content": m["text"], "timestamp": m["timestamp"]}
        for m in chat_sessions.get(session_id, [])
    ]
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
def clear_chat_session(session_id: str):
    chat_sessions.pop(session_id, None)
    return {"message": f"Session {session_id} cleared"}


@router.get("/location/default")
def get_default_location():
    return {
        "location": DEFAULT_LOCATION,
        "context": services.location_context(DEFAULT_LOCATION["latitude"], DEFAULT_LOCATION["longitude"], DEFAULT_LOCATION["name"]),
    }


@router.post("/location/risk-assessment")
def location_risk_assessment(location: Dict[str, Any]):
    if "latitude" not in location or "longitude" not in location:
        raise HTTPException(status_code=400, detail="Location must include latitude and longitude")
    return {
        **services.location_context(float(location["latitude"]), float(location["longitude"]), location.get("name")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
