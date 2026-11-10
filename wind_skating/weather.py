"""Fetch and normalize observed wind from the NWS API."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.request import Request, urlopen


STATION_ID = "KOKC"  # Will Rogers World Airport, Oklahoma City
OBSERVATION_URL = (
    f"https://api.weather.gov/stations/{STATION_ID}/observations/latest"
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


def fetch_latest_observation() -> dict:
    request = Request(
        OBSERVATION_URL,
        headers={"Accept": "application/geo+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)

    properties = payload.get("properties", {})
    if not properties:
        raise ValueError("NWS returned an observation without properties")
    if not properties.get("timestamp"):
        raise ValueError("NWS observation is missing its timestamp")
    return {
        "station_id": STATION_ID,
        "station_name": properties.get("stationName") or "Will Rogers World Airport",
        "observed_at": properties.get("timestamp"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wind_speed_mph": _number(properties.get("windSpeed"), target="mph"),
        "wind_gust_mph": _number(properties.get("windGust"), target="mph"),
        "wind_direction_deg": _number(
            properties.get("windDirection"), target="degrees"
        ),
        "raw_json": json.dumps(properties, separators=(",", ":")),
        "source": OBSERVATION_URL,
    }
