"""Command line entry point: python -m wind_skating {collect,serve}."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse, parse_qs

from .storage import DEFAULT_DB, latest_wind_observation, list_observations, save_observation
from .weather import fetch_latest_observation
from .forecast import fetch_hourly_forecast

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def collect(db_path: Path) -> None:
    observation = fetch_latest_observation()
    inserted = save_observation(observation, db_path)
    speed = observation["wind_speed_mph"]
    speed_text = "missing" if speed is None else f"{speed:.1f} mph"
    status = "saved" if inserted else "already stored"
    print(f"{observation['observed_at']}: {speed_text} ({status})")


def _collect_periodically(db_path: Path, interval_seconds: int) -> None:
    while True:
        try:
            collect(db_path)
        except Exception as exc:
            print(f"Wind collection failed: {exc}")
        time.sleep(interval_seconds)


def serve(db_path: Path, host: str, port: int, collection_interval_minutes: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/api/forecast":
                try:
                    body = json.dumps(fetch_hourly_forecast()).encode()
                except Exception as exc:
                    print(f"Forecast request failed: {exc}")
                    body = json.dumps({"error": f"Forecast unavailable: {exc}"}).encode()
                    self._send(body, "application/json; charset=utf-8", status=502)
                    return
                self._send(body, "application/json; charset=utf-8")
                return
            if parsed.path not in ("/api/wind", "/api/wind/latest"):
                self.send_error(404, "Use /api/wind or /api/wind/latest")
                return
            query = parse_qs(parsed.query)
            try:
                limit = max(1, min(500, int(query.get("limit", ["24"])[0])))
            except ValueError:
                self.send_error(400, "limit must be an integer")
                return
            if parsed.path.endswith("/latest"):
                latest = latest_wind_observation(db_path)
                items = [latest] if latest else []
            else:
                items = list_observations(db_path, limit=limit)
            body = json.dumps(
                {"location": "Oklahoma City, Oklahoma", "observations": items}
            ).encode()
            self._send(body, "application/json; charset=utf-8")

        def _send_file(self, path: Path, content_type: str) -> None:
            try:
                body = path.read_bytes()
            except FileNotFoundError:
                self.send_error(404, "Dashboard file not found")
                return
            self._send(body, content_type)

        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

    server = ThreadingHTTPServer((host, port), Handler)
    collector = threading.Thread(
        target=_collect_periodically,
        args=(db_path, collection_interval_minutes * 60),
        name="wind-collector",
        daemon=True,
    )
    collector.start()
    print(f"Serving dashboard at http://{host}:{port}/")
    print(f"Collecting observed wind every {collection_interval_minutes} minutes")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Oklahoma City observed wind collector")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("collect", help="Fetch and store the latest observation")
    server_parser = subparsers.add_parser("serve", help="Serve stored observations as JSON")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8000)
    server_parser.add_argument(
        "--collection-interval-minutes", type=int, default=60,
        help="How often the server collects observed wind (default: 60 minutes)",
    )
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.db)
    else:
        if args.collection_interval_minutes < 1:
            parser.error("--collection-interval-minutes must be at least 1")
        serve(args.db, args.host, args.port, args.collection_interval_minutes)


if __name__ == "__main__":
    main()
