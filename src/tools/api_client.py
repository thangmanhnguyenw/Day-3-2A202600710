"""
HTTP clients for commute lab: OpenWeatherMap, OSRM routing, optional Google Directions, ICS calendar.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
CALENDAR_ICS_URL = os.getenv("CALENDAR_ICS_URL", "")
REQUEST_TIMEOUT = int(os.getenv("API_REQUEST_TIMEOUT", "15"))


class ApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _get(url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 400:
        raise ApiError(f"HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code)
    return resp.json()


def fetch_weather_forecast(lat: float, lon: float, target_date: str) -> Dict[str, Any]:
    """
    OpenWeatherMap 5-day / 3-hour forecast.
    https://openweathermap.org/forecast5
    """
    if not OPENWEATHER_API_KEY:
        raise ApiError(
            "OPENWEATHER_API_KEY is not set. Get a free key at https://openweathermap.org/api"
        )

    data = _get(
        "https://api.openweathermap.org/data/2.5/forecast",
        {
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "vi",
        },
    )

    try:
        day = date.fromisoformat(target_date)
    except ValueError as e:
        raise ApiError(f"Invalid date '{target_date}': use YYYY-MM-DD") from e

    slots = []
    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"])
        if dt.date() == day:
            slots.append(item)

    if not slots:
        return {
            "source": "openweathermap",
            "date": target_date,
            "available": False,
            "message": f"No forecast slots for {target_date} (OpenWeather provides ~5 days ahead).",
            "city": data.get("city", {}).get("name"),
        }

    # Midday-ish slot or average
    pick = slots[len(slots) // 2]
    main = pick["weather"][0]
    pop = pick.get("pop", 0)
    temp = pick["main"]["temp"]
    condition = main.get("main", "unknown").lower()
    description = main.get("description", "")

    advice = "Mang ô hoặc áo mưa." if pop >= 0.5 or "mưa" in description.lower() or "rain" in condition else "Thời tiết ổn cho di chuyển."

    return {
        "source": "openweathermap",
        "available": True,
        "date": target_date,
        "temp_c": round(temp, 1),
        "rain_probability": round(pop, 2),
        "condition": condition,
        "description": description,
        "advice": advice,
        "city": data.get("city", {}).get("name"),
    }


def fetch_osrm_route(
    lat1: float, lon1: float, lat2: float, lon2: float, profile: str = "driving"
) -> Dict[str, Any]:
    """
    OSRM public routing API (driving ≈ xe máy/ô tô trên đường).
    https://project-osrm.org/
    """
    coord_path = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coord_path}"
    data = _get(url, {"overview": "false"})

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ApiError(data.get("message", "OSRM routing failed"))

    route = data["routes"][0]
    duration_sec = route["duration"]
    distance_m = route["distance"]
    return {
        "source": "osrm",
        "profile": profile,
        "duration_seconds": duration_sec,
        "duration_minutes": max(1, int(round(duration_sec / 60))),
        "distance_meters": int(distance_m),
        "distance_km": round(distance_m / 1000, 2),
    }


def fetch_google_directions(
    lat1: float, lon1: float, lat2: float, lon2: float, mode: str = "driving"
) -> Dict[str, Any]:
    """Optional Google Directions API when GOOGLE_MAPS_API_KEY is set."""
    if not GOOGLE_MAPS_API_KEY:
        raise ApiError("GOOGLE_MAPS_API_KEY is not set")

    origin = f"{lat1},{lon1}"
    destination = f"{lat2},{lon2}"
    data = _get(
        "https://maps.googleapis.com/maps/api/directions/json",
        {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "key": GOOGLE_MAPS_API_KEY,
            "language": "vi",
        },
    )

    if data.get("status") != "OK" or not data.get("routes"):
        raise ApiError(data.get("error_message", data.get("status", "Directions failed")))

    leg = data["routes"][0]["legs"][0]
    return {
        "source": "google_maps",
        "mode": mode,
        "duration_minutes": max(1, int(leg["duration"]["value"] / 60)),
        "distance_meters": leg["distance"]["value"],
        "distance_km": round(leg["distance"]["value"] / 1000, 2),
        "summary": data["routes"][0].get("summary", ""),
    }


def build_commute_options(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    preferred_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Derive bus / motorbike / grab estimates from OSRM (and optional Google)."""
    if lat1 == lat2 and lon1 == lon2:
        return [
            {
                "mode": "walk",
                "minutes": 5,
                "cost_vnd": 0,
                "note": "Cùng khu vực",
                "source": "local",
            }
        ]

    base = fetch_osrm_route(lat1, lon1, lat2, lon2)
    drive_min = base["duration_minutes"]
    dist_km = base["distance_km"]

    # Heuristic costs (VND) for lab demo — not official Grab pricing
    grab_cost = int(12000 + dist_km * 18000)
    bus_min = int(drive_min * 1.55)
    bus_cost = 7000 if dist_km < 8 else 9000

    options = [
        {
            "mode": "motorbike",
            "minutes": drive_min,
            "cost_vnd": int(8000 + dist_km * 3500),
            "note": f"Ước tính từ OSRM driving ({base['distance_km']} km)",
            "source": "osrm",
        },
        {
            "mode": "bus",
            "minutes": bus_min,
            "cost_vnd": bus_cost,
            "note": "Ước tính: xe buýt thường chậm hơn ~55% so với xe máy",
            "source": "estimate",
        },
        {
            "mode": "grab",
            "minutes": int(drive_min * 1.1),
            "cost_vnd": grab_cost,
            "note": "Ước tính chi phí ride-hailing (không phải báo giá chính thức)",
            "source": "estimate",
        },
    ]

    if GOOGLE_MAPS_API_KEY:
        try:
            g = fetch_google_directions(lat1, lon1, lat2, lon2)
            options.append(
                {
                    "mode": "google_driving",
                    "minutes": g["duration_minutes"],
                    "cost_vnd": grab_cost,
                    "note": f"Google Directions: {g.get('summary', '')}",
                    "source": "google_maps",
                }
            )
        except ApiError:
            pass

    if preferred_mode:
        mode_key = preferred_mode.strip().lower()
        filtered = [o for o in options if o["mode"] == mode_key]
        if filtered:
            return filtered
    return options


