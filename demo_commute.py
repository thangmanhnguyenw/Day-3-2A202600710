#!/usr/bin/env python3
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

# Ưu tiên file hybrid/Gemini nếu có, fallback về day_planner cũ.
try:
    from src.tools.day_planner_gemini_hybrid import format_day_plan_text, plan_day_schedule
except ImportError:
    from src.tools.day_planner import format_day_plan_text, plan_day_schedule


def load_schedule(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def input_schedule_interactive() -> str:
    print("=== Nhập lịch trong ngày (Gemini + API) ===\n")
    day = input("Ngày (YYYY-MM-DD, Enter = hôm nay): ").strip()
    home = input("Xuất phát từ đâu? (vd: Vinhomes Ocean Park / VinUniversity / Quận 1...): ").strip()
    stops = []

    print("Nhập từng mốc theo dạng: time | location | title")
    print("VD: 08:00 | VinUniversity | Đi học")
    print("Dòng trống để kết thúc.\n")

    while True:
        line = input(f"Mốc {len(stops) + 1}: ").strip()
        if not line:
            break

        if "|" in line:
            parts = [p.strip() for p in line.split("|", maxsplit=2)]
        else:
            parts = line.split(maxsplit=2)

        if len(parts) < 2:
            print("  Cần ít nhất: time và location (VD: 08:00 | VinUniversity | Đi học)")
            continue

        time_str = parts[0]
        location = parts[1]
        title = parts[2] if len(parts) > 2 else f"Mốc {len(stops) + 1}"

        stops.append(
            {
                "time": time_str,
                "location": location,
                "title": title,
            }
        )

    payload = {"home": home, "stops": stops}
    if day:
        payload["date"] = day
    return json.dumps(payload, ensure_ascii=False)


def main() -> None:
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("Cảnh báo: thiếu GEMINI_API_KEY (hoặc GOOGLE_API_KEY) trong .env\n")

    if not os.getenv("OPENWEATHER_API_KEY"):
        print("Cảnh báo: thiếu OPENWEATHER_API_KEY trong .env\n")

    if len(sys.argv) > 1:
        schedule_json = load_schedule(sys.argv[1])
    else:
        sample = os.path.join(os.path.dirname(__file__), "data", "sample_day_plan.json")
        if os.path.exists(sample):
            use = input(f"Dùng mẫu {sample}? [Y/n]: ").strip().lower()
            if use in ("", "y", "yes"):
                schedule_json = load_schedule(sample)
            else:
                schedule_json = input_schedule_interactive()
        else:
            schedule_json = input_schedule_interactive()

    raw = plan_day_schedule(schedule_json)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print("\nKết quả thô:")
        print(raw)
        return

    print("\n" + format_day_plan_text(result))


if __name__ == "__main__":
    main()