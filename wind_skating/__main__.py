"""Command line entry point: python -m wind_skating {collect,serve}."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .storage import DEFAULT_DB, list_observations, save_observation
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


def serve(db_path: Path, host: str, port: int) -> None:
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
            result_limit = 1 if parsed.path.endswith("/latest") else limit
            items = list_observations(db_path, limit=result_limit)
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
    print(f"Serving wind data at http://{host}:{port}/api/wind")
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
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.db)
    else:
        serve(args.db, args.host, args.port)


if __name__ == "__main__":
    main()