def fetch_calendar_events_from_ics(ics_url: Optional[str] = None) -> List[Dict[str, str]]:
    """Load events from a public ICS URL (e.g. Google Calendar secret iCal address)."""
    url = (ics_url or CALENDAR_ICS_URL or "").strip()
    if not url:
        raise ApiError(
            "CALENDAR_ICS_URL is not set. In Google Calendar: Settings → Integrate calendar → Secret address in iCal format."
        )

    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 400:
        raise ApiError(f"Failed to fetch ICS: HTTP {resp.status_code}", resp.status_code)

    try:
        from icalendar import Calendar
    except ImportError as e:
        raise ApiError("Install icalendar: pip install icalendar") from e

    cal = Calendar.from_ical(resp.content)
    events: List[Dict[str, str]] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        if not dtstart or not dtend:
            continue
        start = dtstart.dt
        end = dtend.dt
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())

        events.append(
            {
                "title": str(component.get("summary", "Busy")),
                "start": start.isoformat(timespec="minutes"),
                "end": end.isoformat(timespec="minutes"),
                "location": str(component.get("location", "")),
            }
        )

    return events

from typing import Any, Dict

def geocode_place(query: str) -> Dict[str, Any]:
    if not OPENWEATHER_API_KEY:
        raise ApiError("OPENWEATHER_API_KEY is not set")

    data = _get(
        "http://api.openweathermap.org/geo/1.0/direct",
        {
            "q": query,
            "limit": 1,
            "appid": OPENWEATHER_API_KEY,
        },
    )

    if not data:
        raise ApiError(f"Không tìm thấy tọa độ cho địa điểm: {query}")

    best = data[0]
    parts = [best.get("name"), best.get("state"), best.get("country")]

    return {
        "name": ", ".join([p for p in parts if p]),
        "lat": best["lat"],
        "lon": best["lon"],
    }