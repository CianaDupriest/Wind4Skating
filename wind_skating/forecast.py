"""Fetch and lightly normalize the NWS hourly forecast for Oklahoma City."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen


OKC_LATITUDE = 35.4676
OKC_LONGITUDE = -97.5164
POINTS_URL = f"https://api.weather.gov/points/{OKC_LATITUDE},{OKC_LONGITUDE}"
USER_AGENT = "Wind4Skating/1.0 (personal weather project)"
CACHE_TTL = timedelta(minutes=30)
_cache: tuple[datetime, dict] | None = None


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/geo+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


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


def fetch_hourly_forecast() -> dict:
    """Return cached hourly NWS forecast periods; refresh at most every 30 min."""
    global _cache
    now = datetime.now(timezone.utc)
    if _cache and now - _cache[0] < CACHE_TTL:
        return _cache[1]

    point = _get_json(POINTS_URL)
    forecast_url = point.get("properties", {}).get("forecastHourly")
    if not forecast_url:
        raise ValueError("NWS did not provide an hourly forecast URL for Oklahoma City")
    parsed = urlparse(forecast_url)
    if parsed.scheme != "https" or parsed.hostname != "api.weather.gov":
        raise ValueError("NWS returned an unexpected hourly forecast URL")

    forecast = _get_json(forecast_url)
    props = forecast.get("properties", {})
    periods = []
    for period in props.get("periods", []):
        low, high = _speed_range(period.get("windSpeed"))
        temperature = period.get("temperature")
        temperature_unit = period.get("temperatureUnit")
        if temperature is not None and temperature_unit == "C":
            temperature = temperature * 9 / 5 + 32
        periods.append(
            {
                "start_time": period.get("startTime"),
                "is_daytime": period.get("isDaytime"),
                "wind_speed_min_mph": low,
                "wind_speed_max_mph": high,
                "wind_direction": period.get("windDirection"),
                "temperature_f": temperature if temperature_unit in ("F", "C") else None,
                "short_forecast": period.get("shortForecast"),
            }
        )
    result = {
        "location": "Oklahoma City, Oklahoma",
        "timezone": "America/Chicago",
        "updated": props.get("updateTime"),
        "periods": periods,
        "source": forecast_url,
    }
    _cache = (now, result)
    return result
