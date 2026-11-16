# Wind4Skating

Wind4Skating is a small weather dashboard for checking whether the wind may help or hinder a skate. It combines current National Weather Service (NWS) station observations with the NWS hourly forecast, then relates wind direction and speed to the direction you plan to skate.

The dashboard also shows current temperature and basic temperature guidance. Its skate ratings are based on wind alone; they do not account for rain, pavement conditions, or other hazards.

## Locations

Choose a location in the dashboard:

| Dashboard location | Observation station |
| --- | --- |
| Oklahoma City | KOKC |
| Los Angeles | KLAX |
| Seattle | KSEA |
| Dallas | KDAL |
| New York | KNYC |

The app uses each station as a nearby reference. Conditions at a particular skate spot can differ from an airport or other reporting station.

## Run locally

Requires Python 3.10 or newer. The app uses only the Python standard library, so no package installation is needed.

From the project directory, start the dashboard and collector:

```powershell
python -m wind_skating serve
```

Then open <http://127.0.0.1:8000> in a browser. The server fetches observations for the supported locations when it starts and repeats collection every 60 minutes by default. Keep the process running while using the dashboard.

To change the collection interval, for example to 30 minutes:

```powershell
python -m wind_skating serve --collection-interval-minutes 30
```

To fetch and save one Oklahoma City observation without starting the web server:

```powershell
python -m wind_skating collect
```

Use `--db PATH` with either command to choose a different SQLite database file. By default, readings are stored in `data/wind_observations.sqlite3`. That file is local and ignored by Git.

## Dashboard features

- Current observed wind speed, its intensity, and current temperature.
- A wind outlook for the selected skating heading, with headwind, tailwind, and crosswind guidance.
- Seven days of hourly forecast data, including a daily daytime wind rating and an hour-by-hour view.
- Temperature guidance based on the latest station observation.
- A location selector and a 16-direction skating selector. The skating direction is saved in the browser.

The wind rating is a simple estimate: wind under 3 mph is treated as light, and a headwind or tailwind component of at least 3 mph is labeled challenging or favorable. Wind direction is the direction it comes **from**; for example, wind from the south blows northward.

The forecast is fetched from the NWS hourly forecast associated with the selected location and cached by the server for up to 30 minutes. Current observations are collected periodically and read from the local database. If the newest report has incomplete wind data, the app can use a recent usable report and indicate its observation time.

## JSON API

The local server also provides JSON endpoints. Each accepts an optional `location` parameter; supported values are `okc`, `los-angeles`, `seattle`, `dallas`, and `new-york`.

| Endpoint | Description |
| --- | --- |
| `/api/wind/latest?location=okc` | Latest saved observation for the selected location |
| `/api/wind?location=okc&limit=24` | Up to the requested number of saved observations (maximum 500) |
| `/api/forecast?location=okc` | Hourly NWS forecast for the selected location |

Observation responses include station and timestamp fields, wind speed and gust in mph, wind direction in degrees, and temperature in Fahrenheit when reported. Forecast responses include hourly periods with wind speed ranges, direction, and temperature.

## Data and deployment notes

Wind4Skating gets weather data from the [National Weather Service API](https://www.weather.gov/documentation/services-web-api). NWS observations may be delayed while undergoing quality control, and a station reading is only a nearby reference for local skating conditions.

For a hosted deployment, attach persistent storage for the SQLite database so collected readings survive restarts and redeploys. The server process must remain running for scheduled collection to continue.
