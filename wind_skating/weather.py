"""Fetch and normalize observed wind from the NWS API."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.request import Request, urlopen


STATION_ID = "KOKC"  # Will Rogers World Airport, Oklahoma City
OBSERVATION_URL = (
    f"https://api.weather.gov/stations/{STATION_ID}/observations/latest"
)
RECENT_OBSERVATIONS_URL = (
    f"https://api.weather.gov/stations/{STATION_ID}/observations?limit=20"
)
USER_AGENT = "WindAnalysisForSkating/0.1 (personal weather project)"


def _number(measurement: dict | None, *, target: str) -> float | None:
    """Convert a NWS measurement to mph or degrees, returning None if absent."""
    if not measurement or measurement.get("value") is None:
        return None
    value = float(measurement["value"])
    unit = measurement.get("unitCode", "")
    if target == "mph":
        if "m_s-1" in unit:
            return value * 2.2369362921
        if "km_h-1" in unit:
            return value * 0.6213711922
        if "[kn_i]" in unit or "knot" in unit:
            return value * 1.150779448
        if "mi_h-1" in unit:
            return value
        raise ValueError(f"Unsupported wind speed unit: {unit!r}")
    if target == "degrees":
        return value
    raise ValueError(f"Unsupported conversion target: {target}")


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/geo+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def _normalize(properties: dict, source: str) -> dict:
    timestamp = properties.get("timestamp")
    if not timestamp:
        raise ValueError("NWS observation is missing its timestamp")
    return {
        "station_id": STATION_ID,
        "station_name": properties.get("stationName") or "Will Rogers World Airport",
        "observed_at": timestamp,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wind_speed_mph": _number(properties.get("windSpeed"), target="mph"),
        "wind_gust_mph": _number(properties.get("windGust"), target="mph"),
        "wind_direction_deg": _number(
            properties.get("windDirection"), target="degrees"
        ),
        "raw_json": json.dumps(properties, separators=(",", ":")),
        "source": source,
    }


def _has_usable_wind(observation: dict) -> bool:
    speed = observation["wind_speed_mph"]
    return speed is not None and (
        observation["wind_direction_deg"] is not None or speed < 0.5
    )


def fetch_latest_observation() -> dict:
    latest_payload = _get_json(OBSERVATION_URL)
    properties = latest_payload.get("properties", {})
    if not properties:
        raise ValueError("NWS returned an observation without properties")
    latest = _normalize(properties, OBSERVATION_URL)
    if _has_usable_wind(latest):
        return latest

    # A fresh deployment may not yet have a usable reading in its own database.
    # Check recent station reports so it can save the most recent usable one now.
    try:
        recent_payload = _get_json(RECENT_OBSERVATIONS_URL)
        features = recent_payload.get("features", [])
        features.sort(
            key=lambda item: item.get("properties", {}).get("timestamp", ""),
            reverse=True,
        )
        for feature in features:
            previous_properties = feature.get("properties", {})
            if previous_properties.get("timestamp") == latest["observed_at"]:
                continue
            try:
                previous = _normalize(previous_properties, RECENT_OBSERVATIONS_URL)
            except (TypeError, ValueError):
                continue
            if _has_usable_wind(previous):
                latest["fallback_observation"] = previous
                break
    except Exception as exc:
        latest["fallback_lookup_error"] = str(exc)

    return latest
