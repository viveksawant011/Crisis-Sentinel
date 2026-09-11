"""
CrisisSentinel End-to-End Execution Pipeline.
"""

from tavily_nemotron_probe import research, analyze_disruption, resolve_nemotron_model
from engine import evaluate_erp_exposure
from strategist import generate_mitigation_strategy

def run_pipeline(crisis_query: str):
    print("=" * 60)
    print("STAGE 1: EXTERNAL DISRUPTION EXTRACTION (Tavily + Nemotron Nano)")
    print("=" * 60)
    nano_model = resolve_nemotron_model()
    print(f"Searching web: '{crisis_query}'")
    sources = research(crisis_query)
    analysis = analyze_disruption(crisis_query, sources, nano_model)
    print(f"Identified: Country={analysis.impacted_country} | Category={analysis.impacted_category} | Severity={analysis.severity}")

    print("\n" + "=" * 60)
    print("STAGE 2: DETERMINISTIC ENTERPRISE EXPOSURE (SQLite Engine)")
    print("=" * 60)
    erp_exposure = evaluate_erp_exposure(analysis.impacted_country, analysis.impacted_category)
    
    if not erp_exposure["matched"]:
        print(f"Zero exposure: {erp_exposure['message']}")
        return

    print(f"Exposed Open POs:    {erp_exposure['open_pos_count']}")
    print(f"Financial Exposure:  €{erp_exposure['total_exposure_eur']:,.2f}")
    print(f"Critical Runway:     {erp_exposure['critical_runway_days']} Days Remaining")
    print(f"Alternative Routes:  {len(erp_exposure['mitigation_alternatives'])} available")

    print("\n" + "=" * 60)
    print("STAGE 3: EXECUTIVE MITIGATION BRIEF (Nemotron Strategist)")
    print("=" * 60)
    brief = generate_mitigation_strategy(analysis.model_dump(), erp_exposure)
    print(f"Headline: {brief.headline}\n")
    for action in brief.recommended_actions:
        print(f"[{action.priority}] {action.title} ({action.action_type})")
        print(f"    Plant: {action.target_plant} | Component: {action.target_material}")
        print(f"    Rationale: {action.rationale}")
        print(f"    Est. Cost: €{action.estimated_cost_eur:,.2f}\n")

if __name__ == "__main__":
    run_pipeline("Taiwan semiconductor supply chain disruption 2026")