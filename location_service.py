"""
Location Service - Laptop Mode
Uses IP-based geolocation to get approximate latitude/longitude.
(Free service, no API key required. Fallback to fixed coords if offline.)
"""
import urllib.request
import json

# ip-api.com - free, no key, returns lat/lon (45 req/min)
IP_GEOLOC_URL = "http://ip-api.com/json/?fields=lat,lon"

# Fallback when IP geolocation fails
DEFAULT_LAT = 17.3850
DEFAULT_LNG = 78.4867


def get_location_from_ip():
    """
    Get approximate (lat, lng) from IP address.
    Returns (lat, lng) tuple or None on failure.
    """
    try:
        req = urllib.request.Request(IP_GEOLOC_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            lat = data.get("lat")
            lng = data.get("lon")
            if lat is not None and lng is not None:
                return (float(lat), float(lng))
    except Exception:
        pass
    return None


def get_current_location_string():
    """
    Get current location as "lat,lng" string for use in navigation.
    Uses IP geolocation on laptop; falls back to default if unavailable.
    """
    result = get_location_from_ip()
    if result:
        return f"{result[0]},{result[1]}"
    return f"{DEFAULT_LAT},{DEFAULT_LNG}"
