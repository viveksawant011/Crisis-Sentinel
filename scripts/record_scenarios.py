"""
Pre-records live runs of the 3 primary scenarios for offline demo safety.
Saves results into backend/cache/scenarios/
"""

import os
import sys
import json
from pathlib import Path

# Add backend directory to module search path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from api import scan_disruption, ScanRequest

SCENARIOS = {
    "taiwan_semiconductor": "Taiwan earthquake TSMC fab shutdown automotive semiconductor supply",
    "poland_battery": "Poland battery cell plant production disruption EV supply",
    "japan_sensor": "Japan port logistics disruption automotive radar sensor"
}

def record_all():
    cache_dir = BACKEND_DIR / "cache" / "scenarios"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("=== Recording CrisisSentinel Scenario Cache ===")
    for key, query in SCENARIOS.items():
        print(f"\n[Recording] {key}...")
        try:
            result = scan_disruption(ScanRequest(query=query))
            target_file = cache_dir / f"{key}.json"
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"  ✓ Saved cached response to: {target_file}")
        except Exception as e:
            print(f"  ✗ Failed to record {key}: {e}")

    print("\n✓ Pre-recording complete. Offline cache ready for demo.")

if __name__ == "__main__":
    record_all()