"""
Plan one day: user timeline (time + location) → weather, commute options, recommendations.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.tools.api_client import ApiError, build_commute_options, fetch_weather_forecast
from src.tools.districts import DISTRICTS, resolve_district


def _parse_time(day: str, time_str: str) -> datetime:
    """time_str: HH:MM or HH:MM:SS"""
    t = time_str.strip()
    if len(t) == 5:
        t += ":00"
    return datetime.fromisoformat(f"{day}T{t}")


def _fetch_weather_at_time(lat: float, lon: float, day: str, depart_time: str) -> Dict[str, Any]:
    """Forecast closest to departure hour (uses OpenWeather 3h slots)."""
    if not depart_time:
        return fetch_weather_forecast(lat, lon, day)

    target_dt = _parse_time(day, depart_time)
    from src.tools.api_client import OPENWEATHER_API_KEY, _get

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
        "at_time": depart_time,
        "temp_c": round(best["main"]["temp"], 1),
        "rain_probability": round(pop, 2),
        "condition": condition,
        "description": description,
        "advice": advice,
    }


def _recommend_mode(
    options: List[Dict[str, Any]],
    weather: Dict[str, Any],
    buffer_minutes: Optional[int],
) -> Dict[str, Any]:
    """Pick bus / motorbike / grab with short reason."""
    by_mode = {o["mode"]: o for o in options if o["mode"] in ("bus", "motorbike", "grab")}
    if not by_mode:
        return {"mode": options[0]["mode"], "reason": "Chỉ có một phương tiện khả dụng."}

    rain = weather.get("rain_probability", 0) or 0
    motorbike = by_mode.get("motorbike")
    bus = by_mode.get("bus")
    grab = by_mode.get("grab")

    if buffer_minutes is not None and buffer_minutes < 0:
        fastest = min(by_mode.values(), key=lambda x: x["minutes"])
        return {
            "mode": fastest["mode"],
            "reason": "Không đủ thời gian — chọn phương tiện nhanh nhất.",
            "urgent": True,
        }

    if rain >= 0.6:
        choice = grab or bus or motorbike
        return {
            "mode": choice["mode"],
            "reason": "Dự báo mưa — ưu tiên ít phơi nắng/mưa (Grab hoặc xe buýt).",
        }

    if buffer_minutes is not None and buffer_minutes <= 10 and grab:
        return {
            "mode": "grab",
            "reason": "Sát giờ — Grab thường ổn định hơn so với chờ bus.",
        }

    if motorbike:
        return {
            "mode": "motorbike",
            "reason": "Xe máy cân bằng thời gian và chi phí cho đường nội đô.",
        }

    return {"mode": bus["mode"], "reason": "Xe buýt tiết kiệm chi phí."}


def _analyze_leg(
    from_code: str,
    to_code: str,
    day: str,
    arrive_by: str,
    title: str,
    previous_arrive: Optional[datetime] = None,
) -> Dict[str, Any]:
    lat1, lon1 = DISTRICTS[from_code]["lat"], DISTRICTS[from_code]["lon"]
    lat2, lon2 = DISTRICTS[to_code]["lat"], DISTRICTS[to_code]["lon"]

    arrive_dt = _parse_time(day, arrive_by)
    try:
        options = build_commute_options(lat1, lon1, lat2, lon2)
    except ApiError as e:
        return {
            "ok": False,
            "title": title,
            "from": from_code,
            "to": to_code,
            "arrive_by": arrive_by,
            "error": str(e),
        }

    fastest = min(options, key=lambda o: o["minutes"])
    buffer_minutes = None
    if previous_arrive is not None:
        buffer_minutes = int((arrive_dt - previous_arrive).total_seconds() / 60)

    try:
        weather = _fetch_weather_at_time(lat2, lon2, day, arrive_by)
    except ApiError as e:
        weather = {"available": False, "error": str(e)}

    # Time available to travel after previous event ends
    travel_buffer = buffer_minutes
    if previous_arrive is not None and buffer_minutes is not None:
        travel_buffer = buffer_minutes  # gap between events; user should leave after prev ends
        # Assume previous event ends just before next arrive time is WRONG - 
        # buffer is time from prev scheduled time to next - we use as loose window
        # Better: must_depart = arrive_dt - recommended minutes
        pass

    rec = _recommend_mode(
        options,
        weather,
        (travel_buffer - fastest["minutes"]) if travel_buffer is not None else None,
    )
    chosen = next((o for o in options if o["mode"] == rec["mode"]), fastest)
    must_depart = (arrive_dt - timedelta(minutes=chosen["minutes"])).strftime("%H:%M")

    return {
        "ok": True,
        "title": title,
        "from_district": from_code,
        "from_name": DISTRICTS[from_code]["name"],
        "to_district": to_code,
        "to_name": DISTRICTS[to_code]["name"],
        "arrive_by": arrive_by,
        "should_depart_by": must_depart,
        "weather_at_destination": weather,
        "commute_options": options,
        "recommended": {**rec, **chosen},
        "buffer_before_arrival_minutes": travel_buffer,
    }


def plan_day_schedule(schedule_json: str) -> str:
    """
    Main tool: analyze a full day timeline.

    Input JSON example:
    {
      "date": "2026-06-02",
      "home": "QBT",
      "stops": [
        {"time": "08:00", "location": "Q1", "title": "Đi làm"},
        {"time": "12:00", "location": "Q3", "title": "Ăn trưa"},
        {"time": "17:30", "location": "QBT", "title": "Về nhà"}
      ]
    }

    location: district code (Q1, QBT, Q7, Q3) or Vietnamese name.
    """
    try:
        data = json.loads(schedule_json) if isinstance(schedule_json, str) else schedule_json
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}, ensure_ascii=False)

    day = data.get("date") or date.today().isoformat()
    home_raw = data.get("home") or data.get("start_location")
    stops = data.get("stops") or data.get("timeline") or []

    if not home_raw:
        return json.dumps(
            {"ok": False, "error": "Missing 'home' (điểm xuất phát, ví dụ QBT)"},
            ensure_ascii=False,
        )
    if not stops:
        return json.dumps(
            {"ok": False, "error": "Missing 'stops': list of {time, location, title}"},
            ensure_ascii=False,
        )

    home_code, home_err = resolve_district(home_raw)
    if home_err:
        return json.dumps({"ok": False, "error": home_err}, ensure_ascii=False)

    legs: List[Dict[str, Any]] = []
    current = home_code
    previous_arrive: Optional[datetime] = None

    for i, stop in enumerate(stops):
        time_str = stop.get("time") or stop.get("arrive_at")
        loc_raw = stop.get("location") or stop.get("district")
        title = stop.get("title") or stop.get("name") or f"Mốc {i + 1}"

        if not time_str or not loc_raw:
            return json.dumps(
                {"ok": False, "error": f"Stop {i + 1} needs 'time' and 'location'"},
                ensure_ascii=False,
            )

        to_code, loc_err = resolve_district(loc_raw)
        if loc_err:
            return json.dumps({"ok": False, "error": loc_err}, ensure_ascii=False)

        leg = _analyze_leg(current, to_code, day, time_str, title, previous_arrive)
        legs.append(leg)
        if not leg.get("ok"):
            return json.dumps(
                {"ok": False, "error": leg.get("error"), "partial_legs": legs},
                ensure_ascii=False,
            )

        current = to_code
        previous_arrive = _parse_time(day, time_str)

    summary_lines = []
    for leg in legs:
        w = leg["weather_at_destination"]
        r = leg["recommended"]
        rain = w.get("rain_probability", "?")
        summary_lines.append(
            f"{leg['arrive_by']} → {leg['to_name']}: nên đi {r['mode']} "
            f"({r['minutes']} phút, ~{r['cost_vnd']:,}đ). Rời trước {leg['should_depart_by']}. "
            f"Mưa {rain}. {r.get('reason', '')}"
        )

    return json.dumps(
        {
            "ok": True,
            "date": day,
            "home": home_code,
            "legs": legs,
            "summary_vi": "\n".join(summary_lines),
        },
        ensure_ascii=False,
    )


def format_day_plan_text(result: Dict[str, Any]) -> str:
    """Human-readable report for CLI."""
    if not result.get("ok"):
        return f"Lỗi: {result.get('error')}"

    lines = [f"=== Kế hoạch di chuyển ngày {result['date']} ===\n"]
    for i, leg in enumerate(result.get("legs", []), 1):
        lines.append(f"--- Chặng {i}: {leg['title']} ---")
        lines.append(f"  {leg['from_name']} → {leg['to_name']}, đến trước {leg['arrive_by']}")
        lines.append(f"  Nên rời lúc: {leg['should_depart_by']}")
        w = leg["weather_at_destination"]
        if w.get("available"):
            lines.append(
                f"  Thời tiết: {w.get('description', w.get('condition'))}, "
                f"{w.get('temp_c')}°C, mưa {int((w.get('rain_probability') or 0) * 100)}%"
            )
            lines.append(f"  → {w.get('advice', '')}")
        lines.append("  Phương tiện:")
        for o in leg["commute_options"]:
            mark = " ★" if o["mode"] == leg["recommended"]["mode"] else ""
            lines.append(
                f"    - {o['mode']}: {o['minutes']} phút, ~{o['cost_vnd']:,} VND{mark}"
            )
        lines.append(f"  Gợi ý: {leg['recommended']['mode']} — {leg['recommended'].get('reason', '')}\n")
    lines.append("=== Tóm tắt ===")
    lines.append(result.get("summary_vi", ""))
    return "\n".join(lines)
