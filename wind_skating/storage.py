"""SQLite storage for station observations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DEFAULT_DB = Path("data/wind_observations.sqlite3")


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY,
            station_id TEXT NOT NULL,
            station_name TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            wind_speed_mph REAL,
            wind_gust_mph REAL,
            wind_direction_deg REAL,
            temperature_f REAL,
            source TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            UNIQUE(station_id, observed_at)
        )"""
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(observations)")}
    if "temperature_f" not in columns:
        connection.execute("ALTER TABLE observations ADD COLUMN temperature_f REAL")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(observed_at)"
    )
    connection.commit()
    return connection


def save_observation(observation: dict, db_path: Path = DEFAULT_DB) -> bool:
    """Insert an observation; return False when this timestamp was already saved."""
    with connect(db_path) as connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO observations
            (station_id, station_name, observed_at, fetched_at, wind_speed_mph,
             wind_gust_mph, wind_direction_deg, temperature_f, source, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                observation["station_id"], observation["station_name"],
                observation["observed_at"], observation["fetched_at"],
                observation["wind_speed_mph"], observation["wind_gust_mph"],
                observation["wind_direction_deg"], observation.get("temperature_f"),
                observation["source"], observation["raw_json"],
            ),
        )
        return cursor.rowcount == 1


def list_observations(db_path: Path = DEFAULT_DB, limit: int = 24, station_id: str = "KOKC") -> list[dict]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """SELECT station_id, station_name, observed_at, fetched_at,
                      wind_speed_mph, wind_gust_mph, wind_direction_deg, temperature_f, source
               FROM observations WHERE station_id = ? ORDER BY observed_at DESC LIMIT ?""",
            (station_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def latest_wind_observation(db_path: Path = DEFAULT_DB, station_id: str = "KOKC") -> dict | None:
    """Return the newest direction-usable report, falling back to latest speed data."""
    columns = """station_id, station_name, observed_at, fetched_at,
                 wind_speed_mph, wind_gust_mph, wind_direction_deg, temperature_f, source"""
    with connect(db_path) as connection:
        newest = connection.execute(
            f"SELECT {columns} FROM observations WHERE station_id = ? ORDER BY observed_at DESC LIMIT 1", (station_id,)
        ).fetchone()
        complete = connection.execute(
            f"""SELECT {columns} FROM observations
                WHERE station_id = ? AND wind_speed_mph IS NOT NULL
                  AND (wind_direction_deg IS NOT NULL OR wind_speed_mph < 0.5)
                ORDER BY observed_at DESC LIMIT 1""", (station_id,)
        ).fetchone()
        speed_only = connection.execute(
            f"""SELECT {columns} FROM observations WHERE station_id = ? AND wind_speed_mph IS NOT NULL
                ORDER BY observed_at DESC LIMIT 1""", (station_id,)
        ).fetchone()

    selected = complete or speed_only or newest
    if selected is None:
        return None
    result = dict(selected)
    result["latest_station_report_at"] = newest["observed_at"] if newest else None
    result["using_previous_report"] = bool(
        newest and selected["observed_at"] != newest["observed_at"]
    )
    return result
