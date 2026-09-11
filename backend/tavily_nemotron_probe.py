"""
CrisisSentinel: External Intelligence (Tavily + Nemotron) -> Internal ERP Engine (SQLite).
"""

import os
import json
import re
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

from tavily import TavilyClient
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from engine import evaluate_erp_exposure

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
FALLBACK_NANO_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
nebius_client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ["NEBIUS_API_KEY"],
)

def resolve_nemotron_model() -> str:
    try:
        models = nebius_client.models.list()
        nemotron_models = [m.id for m in models.data if "nemotron" in m.id.lower()]
        nano_matches = [m for m in nemotron_models if "nano" in m.lower()]
        return nano_matches[0] if nano_matches else (nemotron_models[0] if nemotron_models else FALLBACK_NANO_MODEL)
    except Exception:
        return FALLBACK_NANO_MODEL

# ---------------------------------------------------------------------------
# Target Output Schema: High-Level Real-World Taxonomy Only
# ---------------------------------------------------------------------------
class DisruptionAnalysis(BaseModel):
    event: str
    impacted_country: str               # e.g., "Taiwan"
    impacted_category: str              # e.g., "semiconductor", "battery component", "sensor"
    severity: str                       # "low" | "medium" | "high" | "critical"
    real_world_entities_mentioned: List[str]  # e.g., ["TSMC", "Hsinchu Science Park"]
    evidence: List[str]
    conflicting_claims: List[str]
    confidence: Optional[float] = None

def research(query: str, max_results: int = 8) -> list[dict]:
    response = tavily_client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False,
    )
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in response.get("results", [])
    ]

def clean_json_string(raw: str) -> str:
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    return match.group(1).strip() if match else raw

def analyze_disruption(event_query: str, sources: list[dict], model_id: str) -> DisruptionAnalysis:
    sources_block = "\n\n".join(
        f"SOURCE {i+1}: {s['title']}\nURL: {s['url']}\nCONTENT: {s['content'][:1200]}"
        for i, s in enumerate(sources)
    )

    system_prompt = (
        "You are an enterprise disruption extraction engine for CrisisSentinel. "
        "Analyze external news sources. Extract ONLY facts supported by the text. "
        "Standardize 'impacted_category' to one of: ['semiconductor', 'battery component', 'sensor']. "
        "Standardize 'impacted_country' to the primary sovereign nation/territory (e.g., 'Taiwan'). "
        "Do NOT invent internal customer part codes or customer supplier names.\n\n"
        f"Respond ONLY with a JSON object conforming to:\n{json.dumps(DisruptionAnalysis.model_json_schema(), indent=2)}"
    )

    completion = nebius_client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"EVENT TO INVESTIGATE: {event_query}\n\n{sources_block}"},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    cleaned = clean_json_string(completion.choices[0].message.content or "")
    return DisruptionAnalysis.model_validate(json.loads(cleaned))

def main():
    active_model = resolve_nemotron_model()
    query = "Taiwan semiconductor supply chain disruption 2026"
    
    print(f"1. Researching live event: '{query}'")
    sources = research(query)
    
    print(f"2. Extracting intelligence with {active_model}")
    analysis = analyze_disruption(query, sources, active_model)
    print("\n--- EXTRACTED REAL-WORLD INTELLIGENCE ---")
    print(analysis.model_dump_json(indent=2))

    print("\n--- QUERYING VOLTAUTO ERP DATABASE ---")
    erp_impact = evaluate_erp_exposure(
        country=analysis.impacted_country,
        category=analysis.impacted_category,
        db_path="voltauto.db"
    )

    if erp_impact["matched"]:
        print(f"Status:             CRITICAL EXPOSURE IDENTIFIED")
        print(f"Matched Country:    {erp_impact['impacted_country']}")
        print(f"Matched Category:   {erp_impact['impacted_category']}")
        print(f"Total Open POs:     {erp_impact['open_pos_count']} orders")
        print(f"Financial Exposure: €{erp_impact['total_exposure_eur']:,.2f}")
        print(f"Shortest Runway:    {erp_impact['critical_runway_days']} days")
        print(f"Alternative Reroutings Available: {len(erp_impact['mitigation_alternatives'])}")
    else:
        print(f"Status: CLEAN - {erp_impact['message']}")

if __name__ == "__main__":
    main()