"""
Step 1 milestone for CrisisSentinel: prove Tavily -> Nemotron -> structured JSON
works reliably, before touching LangGraph, the database, or the UI.
"""

import os
import json
import re
from typing import List, Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 0. Load Environment First
# ---------------------------------------------------------------------------
load_dotenv()

# Verify keys exist before importing clients
if "TAVILY_API_KEY" not in os.environ or "NEBIUS_API_KEY" not in os.environ:
    raise ValueError(
        "Missing keys! Ensure backend/.env exists and contains TAVILY_API_KEY and NEBIUS_API_KEY."
    )

from tavily import TavilyClient
from openai import OpenAI
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# 1. Config & Clients
# ---------------------------------------------------------------------------
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
FALLBACK_NANO_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
nebius_client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ["NEBIUS_API_KEY"],
)

# ---------------------------------------------------------------------------
# 2. Dynamic Model Resolver
# ---------------------------------------------------------------------------
def resolve_nemotron_model() -> str:
    """Finds the exact active Nemotron Nano model ID on your Nebius account."""
    try:
        models = nebius_client.models.list()
        nemotron_models = [
            m.id for m in models.data 
            if "nemotron" in m.id.lower()
        ]
        print(f"Found {len(nemotron_models)} Nemotron-family model(s) on your account:")
        for m in nemotron_models:
            print(f"  - {m}")
        
        # Priority: choose a nano model for fast extraction, otherwise pick the first Nemotron
        nano_matches = [m for m in nemotron_models if "nano" in m.lower()]
        if nano_matches:
            selected = nano_matches[0]
        elif nemotron_models:
            selected = nemotron_models[0]
        else:
            selected = FALLBACK_NANO_MODEL

        print(f"\n[Active Model Selected]: {selected}")
        return selected
    except Exception as e:
        print(f"Warning: Could not fetch models dynamically ({e}). Using fallback: {FALLBACK_NANO_MODEL}")
        return FALLBACK_NANO_MODEL

# ---------------------------------------------------------------------------
# 3. Target Output Schema (Matches Hackathon Charter Step 5)
# ---------------------------------------------------------------------------
class DisruptionAnalysis(BaseModel):
    event: str
    location: str
    severity: str  # "low" | "medium" | "high" | "critical"
    affected_materials: List[str]
    affected_suppliers: List[str]
    evidence: List[str]          # short evidence snippets, one per source used
    conflicting_claims: List[str]  # empty list if none found
    confidence: Optional[float] = None  # 0-1, model's self-rated confidence

# ---------------------------------------------------------------------------
# 4. Tavily Research Step
# ---------------------------------------------------------------------------
def research(query: str, max_results: int = 8, search_depth: str = "basic") -> list[dict]:
    """Runs a Tavily search and returns titles, URLs, and snippet contents."""
    response = tavily_client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        include_answer=False,
    )
    sources = []
    for r in response.get("results", []):
        sources.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        })
    return sources

# ---------------------------------------------------------------------------
# 5. Nemotron Structured Extraction
# ---------------------------------------------------------------------------
def clean_json_string(raw: str) -> str:
    """Strips Markdown backticks and extraneous prose if the model returns them."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw

def analyze_disruption(event_query: str, sources: list[dict], model_id: str) -> DisruptionAnalysis:
    """Feeds sources into Nemotron and enforces a valid DisruptionAnalysis JSON."""
    sources_block = "\n\n".join(
        f"SOURCE {i+1}: {s['title']}\nURL: {s['url']}\nCONTENT: {s['content'][:1200]}"
        for i, s in enumerate(sources)
    )

    schema_str = json.dumps(DisruptionAnalysis.model_json_schema(), indent=2)

    system_prompt = (
        "You are an enterprise disruption extraction engine for CrisisSentinel. "
        "Analyze the provided search sources. Extract ONLY facts supported by the text. "
        "If sources contradict each other, record the dispute in conflicting_claims. "
        "Do NOT hallucinate suppliers or part numbers not explicitly mentioned in the text.\n\n"
        "Respond with a single valid JSON object strictly matching this schema:\n"
        f"{schema_str}"
    )

    user_prompt = f"EVENT TO INVESTIGATE: {event_query}\n\n{sources_block}"

    last_error = None
    for attempt in range(2):
        try:
            completion = nebius_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Lower temperature guarantees extraction fidelity
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
            cleaned = clean_json_string(raw)
            data = json.loads(cleaned)
            return DisruptionAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValidationError, Exception) as e:
            last_error = e
            print(f"  [Attempt {attempt + 1} validation failed, retrying...] Error: {e}")

    raise RuntimeError(f"Nemotron failed to produce valid schema output: {last_error}")

# ---------------------------------------------------------------------------
# 6. Main Execution
# ---------------------------------------------------------------------------
def main():
    print("=== CrisisSentinel: Day-1 Extraction Probe ===")
    active_model = resolve_nemotron_model()

    query = "Taiwan semiconductor supply chain disruption 2026"
    print(f"\n=== Running Tavily Research: '{query}' (basic depth) ===")
    sources = research(query)
    print(f"Retrieved {len(sources)} sources.")
    for s in sources[:3]:
        print(f"  * {s['title']} ({s['url']})")

    print(f"\n=== Extracting structured data using {active_model} ===")
    result = analyze_disruption(query, sources, active_model)

    print("\n=== VALIDATED OUTPUT (Pydantic Schema) ===")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    main()