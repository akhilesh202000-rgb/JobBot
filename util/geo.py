# util/geo.py
#
# Standort-Näherung für Wien: Bezirk/PLZ -> Zentroid -> Distanz zu Hause.
# Bewusst offline (keine Geocoding-API), damit der Lauf schnell und stabil bleibt.

import math
import re

from config.constants import (
    DISTRICTS,
    HOME_LAT,
    HOME_LNG,
    INCLUDE_SUBURBS,
    MAX_SUBURB_DISTANCE_KM,
    SUBURB_COORDS,
    VIENNA_CENTROID,
)

EARTH_RADIUS_KM = 6371.0

# "Wien 22. Bezirk (Donaustadt)" / "Wien 22.Bezirk"
_DISTRICT_RE = re.compile(r"wien\s*[-\s]?\s*(\d{1,2})\s*\.?\s*bezirk", re.I)
# "Wien 9" / "Wien 2" (z. B. metajob) – aber nicht "Wien 1220" (PLZ).
_DISTRICT_SHORT_RE = re.compile(r"\bwien\s*[-–]?\s*(\d{1,2})(?!\d)", re.I)
# "1220 Wien" oder "Wien 1220"
_PLZ_AFTER_RE = re.compile(r"\bwien\b[^\d]{0,10}(\d{4})\b", re.I)
_PLZ_BEFORE_RE = re.compile(r"\b(\d{4})\s+wien\b", re.I)
# "Südliches Wien" / "südlich von Wien" -> grob Favoriten/Liesing
_SOUTH_RE = re.compile(r"s[üu]dlich(e[sr]?)?\s*(von\s*)?wien", re.I)
_ANY_WIEN_RE = re.compile(r"\bwien\b", re.I)


def haversine_km(lat1, lon1, lat2, lon2):
    """Luftlinie in Kilometern zwischen zwei Koordinaten."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _distance_to_home(lat, lon):
    return haversine_km(HOME_LAT, HOME_LNG, lat, lon)


def parse_location(raw):
    """
    Wandelt einen Location-String in ein Dict um oder gibt None zurück.

    Ergebnis:
        {"raw": str, "district": int|None, "name": str,
         "lat": float, "lng": float, "km": float,
         "in_vienna": bool, "approx": bool}
    """
    if not raw or not isinstance(raw, str):
        return None

    text = raw.strip()
    lower = text.lower()

    # 1) Bezirk, z. B. "Wien 22. Bezirk (Donaustadt)" oder "Wien 9"
    match = _DISTRICT_RE.search(text) or _DISTRICT_SHORT_RE.search(text)
    if match:
        district = int(match.group(1))
        if district in DISTRICTS:
            name, lat, lng = DISTRICTS[district]
            return {
                "raw": text,
                "district": district,
                "name": name,
                "lat": lat,
                "lng": lng,
                "km": _distance_to_home(lat, lng),
                "in_vienna": True,
                "approx": True,
            }

    # 2) PLZ, z. B. "1220 Wien" / "Wien 1220"
    plz_match = _PLZ_BEFORE_RE.search(text) or _PLZ_AFTER_RE.search(text)
    if plz_match:
        plz = int(plz_match.group(1))
        # Wiener PLZ: 1010 = 1. Bezirk, 1220 = 22. Bezirk, 1230 = 23. Bezirk
        district = plz // 10 - 100
        if district in DISTRICTS:
            name, lat, lng = DISTRICTS[district]
            return {
                "raw": text,
                "district": district,
                "name": name,
                "lat": lat,
                "lng": lng,
                "km": _distance_to_home(lat, lng),
                "in_vienna": True,
                "approx": True,
            }

    # 3) "Südliches Wien" o. ä.
    if _SOUTH_RE.search(text):
        name, lat, lng = DISTRICTS[10]
        return {
            "raw": text,
            "district": 10,
            "name": f"{name} (Süden, ca.)",
            "lat": lat,
            "lng": lng,
            "km": _distance_to_home(lat, lng),
            "in_vienna": True,
            "approx": True,
        }

    # 4) Umliegende Gemeinde
    for suburb, (lat, lng) in SUBURB_COORDS.items():
        if suburb in lower:
            km = _distance_to_home(lat, lng)
            if not INCLUDE_SUBURBS or km > MAX_SUBURB_DISTANCE_KM:
                return None
            return {
                "raw": text,
                "district": None,
                "name": text,
                "lat": lat,
                "lng": lng,
                "km": km,
                "in_vienna": False,
                "approx": True,
            }

    # 5) Nur "Wien" ohne Details -> Stadtzentrum
    if _ANY_WIEN_RE.search(text):
        lat, lng = VIENNA_CENTROID
        return {
            "raw": text,
            "district": None,
            "name": "Wien (Bezirk unbekannt)",
            "lat": lat,
            "lng": lng,
            "km": _distance_to_home(lat, lng),
            "in_vienna": True,
            "approx": True,
        }

    return None


def best_vienna_location(locations):
    """
    Nimmt eine Liste von Location-Strings und liefert die näheste
    Wien-Location (oder None, wenn keine in Wien liegt).
    """
    parsed = []
    for raw in locations or []:
        item = parse_location(raw)
        if item and (item["in_vienna"] or INCLUDE_SUBURBS):
            parsed.append(item)

    if not parsed:
        return None

    return min(parsed, key=lambda item: item["km"])
