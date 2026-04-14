"""
Navigation Module - Google Maps APIs
- Directions API: Walking route
- Geocoding API: Convert destination to coordinates
- Places API: General categories (e.g. "hospital" -> nearest)
- Roads API: Snap GPS to road (reduces drift when real GPS available)
- Route deviation detection and automatic recalculation
"""
import re
import time
import math
import threading
import webbrowser

import googlemaps
import googlemaps.roads
from config import Config
from location_service import get_current_location_string

# Optional custom map window (served on 127.0.0.1). Disabled so we always
# fallback to real Google Maps in the browser using the Directions URL.
MAP_VIEW_AVAILABLE = False


def _decode_polyline(encoded):
    """Decode Google polyline to list of (lat, lng) tuples."""
    points = []
    i = 0
    lat, lng = 0, 0
    while i < len(encoded):
        shift, result = 0, 0
        while True:
            b = ord(encoded[i]) - 63
            i += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat
        shift, result = 0, 0
        while True:
            b = ord(encoded[i]) - 63
            i += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng
        points.append((lat / 1e5, lng / 1e5))
    return points


def _haversine_meters(lat1, lng1, lat2, lng2):
    """Distance in meters between two points (approximate)."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _distance_to_segment(px, py, x1, y1, x2, y2):
    """Min distance from point (px,py) to segment (x1,y1)-(x2,y2). Approx for short segments."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx*dx + dy*dy
    if length_sq == 0:
        return _haversine_meters(px, py, x1, y1)
    t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / length_sq))
    tx = x1 + t * dx
    ty = y1 + t * dy
    return _haversine_meters(px, py, tx, ty)


