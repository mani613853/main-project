#!/usr/bin/env python3
"""
Test script to verify all APIs used by the Assistive Vision System.
Run: python test_navigation_api.py
Tests: Geocoding, Places, Directions, Roads (Google); IP location (ip-api.com).
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')


def test_ip_location():
    """IP-based location (used on laptop when no GPS)."""
    print("\n--- IP Location (ip-api.com) ---")
    try:
        from location_service import get_location_from_ip, get_current_location_string
        result = get_location_from_ip()
        if result:
            print(f"  OK -> lat={result[0]:.4f}, lng={result[1]:.4f}")
            return True
        s = get_current_location_string()
        print(f"  Fallback used -> {s}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_google_apis():
    """Geocoding, Places, Directions, Roads."""
    print("\n--- Google Maps APIs ---")
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY == "your_google_maps_api_key_here":
        print("  FAIL: GOOGLE_MAPS_API_KEY not set in .env")
        return {}

    try:
        import googlemaps
    except ImportError:
        print("  FAIL: pip install googlemaps")
        return {}

    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    origin = "17.3850,78.4867"
    results = {"Geocoding": False, "Places": False, "Directions": False, "Roads": False}

    # Geocoding
    try:
        r = gmaps.geocode("Sri Chaitanya School Rajam")
        if r:
            loc = r[0]["geometry"]["location"]
            print(f"  Geocoding: OK -> {loc['lat']},{loc['lng']}")
            results["Geocoding"] = True
        else:
            print("  Geocoding: no results")
    except Exception as e:
        print(f"  Geocoding: ERROR -> {e}")

    # Places
    try:
        lat, lng = 17.3850, 78.4867
        places = gmaps.places_nearby(location={"lat": lat, "lng": lng}, keyword="hospital", radius=5000)
        if places.get("results"):
            print("  Places: OK")
            results["Places"] = True
        else:
            err = places.get("error_message", "no results")
            print(f"  Places: {err}")
    except Exception as e:
        print(f"  Places: ERROR -> {e}")

    # Directions
    try:
        r = gmaps.directions(origin, "18.4474704,83.6732556", mode="walking")
        if r and r[0].get("legs"):
            steps = len(r[0]["legs"][0].get("steps", []))
            print(f"  Directions: OK -> {steps} steps")
            results["Directions"] = True
        else:
            print("  Directions: no route")
    except Exception as e:
        print(f"  Directions: ERROR -> {e}")

    # Roads (snap to road)
    try:
        path = [(17.3850, 78.4867)]
        r = googlemaps.roads.snap_to_roads(gmaps, path)
        if r and len(r) > 0:
            loc = r[0]["location"]
            print(f"  Roads: OK -> snapped to {loc['latitude']:.4f},{loc['longitude']:.4f}")
            results["Roads"] = True
        else:
            print("  Roads: no snapped point")
    except Exception as e:
        print(f"  Roads: ERROR -> {e}")

    return results


def main():
    print("=" * 60)
    print("Assistive Vision System - API Check")
    print("=" * 60)

    ip_ok = test_ip_location()
    google_results = test_google_apis()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  IP Location (laptop):  {'OK' if ip_ok else 'FAIL'}")
    for name, ok in (google_results or {}).items():
        print(f"  {name}:  {'OK' if ok else 'FAIL / not enabled'}")
    print("=" * 60)

    all_required = ip_ok and (google_results.get("Geocoding") and google_results.get("Directions"))
    if not google_results.get("Places"):
        print("Note: Enable Places API in Google Cloud Console for category search (e.g. 'hospital').")
    if not google_results.get("Roads"):
        print("Note: Enable Roads API for snapping GPS to roads (optional; app works without it).")
    return all_required


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
