"""HCMC district codes and coordinates (for API geolocation, not mock business data)."""

import re
from typing import Dict, Optional, Tuple

DISTRICTS: Dict[str, Dict] = {
    "Q1": {
        "name": "Quận 1",
        "lat": 10.7769,
        "lon": 106.7009,
        "aliases": ["quan 1", "quận 1", "district 1"],
    },
    "QBT": {
        "name": "Bình Thạnh",
        "lat": 10.8106,
        "lon": 106.7091,
        "aliases": ["binh thanh", "bình thạnh"],
    },
    "Q7": {
        "name": "Quận 7",
        "lat": 10.7340,
        "lon": 106.7219,
        "aliases": ["quan 7", "quận 7", "district 7"],
    },
    "Q3": {
        "name": "Quận 3",
        "lat": 10.7843,
        "lon": 106.6845,
        "aliases": ["quan 3", "quận 3", "district 3"],
    },
}

FAQ: Dict[str, str] = {
    "bus_payment": "Trả bằng thẻ xe buýt hoặc tiền mặt tùy tuyến (tham khảo TP.HCM).",
    "peak_hours": "Giờ cao điểm thường: 7h–9h và 17h–19h.",
}


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def resolve_district(code_or_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolve district code from code (Q1) or alias (Bình Thạnh)."""
    if not code_or_name or not str(code_or_name).strip():
        return None, "district_code is required"

    raw = str(code_or_name).strip()
    upper = raw.upper()
    if upper in DISTRICTS:
        return upper, None

    normalized = _normalize_key(raw)
    for code, info in DISTRICTS.items():
        if _normalize_key(info["name"]) == normalized:
            return code, None
        for alias in info.get("aliases", []):
            if _normalize_key(alias) == normalized:
                return code, None

    valid = ", ".join(f"{c} ({d['name']})" for c, d in DISTRICTS.items())
    return None, f"Unknown district '{raw}'. Use: {valid}"
