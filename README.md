# Wind4Skating

Collects observed wind readings for Oklahoma City and exposes the stored data as JSON for a website.

## First version

- **Location:** Oklahoma City, Oklahoma
- **Observation station:** KOKC, Will Rogers World Airport
- **Source:** National Weather Service station observations API
- **Storage:** local SQLite database at `data/wind_observations.sqlite3`
- **Units:** wind speed and gust in mph; direction in degrees; temperature in °F

These are station observations, not forecasts. The airport reading is a useful city reference, but local conditions at a skate spot can differ. The NWS API retains only seven days of station observations, so the server collects regularly to build your own history. NWS notes station data can be delayed during quality control.

## Run it

Requires Python 3.10 or newer. The collector and local JSON server use only the Python standard library.

```powershell
python -m wind_skating collect
python -m wind_skating serve
```

Open `http://127.0.0.1:8000` in a browser to see the dashboard. Wind remains the main focus: the page shows current wind and skate impact, a seven-day skate outlook, and an hourly wind breakdown. Temperature appears as a supporting current condition, daytime high in the outlook, and hourly value. Choose a forecast day from the selector; it defaults to today. The page refreshes the data periodically. Keep the server running while viewing it.

The current-wind card includes an intensity meter based on sustained wind speed: green below 10 mph, yellow from 10 to under 20 mph, and red at 20 mph or higher. Speeds above 30 mph are shown at the end of the red range.

Use **Which way are you skating?** to select one of 16 compass directions. The dashboard projects the reported wind onto that heading and shows headwind, tailwind, and crosswind components. Wind from the south blows northward, so skating south into it is labeled a headwind; wind from the north is a tailwind for southbound skating. It calls wind under 3 mph light, and an along-route headwind or tailwind component of 3 mph or more challenging or favorable. The selected direction is saved in that browser.

The server fetches and saves an observation immediately on startup, then once per hour by default. The dashboard retries shortly when it has no saved readings yet. Set `--collection-interval-minutes` on `serve` to change the interval. The **Skate wind outlook** section shows the next seven Oklahoma City forecast days. It uses NWS hourly forecast periods, groups daytime hours by local date, and rates the average wind component relative to your selected skating direction using the same 3 mph thresholds. Forecasts refresh every 30 minutes and are cached by the server for 30 minutes. This is a wind-only rating; it does not account for rain, temperature, pavement condition, or other skating conditions.

If the newest station report has incomplete wind data, the current-conditions panel uses the latest saved report with a usable wind speed and direction (or a calm reading) and labels the older report time. If there is no earlier usable report, it can still show a speed-only variable-direction report.

The skating rating remains based on wind and does not factor temperature into whether the wind is favorable. Temperature is informational. The same server provides JSON endpoints at `http://127.0.0.1:8000`:

- `GET /api/wind/latest` — most recently stored observation
- `GET /api/wind?limit=24` — up to 24 newest observations (maximum 500)
- `GET /api/forecast` — cached NWS hourly forecast periods for Oklahoma City

Example response:

```json
{
  "location": "Oklahoma City, Oklahoma",
  "observations": [
    {
      "station_id": "KOKC",
      "station_name": "Will Rogers World Airport",
      "observed_at": "2026-11-10T18:00:00+00:00",
      "fetched_at": "2026-11-10T18:04:00+00:00",
      "wind_speed_mph": 8.1,
      "wind_gust_mph": 12.7,
      "wind_direction_deg": 210.0,
      "temperature_f": 68.0,
      "source": "https://api.weather.gov/stations/KOKC/observations/latest"
    }
  ]
}
```

The SQLite database is local to the server. For a hosted deployment, attach persistent storage at the database directory so collected readings survive restarts and redeploys. The server process must stay running for its hourly collector to run.

## Source notes

The NWS documents the latest station observation endpoint as `/stations/{stationId}/observations/latest` and provides an hourly forecast link for a location through its `/points` endpoint. Hourly forecast periods cover the next seven days. Station observations are available for seven days through the API. See the [NWS API documentation](https://www.weather.gov/documentation/services-web-api).