def _distance_to_polyline(lat, lng, points):
    """Min distance in meters from (lat,lng) to polyline."""
    if not points:
        return float('inf')
    min_d = float('inf')
    for i in range(len(points) - 1):
        d = _distance_to_segment(lat, lng, points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        min_d = min(min_d, d)
    return min_d


class NavigationModule:
    def __init__(self, voice_engine):
        self.voice_engine = voice_engine
        self.gmaps = googlemaps.Client(key=Config.GOOGLE_MAPS_API_KEY) if Config.GOOGLE_MAPS_API_KEY else None
        self.is_navigating = False
        self.route = None
        self.route_polyline = []
        self.step_index = 0
        self.current_location = None
        self._snapped_location = None
        self.destination = None
        self.dest_text = None
        self.nav_thread = None
        self.pending_destination = None
        self._position_thread = None
        self._last_deviation_check = 0
        self._use_real_gps = False  # Set True when real GPS provides updates

    def set_current_location(self, lat, lng):
        """Update current location (call from GPS module). Uses Roads API to snap to road."""
        self.current_location = f"{lat},{lng}"
        self._snapped_location = None
        self._use_real_gps = True

    def _get_current_location(self):
        """Laptop: IP-based geolocation. Mobile: real GPS via set_current_location."""
        if self.current_location:
            return self.current_location
        return get_current_location_string()

    def _snap_location_to_road(self, lat, lng):
        """Roads API: snap raw GPS to nearest road to reduce drift."""
        if not self.gmaps:
            return (lat, lng)
        try:
            path = [(lat, lng)]
            r = googlemaps.roads.snap_to_roads(self.gmaps, path)
            if r and len(r) > 0:
                loc = r[0]["location"]
                return (loc["latitude"], loc["longitude"])
        except Exception as e:
            print(f"Roads API error: {e}")
        return (lat, lng)

    def _get_snapped_origin(self):
        """Get origin for directions - snapped via Roads API when real GPS is used."""
        raw = self._get_current_location()
        lat, lng = map(float, raw.split(','))
        if getattr(self, '_use_real_gps', False):
            snapped = self._snap_location_to_road(lat, lng)
            return f"{snapped[0]},{snapped[1]}"
        return raw

    def _geocode_destination(self, dest_text):
        """Find any location by name/address (like Google Maps). Uses Geocoding API."""
        if not dest_text or not dest_text.strip():
            return None
        try:
            r = self.gmaps.geocode(dest_text.strip())
            if r:
                loc = r[0]['geometry']['location']
                return f"{loc['lat']},{loc['lng']}"
        except Exception as e:
            print(f"Geocode error: {e}")
        return None

    def _geocode_city(self, city_name):
        """Get lat,lng of a city for Places search in that city. Returns (lat, lng) or None."""
        if not city_name or not city_name.strip():
            return None
        try:
            r = self.gmaps.geocode(city_name.strip())
            if r:
                loc = r[0]['geometry']['location']
                return (loc['lat'], loc['lng'])
        except Exception as e:
            print(f"Geocode city error: {e}")
        return None

    def _parse_destination_intent(self, dest_text):
        """Parse user input:
        - 'hospital in Hyderabad'  -> ('hospital', 'Hyderabad')
        - 'supermarket near Rajam' -> ('supermarket', 'Rajam')
        - 'restaurant'             -> ('restaurant', None)
        """
        text = (dest_text or "").strip()
        if not text:
            return None, None
        text_lower = text.lower()

        # Handle "X in City" or "X near City" / "X around City"
        m = re.search(r'\b(.+?)\s+(in|near|around)\s+(.+)$', text_lower, re.IGNORECASE)
        if m:
            category_or_name = m.group(1).strip()
            city = m.group(3).strip()
            if city:
                return category_or_name, city

        return text_lower, None

    def _is_category_keyword(self, query):
        """True if query is a single category for 'near me' (hospital, restaurant, etc.)."""
        q = (query or "").strip().lower()
        if not q:
            return False
        for kw in getattr(Config, 'PLACES_CATEGORY_KEYWORDS', ['hospital', 'restaurant', 'bank', 'shopping mall', 'mall']):
            if q == kw or q.replace(' ', '') == kw.replace(' ', ''):
                return True
        return False

    def _resolve_category_in_city(self, category, city_name, radius=None):
        """Places API: nearest place of category in a specific city. Returns (coords, place_name) or (None, None)."""
        radius = radius or getattr(Config, 'PLACES_SEARCH_RADIUS_METERS', 5000)
        center = self._geocode_city(city_name)
        if not center:
            return None, None
        lat, lng = center
        try:
            places = self.gmaps.places_nearby(
                location={'lat': lat, 'lng': lng},
                keyword=category.strip(),
                radius=radius
            )
            if places.get('results'):
                p = places['results'][0]
                loc = p['geometry']['location']
                return f"{loc['lat']},{loc['lng']}", p.get('name', category)
        except Exception as e:
            print(f"Places API (city): {e}")
        return None, None

    def _resolve_place_category(self, query, radius=None):
        """Places API: nearest place for category near current location (e.g. hospital, restaurant). Handles API errors."""
        radius = radius or getattr(Config, 'PLACES_SEARCH_RADIUS_METERS', 5000)
        if not query or not query.strip():
            return None, None
        try:
            origin = self._get_current_location()
            lat, lng = map(float, origin.split(','))
            places = self.gmaps.places_nearby(
                location={'lat': lat, 'lng': lng},
                keyword=query.strip(),
                radius=radius
            )
            if places.get('results'):
                p = places['results'][0]
                loc = p['geometry']['location']
                return f"{loc['lat']},{loc['lng']}", p.get('name', query)
        except Exception as e:
            print(f"Places API: {e}")
        return None, None

    def _get_directions(self, origin, dest):
        try:
            r = self.gmaps.directions(origin, dest, mode="walking")
            if r:
                return r[0]
        except Exception as e:
            print(f"Directions error: {e}")
        return None

    def _extract_polyline(self, route):
        enc = route.get('overview_polyline', {}).get('points')
        if enc:
            return _decode_polyline(enc)
        points = []
        for leg in route.get('legs', []):
            for step in leg.get('steps', []):
                start = step.get('start_location', {})
                points.append((start.get('lat'), start.get('lng')))
        if route.get('legs'):
            end = route['legs'][-1].get('end_location', {})
            points.append((end.get('lat'), end.get('lng')))
        return points

    def _check_deviation_and_recalculate(self):
        """Check if user deviated from route; recalculate if beyond threshold."""
        now = time.time()
        if now - self._last_deviation_check < getattr(Config, 'POSITION_UPDATE_INTERVAL', 5):
            return
        self._last_deviation_check = now

        raw = self._get_current_location()
        lat, lng = map(float, raw.split(','))
        if not self.route_polyline:
            return
        dist = _distance_to_polyline(lat, lng, self.route_polyline)
        if dist < getattr(Config, 'DEVIATION_THRESHOLD_METERS', 50):
            return

        self.voice_engine.speak("Recalculating route.")
        origin = self._get_snapped_origin()
        new_route = self._get_directions(origin, self.destination)
        if new_route:
            self.route = new_route
            self.route_polyline = self._extract_polyline(new_route)
            self.step_index = 0

    def _do_navigate(self, dest_text):
        """Find destination: any place globally, category in city, or category near me (5 km).
        Returns True if navigation started successfully, False otherwise.
        """
        dest_text = (dest_text or "").strip()
        if not dest_text:
            self.voice_engine.speak("Please say a destination.")
            return False
        origin = self._get_snapped_origin()
        dest_coords = None
        display_name = dest_text

        category_or_name, city = self._parse_destination_intent(dest_text)

        # 1) "X in City" -> Places in that city (e.g. hospital in Hyderabad)
        if city and category_or_name:
            coords, place_name = self._resolve_category_in_city(category_or_name, city)
            if coords:
                dest_coords = coords
                display_name = place_name or dest_text

        # 2) Category only, near me (5 km radius): hospital, restaurant, bank, shopping mall, etc.
        if not dest_coords and self._is_category_keyword(dest_text):
            coords, place_name = self._resolve_place_category(dest_text)
            if coords:
                dest_coords = coords
                display_name = place_name or dest_text

        # 3) Any specific name/address globally (Geocoding)
        if not dest_coords:
            dest_coords = self._geocode_destination(dest_text)
            if dest_coords:
                display_name = dest_text

        # 4) Fallback: try Places near me for whatever user said
        if not dest_coords:
            coords, place_name = self._resolve_place_category(dest_text)
            if coords:
                dest_coords = coords
                display_name = place_name or dest_text
                self.voice_engine.speak(f"Searching for {display_name} near you. For example, you can say 'hospital', 'restaurant', 'bank', or 'shopping mall'.")

        if not dest_coords:
            self.voice_engine.speak("Destination not found. Try again.")
            return False

        self.route = self._get_directions(origin, dest_coords)
        if not self.route:
            self.voice_engine.speak("No route found. Try again.")
            return False

        self.route_polyline = self._extract_polyline(self.route)
        self.step_index = 0
        self.destination = dest_coords
        self.dest_text = display_name
        self.is_navigating = True
        self._last_deviation_check = time.time()
        self.voice_engine.speak("Destination found. Starting navigation.")

        if MAP_VIEW_AVAILABLE and Config.GOOGLE_MAPS_API_KEY:
            # Use custom map view if available.
            o_lat, o_lng = map(float, origin.split(','))
            d_lat, d_lng = map(float, dest_coords.split(','))
            poly = self.route.get('overview_polyline', {}).get('points', '')
            if poly:
                show_route(o_lat, o_lng, d_lat, d_lng, poly)
                update_position(o_lat, o_lng)
                open_map_browser()
        else:
            # Fallback: open Google Maps directions in default browser.
            try:
                maps_url = (
                    f"https://www.google.com/maps/dir/?api=1"
                    f"&origin={origin}&destination={dest_coords}&travelmode=walking"
                )
                webbrowser.open(maps_url)
            except Exception as e:
                print(f"Browser open error: {e}")

        self.nav_thread = threading.Thread(target=self._navigation_loop, daemon=True)
        self.nav_thread.start()
        return True

    def _navigation_loop(self):
        steps = self.route.get('legs', [{}])[0].get('steps', [])
        last_instruction = 0

        while self.is_navigating:
            now = time.time()

            if MAP_VIEW_AVAILABLE:
                raw = self._get_current_location()
                lat, lng = map(float, raw.split(','))
                update_position(lat, lng)

            self._check_deviation_and_recalculate()
            steps = self.route.get('legs', [{}])[0].get('steps', []) if self.route else []

            if self.step_index < len(steps) and (now - last_instruction) >= 8:
                step = steps[self.step_index]
                instr = step.get('html_instructions', '')
                dist = step.get('distance', {}).get('text', '')
                clean = self._clean_instruction(instr, dist)
                self.voice_engine.speak(clean)
                self.step_index += 1
                last_instruction = now
            elif self.step_index >= len(steps):
                self.voice_engine.speak("You have arrived at your destination.")
                self.stop_navigation()
                return
            time.sleep(1)

    def _clean_instruction(self, html, dist):
        text = re.sub(r'<[^>]+>', '', html)
        text = text.replace('Head north', 'Walk north').replace('Head south', 'Walk south')
        text = text.replace('Head east', 'Walk east').replace('Head west', 'Walk west')
        if dist:
            text = f"{dist}. {text}"
        return text.strip()

    def start_navigation(self, destination=None):
        if not self.gmaps:
            self.voice_engine.speak("Google Maps API key not configured. Add GOOGLE_MAPS_API_KEY to .env")
            return
        if destination:
            self._do_navigate(destination)
        else:
            self.pending_destination = True

    def set_destination(self, destination):
        """Called when speech recognizer produces a destination phrase.
        If the first attempt fails (destination not found / no route),
        we keep pending_destination = True so the user can try again.
        """
        if self.pending_destination and destination:
            ok = self._do_navigate(destination)
            if ok:
                # Only clear pending flag when navigation actually started.
                self.pending_destination = False

    def stop_navigation(self):
        self.is_navigating = False
        self.route = None
        self.route_polyline = []
        self.pending_destination = False
