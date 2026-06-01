import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.commute_tools import execute_tool
from src.tools.districts import resolve_district
from src.tools.day_planner import format_day_plan_text, plan_day_schedule


SAMPLE = json.dumps(
    {
        "date": "2026-06-02",
        "home": "QBT",
        "stops": [
            {"time": "08:00", "location": "Q1", "title": "Làm việc"},
            {"time": "17:30", "location": "QBT", "title": "Về nhà"},
        ],
    }
)

MOCK_OPTIONS = [
    {"mode": "motorbike", "minutes": 25, "cost_vnd": 15000, "note": "", "source": "osrm"},
    {"mode": "bus", "minutes": 40, "cost_vnd": 7000, "note": "", "source": "estimate"},
    {"mode": "grab", "minutes": 28, "cost_vnd": 65000, "note": "", "source": "estimate"},
]

MOCK_WEATHER = {
    "available": True,
    "date": "2026-06-02",
    "at_time": "08:00",
    "temp_c": 32,
    "rain_probability": 0.2,
    "condition": "clouds",
    "description": "mây",
    "advice": "OK",
}


def test_resolve_district():
    code, err = resolve_district("Bình Thạnh")
    assert code == "QBT" and err is None


@patch("src.tools.day_planner.build_commute_options", return_value=MOCK_OPTIONS)
@patch("src.tools.day_planner._fetch_weather_at_time", return_value=MOCK_WEATHER)
def test_plan_day_schedule(mock_w, mock_c):
    data = json.loads(plan_day_schedule(SAMPLE))
    assert data["ok"] is True
    assert len(data["legs"]) == 2
    assert "summary_vi" in data
    assert data["legs"][0]["recommended"]["mode"] in ("motorbike", "bus", "grab")


@patch("src.tools.day_planner.build_commute_options", return_value=MOCK_OPTIONS)
@patch("src.tools.day_planner._fetch_weather_at_time", return_value={**MOCK_WEATHER, "rain_probability": 0.8})
def test_plan_recommends_grab_in_rain(mock_w, mock_c):
    data = json.loads(plan_day_schedule(SAMPLE))
    assert data["legs"][0]["recommended"]["mode"] in ("grab", "bus")


def test_execute_tool_plan():
    with patch("src.tools.day_planner.build_commute_options", return_value=MOCK_OPTIONS):
        with patch("src.tools.day_planner._fetch_weather_at_time", return_value=MOCK_WEATHER):
            raw = execute_tool("plan_day_schedule", {"schedule_json": SAMPLE})
    assert json.loads(raw)["ok"] is True


def test_format_text():
    result = {
        "ok": True,
        "date": "2026-06-02",
        "legs": [
            {
                "title": "A",
                "from_name": "Bình Thạnh",
                "to_name": "Quận 1",
                "arrive_by": "08:00",
                "should_depart_by": "07:35",
                "weather_at_destination": MOCK_WEATHER,
                "commute_options": MOCK_OPTIONS,
                "recommended": {**MOCK_OPTIONS[0], "reason": "test"},
            }
        ],
        "summary_vi": "ok",
    }
    text = format_day_plan_text(result)
    assert "Quận 1" in text and "motorbike" in text
