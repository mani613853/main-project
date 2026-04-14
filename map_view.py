"""
Map View - Opens Google Maps in browser during navigation.
Shows route, origin, destination, and current position (updates every 3s).
"""
import json
import webbrowser
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from config import Config

MAP_PORT = 8765
MAP_DIR = Path(__file__).parent / "map_static"
ROUTE_FILE = MAP_DIR / "route.json"
POSITION_FILE = MAP_DIR / "position.json"

_server = None
_server_thread = None


class MapHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MAP_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/map.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = (MAP_DIR / "map.html").read_text(encoding="utf-8")
            key = Config.GOOGLE_MAPS_API_KEY or ""
            self.wfile.write(html.replace("{{API_KEY}}", key).encode("utf-8"))
        elif self.path == "/route.json":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            if ROUTE_FILE.exists():
                self.wfile.write(ROUTE_FILE.read_bytes())
            else:
                self.wfile.write(b'{}')
        elif self.path == "/position.json":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            if POSITION_FILE.exists():
                self.wfile.write(POSITION_FILE.read_bytes())
            else:
                self.wfile.write(b'{"lat":0,"lng":0}')
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass


def _run_server():
    global _server
    _server = HTTPServer(("127.0.0.1", MAP_PORT), MapHandler)
    _server.serve_forever()


def start_map_server():
    """Start the map HTTP server in a background thread."""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return
    _server_thread = threading.Thread(target=_run_server, daemon=True)
    _server_thread.start()


def show_route(origin_lat, origin_lng, dest_lat, dest_lng, polyline_encoded):
    """Write route data and open map in browser."""
    if not Config.GOOGLE_MAPS_API_KEY:
        return
    start_map_server()
    route = {
        "origin": {"lat": origin_lat, "lng": origin_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "polyline": polyline_encoded,
    }
    ROUTE_FILE.write_text(json.dumps(route), encoding="utf-8")


def update_position(lat, lng):
    """Update current position (called during navigation)."""
    pos = {"lat": lat, "lng": lng}
    POSITION_FILE.write_text(json.dumps(pos), encoding="utf-8")


def open_map_browser():
    """Open the map in the default browser."""
    webbrowser.open(f"http://127.0.0.1:{MAP_PORT}/")
