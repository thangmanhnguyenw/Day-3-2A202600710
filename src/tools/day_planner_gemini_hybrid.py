from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests

from src.tools.api_client import (
    ApiError,
    OPENWEATHER_API_KEY,
    _get,
    build_commute_options,
    fetch_weather_forecast,
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "day-commute-planner")
API_REQUEST_TIMEOUT = int(os.getenv("API_REQUEST_TIMEOUT", "30"))


@lru_cache(maxsize=1)
def _get_openrouter_headers() -> Dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise ApiError("OPENROUTER_API_KEY is not set")

    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
    }


def _extract_text(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("content") or "").strip()
    return str(result).strip()


def _parse_time(day: str, time_str: str) -> datetime:
    t = time_str.strip()
    if len(t) == 5:
        t += ":00"
    return datetime.fromisoformat(f"{day}T{t}")


def _call_openrouter_json(prompt: str, system_prompt: str) -> Dict[str, Any]:
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=_get_openrouter_headers(),
            json=payload,
            timeout=API_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        detail = ""
        try:
            detail = response.text
        except Exception:
            detail = str(e)
        raise ApiError(f"OpenRouter request failed: {detail or e}")

    data = response.json()
    text = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    match = re.search(r"\{[\s\S]*\}$", text)
    candidate = match.group(0) if match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ApiError(f"OpenRouter did not return valid JSON: {e}. Raw: {text[:500]}")


def _normalize_place_with_openrouter(place: str) -> str:
    payload = {
        "input": place,
        "task": "Normalize this location into a short geocoding-friendly query.",
        "rules": [
            "Return JSON only.",
            "Use Vietnamese if the place is in Vietnam.",
            "If city/country is missing, infer only when highly likely.",
            "Do not add explanations.",
        ],
        "output_schema": {"normalized_query": "string"},
    }

    data = _call_openrouter_json(
        json.dumps(payload, ensure_ascii=False),
        "You normalize place names for geocoding. Return JSON only.",
    )

    normalized = str(data.get("normalized_query") or "").strip()
    if not normalized:
        return place
    return normalized


def _geocode_place(query: str) -> Dict[str, Any]:
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


def _resolve_place(raw_location: str) -> Dict[str, Any]:
    raw_location = str(raw_location).strip()
    if not raw_location:
        raise ApiError("Thiếu địa điểm")

    try:
        place = _geocode_place(raw_location)
        place["input"] = raw_location
        place["normalized_query"] = raw_location
        place["resolver"] = "direct_geocode"
        return place
    except Exception:
        pass

    try:
        normalized_query = _normalize_place_with_openrouter(raw_location)
        place = _geocode_place(normalized_query)
        place["input"] = raw_location
        place["normalized_query"] = normalized_query
        place["resolver"] = "openrouter_normalized"
        return place
    except Exception:
        pass

    try:
        fallback_query = f"{raw_location}, Vietnam"
        place = _geocode_place(fallback_query)
        place["input"] = raw_location
        place["normalized_query"] = fallback_query
        place["resolver"] = "fallback_vietnam"
        return place
    except Exception as e:
        raise ApiError(f"Không resolve được địa điểm '{raw_location}': {e}")


