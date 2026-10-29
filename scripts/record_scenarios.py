"""
Records live runs of the three demo scenarios for offline use (Recorded mode in the UI).

- Starts every recording from a clean demo database.
- Refuses to overwrite a recording with a degraded run (model or search failure), so a bad
  network moment can never put a fallback into your demo.
- Needs NEBIUS_API_KEY and TAVILY_API_KEY in backend/.env.

Usage: python scripts/record_scenarios.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from api import run_scan  # noqa: E402
from engine import reset_demo_state  # noqa: E402

# Keep these in sync with frontend/src/constants.js
SCENARIOS = {
    "taiwan_semiconductor": "Taiwan earthquake TSMC fab shutdown automotive semiconductor supply",
    "poland_battery": "Poland battery cell plant production disruption EV supply",
    "japan_sensor": "Japan port logistics disruption automotive radar sensor",
}


def record_all() -> None:
    cache_dir = BACKEND_DIR / "cache" / "scenarios"
    cache_dir.mkdir(parents=True, exist_ok=True)
    print("=== Recording CrisisSentinel scenarios ===")
    saved = 0
    for key, query in SCENARIOS.items():
        print(f"\n[{key}] {query}")
        reset_demo_state()
        try:
            result = run_scan(query, emit=lambda ev: print(f"   {ev['stage']:<14} {ev['status']:<7} {ev.get('message', '')}"))
        except Exception as exc:
            print(f"  FAILED: {exc}")
            continue
        problems = result["provenance"]["degraded"] or ([] if result["matched"] else ["no exposure found"])
        if problems:
            print(f"  NOT SAVED: degraded or empty run ({', '.join(problems)}). Existing recording kept.")
            continue
        (cache_dir / f"{key}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"  saved {key}.json  (verdict: {result['critique']['verdict']}, {result['provenance']['total_s']}s)")
        saved += 1
    reset_demo_state()
    print(f"\nDone: {saved}/{len(SCENARIOS)} recordings updated.")


if __name__ == "__main__":
    record_all()
