"""Fetch and lightly normalize the NWS hourly forecast for Oklahoma City."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from .locations import LOCATIONS
from urllib.parse import urlparse
from urllib.request import Request, urlopen


USER_AGENT = "Wind4Skating/1.0 (personal weather project)"
CACHE_TTL = timedelta(minutes=30)
_cache: dict[str, tuple[datetime, dict]] = {}

# Gets the JSON data from a URL.
def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/geo+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)

# Converts a wind speed range string into a tuple of floats in mph.
def _speed_range(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers and "calm" in text.lower():
        return 0.0, 0.0
    if not numbers:
        return None, None
    if "km/h" in text.lower():
        numbers = [value * 0.6213711922 for value in numbers]
    if "kt" in text.lower() or "knot" in text.lower():
        numbers = [value * 1.150779448 for value in numbers]
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers[0], numbers[1]), max(numbers[0], numbers[1])

# Fetches hourly forecast data from the NWS API for a location.
def fetch_hourly_forecast(location: str = "okc") -> dict:
    """Return cached hourly NWS forecast periods; refresh at most every 30 min."""
    if location not in LOCATIONS:
        raise ValueError(f"Unsupported location: {location}")
    now = datetime.now(timezone.utc)
    cached = _cache.get(location)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]

    # Gets hourly forecast data from the NWS API for the location.
    place = LOCATIONS[location]
    point_url = f"https://api.weather.gov/points/{place['latitude']},{place['longitude']}"
    point = _get_json(point_url)
    forecast_url = point.get("properties", {}).get("forecastHourly")
    if not forecast_url:
        raise ValueError("NWS did not provide an hourly forecast URL for Oklahoma City")
    parsed = urlparse(forecast_url)
    if parsed.scheme != "https" or parsed.hostname != "api.weather.gov":
        raise ValueError("NWS returned an unexpected hourly forecast URL")

    # Fetches the forecast data and normalizes it into project format.
    forecast = _get_json(forecast_url)
    props = forecast.get("properties", {})
    periods = []
    for period in props.get("periods", []):
        low, high = _speed_range(period.get("windSpeed"))
        temperature = period.get("temperature")
        temperature_f = None
        if temperature is not None:
            temperature_f = float(temperature)
            if period.get("temperatureUnit") == "C":
                temperature_f = temperature_f * 9 / 5 + 32
        periods.append(
            {
                "start_time": period.get("startTime"),
                "end_time": period.get("endTime"),
                "is_daytime": period.get("isDaytime"),
                "wind_speed_min_mph": low,
                "wind_speed_max_mph": high,
                "temperature_f": temperature_f,
                "wind_direction": period.get("windDirection"),
                "short_forecast": period.get("shortForecast"),
            }
        )
    result = {
        "location": place["name"],
        "timezone": "America/Chicago",
        "updated": props.get("updateTime"),
        "periods": periods,
        "source": forecast_url,
    }
    _cache[location] = (now, result)
    return result
