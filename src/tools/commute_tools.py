"""
Commute lab — simplified: one tool `plan_day_schedule` for a full day timeline.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from src.tools.day_planner import format_day_plan_text, plan_day_schedule
from src.tools.districts import FAQ, resolve_district


def get_faq(topic: str) -> str:
    key = topic.strip().lower().replace(" ", "_")
    if key in FAQ:
        return json.dumps({"ok": True, "topic": key, "answer": FAQ[key]}, ensure_ascii=False)
    return json.dumps(
        {"ok": False, "error": f"Unknown topic '{topic}'", "available_topics": list(FAQ.keys())},
        ensure_ascii=False,
    )


def _tool_entry(
    name: str,
    description: str,
    handler: Callable[..., str],
    parameters: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": parameters,
        "handler": handler,
    }


def get_commute_tools() -> List[Dict[str, Any]]:
    return [
        _tool_entry(
            "plan_day_schedule",
            (
                "Phân tích cả ngày: nhập JSON gồm date, home (quận xuất phát), "
                "stops [{time, location, title}]. "
                "Trả về thời tiết lúc đến, thời gian & giá xe máy/bus/grab từng chặng, "
                "giờ nên rời và gợi ý phương tiện. "
                "location/home: Q1, QBT, Q7, Q3 hoặc tên quận tiếng Việt. "
                "Cần OPENWEATHER_API_KEY; lộ trình qua OSRM."
            ),
            plan_day_schedule,
            {"schedule_json": "str (JSON)"},
        ),
    ]


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    for tool in get_commute_tools():
        if tool["name"] == name:
            handler: Callable[..., str] = tool["handler"]
            try:
                return handler(**arguments)
            except TypeError as e:
                return json.dumps(
                    {"ok": False, "error": f"Invalid arguments for {name}: {e}"},
                    ensure_ascii=False,
                )
    return json.dumps({"ok": False, "error": f"Tool '{name}' not found"}, ensure_ascii=False)


def get_tools():
    return get_commute_tools()
