"""Fetch and normalize observed wind from the NWS API."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.request import Request, urlopen
from .locations import LOCATIONS


USER_AGENT = "Wind4Skating/1.0 (personal weather project)"

# The NWS API returns wind speed in various units, including m/s, km/h, knots, and mph,
# and this just converts them all to mph. 
# The NWS API returns temperature in Celsius or Fahrenheit, 
# and this converts it to Fahrenheit.
def _number(measurement: dict | None, *, target: str) -> float | None:
    """Convert a NWS measurement to mph or degrees, returning None if absent."""
    if not measurement or measurement.get("value") is None:
        return None
    value = float(measurement["value"])
    unit = measurement.get("unitCode", "")

    # For miles per hour unit.
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
    
    # For degrees (fahrenheit) unit.
    if target == "degrees":
        return value
    if target == "fahrenheit":
        if "degC" in unit or "degc" in unit:
            return value * 9 / 5 + 32
        if "degF" in unit or "degf" in unit:
            return value
        raise ValueError(f"Unsupported temperature unit: {unit!r}")
    raise ValueError(f"Unsupported conversion target: {target}")

# The NWS API returns JSON, this returns it as a Python dict.
def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/geo+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)

# The NWS API returns a JSON object with a "properties" dict, 
# which contains the actual observation data.
# This function normalizes that data into the dashboard format.
def _normalize(properties: dict, source: str, station_id: str) -> dict:
    timestamp = properties.get("timestamp")
    if not timestamp:
        raise ValueError("NWS observation is missing its timestamp")
    return {
        "station_id": station_id,
        "station_name": properties.get("stationName") or "Will Rogers World Airport",
        "observed_at": timestamp,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wind_speed_mph": _number(properties.get("windSpeed"), target="mph"),
        "wind_gust_mph": _number(properties.get("windGust"), target="mph"),
        "wind_direction_deg": _number(
            properties.get("windDirection"), target="degrees"
        ),
        "temperature_f": _number(properties.get("temperature"), target="fahrenheit"),
        "raw_json": json.dumps(properties, separators=(",", ":")),
        "source": source,
    }

# Checks if observation has usable wind data.
def _has_usable_wind(observation: dict) -> bool:
    speed = observation["wind_speed_mph"]
    return speed is not None and (
        observation["wind_direction_deg"] is not None or speed < 0.5
    )

# Fetches the latest observation from the NWS API for a location.
def fetch_latest_observation(location: str = "okc") -> dict:
    if location not in LOCATIONS:
        raise ValueError(f"Unsupported location: {location}")
    
    # Gets the station ID for the location and construct the URLs for the observations.
    station_id = LOCATIONS[location]["station_id"]
    observation_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    recent_observations_url = f"https://api.weather.gov/stations/{station_id}/observations?limit=20"
    latest_payload = _get_json(observation_url)
    properties = latest_payload.get("properties", {})
    if not properties:
        raise ValueError("NWS returned an observation without properties")

    # Normalize the latest observation and check if it has usable wind data.
    latest = _normalize(properties, observation_url, station_id)
    if _has_usable_wind(latest):
        return latest

    # A fresh deployment may not yet have a usable reading in its own database.
    # Checks the recent station reports so it can use the most recent usable one now as a fallback.
    try:
        recent_payload = _get_json(recent_observations_url)
        features = recent_payload.get("features", [])
        features.sort(
            key=lambda item: item.get("properties", {}).get("timestamp", ""),
            reverse=True,
        )
        # Look for the most recent usable observation that is not the same as the latest one.
        for feature in features:
            previous_properties = feature.get("properties", {})
            if previous_properties.get("timestamp") == latest["observed_at"]:
                continue
            try:
                previous = _normalize(previous_properties, recent_observations_url, station_id)
            except (TypeError, ValueError):
                continue
            if _has_usable_wind(previous):
                latest["fallback_observation"] = previous
                break
    except Exception as exc:
        latest["fallback_lookup_error"] = str(exc)

    return latest