def _fetch_weather_at_time(lat: float, lon: float, day: str, target_time: str) -> Dict[str, Any]:
    if not target_time:
        return fetch_weather_forecast(lat, lon, day)

    target_dt = _parse_time(day, target_time)

    if not OPENWEATHER_API_KEY:
        raise ApiError("OPENWEATHER_API_KEY is not set")

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

    day_date = date.fromisoformat(day)
    best = None
    best_delta = None

    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"])
        if dt.date() != day_date:
            continue
        delta = abs((dt - target_dt).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = item

    if not best:
        return fetch_weather_forecast(lat, lon, day)

    main = best["weather"][0]
    pop = best.get("pop", 0)
    condition = main.get("main", "unknown").lower()
    description = main.get("description", "")
    advice = (
        "Trời mưa — nên mang ô, cân nhắc Grab/xe buýt."
        if pop >= 0.5 or "rain" in condition or "mưa" in description.lower()
        else "Thời tiết thuận lợi cho di chuyển."
    )

    return {
        "source": "openweathermap",
        "available": True,
        "date": day,
        "at_time": target_time,
        "temp_c": round(best["main"]["temp"], 1),
        "rain_probability": round(pop, 2),
        "condition": condition,
        "description": description,
        "advice": advice,
    }


def _choose_recommendation_with_openrouter(
    title: str,
    day: str,
    arrive_by: str,
    from_place: Dict[str, Any],
    to_place: Dict[str, Any],
    options: List[Dict[str, Any]],
    weather: Dict[str, Any],
    previous_arrive: Optional[datetime],
) -> Dict[str, Any]:
    arrive_dt = _parse_time(day, arrive_by)
    available_gap_minutes = None
    if previous_arrive is not None:
        available_gap_minutes = int((arrive_dt - previous_arrive).total_seconds() / 60)

    payload = {
        "trip": {
            "title": title,
            "date": day,
            "arrive_by": arrive_by,
            "from": from_place,
            "to": to_place,
            "available_gap_minutes": available_gap_minutes,
        },
        "weather": weather,
        "commute_options": options,
        "instructions": [
            "Choose exactly one mode from the provided commute_options.",
            "Prefer realistic reasoning based on rain probability, duration, and cost.",
            "Do not invent data not present in the input.",
            "Return JSON only.",
        ],
        "output_schema": {
            "mode": "one of the modes from commute_options",
            "reason": "short Vietnamese explanation",
        },
    }

    data = _call_openrouter_json(
        json.dumps(payload, ensure_ascii=False),
        "You are a day-commute planner. Use only the given structured data. Return JSON only.",
    )

    chosen_mode = str(data.get("mode") or "").strip().lower()
    reason = str(data.get("reason") or "").strip()

    chosen = next((o for o in options if str(o.get("mode", "")).lower() == chosen_mode), None)
    if chosen is None:
        chosen = min(options, key=lambda x: x["minutes"])
        reason = reason or "OpenRouter không chọn được mode hợp lệ, nên dùng phương án nhanh nhất."

    return {
        **chosen,
        "reason": reason or "Phương án phù hợp nhất theo dữ liệu thời tiết và thời gian di chuyển.",
    }


def _analyze_leg(
    from_place: Dict[str, Any],
    to_place: Dict[str, Any],
    day: str,
    arrive_by: str,
    title: str,
    previous_arrive: Optional[datetime] = None,
) -> Dict[str, Any]:
    lat1, lon1 = from_place["lat"], from_place["lon"]
    lat2, lon2 = to_place["lat"], to_place["lon"]
    arrive_dt = _parse_time(day, arrive_by)

    try:
        options = build_commute_options(lat1, lon1, lat2, lon2)
    except ApiError as e:
        return {
            "ok": False,
            "title": title,
            "from": from_place["name"],
            "to": to_place["name"],
            "arrive_by": arrive_by,
            "error": str(e),
        }

    try:
        weather = _fetch_weather_at_time(lat2, lon2, day, arrive_by)
    except ApiError as e:
        weather = {"available": False, "error": str(e)}

    try:
        recommended = _choose_recommendation_with_openrouter(
            title=title,
            day=day,
            arrive_by=arrive_by,
            from_place=from_place,
            to_place=to_place,
            options=options,
            weather=weather,
            previous_arrive=previous_arrive,
        )
    except Exception:
        recommended = min(options, key=lambda x: x["minutes"])
        recommended = {
            **recommended,
            "reason": "Fallback sang phương án nhanh nhất do OpenRouter không trả kết quả hợp lệ.",
        }

    must_depart = (arrive_dt - timedelta(minutes=int(recommended["minutes"]))).strftime("%H:%M")

    buffer_minutes = None
    if previous_arrive is not None:
        buffer_minutes = int((arrive_dt - previous_arrive).total_seconds() / 60)

    return {
        "ok": True,
        "title": title,
        "from_name": from_place["name"],
        "to_name": to_place["name"],
        "from_lat": lat1,
        "from_lon": lon1,
        "to_lat": lat2,
        "to_lon": lon2,
        "arrive_by": arrive_by,
        "should_depart_by": must_depart,
        "weather_at_destination": weather,
        "commute_options": options,
        "recommended": recommended,
        "buffer_before_arrival_minutes": buffer_minutes,
    }


def plan_day_schedule(schedule_json: str) -> str:
    try:
        data = json.loads(schedule_json) if isinstance(schedule_json, str) else schedule_json
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}, ensure_ascii=False)

    day = data.get("date") or date.today().isoformat()
    home_raw = data.get("home") or data.get("start_location")
    stops = data.get("stops") or data.get("timeline") or []

    if not home_raw:
        return json.dumps({"ok": False, "error": "Missing 'home'"}, ensure_ascii=False)
    if not stops:
        return json.dumps({"ok": False, "error": "Missing 'stops': list of {time, location, title}"}, ensure_ascii=False)

    try:
        home_place = _resolve_place(str(home_raw))
    except Exception as e:
        return json.dumps({"ok": False, "error": f"Không resolve được home: {e}"}, ensure_ascii=False)

    legs: List[Dict[str, Any]] = []
    current_place = home_place
    previous_arrive: Optional[datetime] = None

    for i, stop in enumerate(stops):
        time_str = stop.get("time") or stop.get("arrive_at")
