"""
CrisisSentinel command-line run: the same pipeline the API uses, printed to the terminal.
Usage: python main.py "Taiwan semiconductor supply chain disruption"
"""
import sys

from api import run_scan


def main() -> None:
    query = " ".join(sys.argv[1:]) or "Taiwan semiconductor supply chain disruption"
    print(f"Investigating: {query}\n")
    result = run_scan(query, emit=lambda ev: print(f"  [{ev['stage']:<14}] {ev['status']:<7} {ev.get('message', '')}"))

    intel, exposure, brief, critique = result["intelligence"], result["exposure"], result["brief"], result["critique"]
    print(f"\nEvent: {intel['event']}\nCountry/category: {intel['impacted_country']} / {intel['impacted_category']}  (extraction: {intel['extraction_method']})")
    if not result["matched"]:
        print(f"\nNo exposure: {exposure.get('message')}")
        return
    print(f"\nExposure: €{exposure['total_exposure_eur']:,.2f} across {exposure['open_pos_count']} open POs; shortest runway {exposure['critical_runway_days']} days")
    print(f"\nBrief ({brief['brief_source']}): {brief['headline']}")
    for a in brief["recommended_actions"]:
        print(f"  [{a['priority']}] {a['title']}  | PO {a['po_id']} -> {a['target_supplier_id'] or 'n/a'} | order value €{a['value_rerouted_eur']:,.0f}")
    print(f"\nCritic verdict: {critique['verdict']} ({critique['status']})")
    for c in critique["checks"]:
        print(f"  {'PASS' if c['passed'] else 'FAIL'}  {c['label']}")
    print(f"\nDegraded stages: {result['provenance']['degraded'] or 'none'}")


if __name__ == "__main__":
    main()
