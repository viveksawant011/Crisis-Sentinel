"""
CrisisSentinel: External Intelligence (Tavily + Nemotron) -> Internal ERP Engine (SQLite).
"""

import os
import json
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from tavily import TavilyClient
from openai import OpenAI
from pydantic import BaseModel, Field

from llm_json import chat_json
from normalizer import normalize_category, normalize_country, get_db_vocabulary

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
FALLBACK_NANO_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
nebius_client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ.get("NEBIUS_API_KEY") or "missing-key",
    timeout=60.0,
    max_retries=1,
)

_CACHED_NANO_MODEL: Optional[str] = None
_CACHED_SUPER_MODEL: Optional[str] = None

def resolve_nemotron_model() -> str:
    """Finds the active Nemotron Nano model ID on Nebius."""
    global _CACHED_NANO_MODEL
    if _CACHED_NANO_MODEL:
        return _CACHED_NANO_MODEL
    try:
        models = nebius_client.models.list()
        nemotron_models = [m.id for m in models.data if "nemotron" in m.id.lower()]
        nano_matches = [m for m in nemotron_models if "nano" in m.lower()]
        _CACHED_NANO_MODEL = nano_matches[0] if nano_matches else nemotron_models[0]
    except Exception:
        _CACHED_NANO_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    return _CACHED_NANO_MODEL


def resolve_super_model() -> str:
    """Finds the exact lowercase Nemotron Super model on Nebius."""
    global _CACHED_SUPER_MODEL
    if _CACHED_SUPER_MODEL:
        return _CACHED_SUPER_MODEL
    try:
        models = nebius_client.models.list()
        # Find exact matches from your account
        for m in models.data:
            m_lower = m.id.lower()
            if "nemotron-3-super" in m_lower or "super-120b" in m_lower:
                _CACHED_SUPER_MODEL = m.id
                return _CACHED_SUPER_MODEL
        # If not found in loop, check for ultra or lightning
        for m in models.data:
            if "ultra" in m.id.lower() or "lightning" in m.id.lower():
                _CACHED_SUPER_MODEL = m.id
                return _CACHED_SUPER_MODEL
        _CACHED_SUPER_MODEL = "nvidia/nemotron-3-super-120b-a12b"
    except Exception:
        _CACHED_SUPER_MODEL = "nvidia/nemotron-3-super-120b-a12b"
    return _CACHED_SUPER_MODEL

class SourceItem(BaseModel):
    id: str
    title: str
    url: str
    snippet: str


class DisruptionAnalysis(BaseModel):
    event: str
    impacted_country: Optional[str] = None
    impacted_category: Optional[str] = None
    severity: str = "low"  # low, medium, high, critical
    estimated_duration_days: Optional[int] = None
    real_world_entities_mentioned: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    conflicting_claims: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    extraction_method: str = "model"  # 'model' or 'degraded'
    sources: List[SourceItem] = Field(default_factory=list)


def research(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    """Performs real-time search with Tavily and assigns consistent IDs."""
    if not os.environ.get("TAVILY_API_KEY"):
        return []
    try:
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
        )
        sources = []
        for idx, r in enumerate(response.get("results", []), 1):
            sources.append({
                "id": f"S{idx}",
                "title": r.get("title", "Untitled Source"),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:1200]
            })
        return sources
    except Exception as e:
        print(f"[WARN] Tavily search failed: {e}")
        return []


def analyze_disruption(event_query: str, sources: List[Dict[str, str]], model_id: Optional[str] = None) -> DisruptionAnalysis:
    """Extracts country, category, and disruption facts with Nemotron Nano.
    Never hallucinates or fabricates a default scenario.
    """
    active_model = model_id or resolve_nemotron_model()
    
    # Format sources for context
    sources_block = "\n\n".join(
        f"[{s['id']}] {s['title']}\nURL: {s['url']}\nCONTENT: {s['snippet']}"
        for s in sources
    )

    schema_json = json.dumps({
        "event": "Short description of event",
        "impacted_country": "Country name or null if none",
        "impacted_category": "semiconductor | battery component | sensor | null",
        "severity": "low | medium | high | critical",
        "estimated_duration_days": "Number of days or null",
        "real_world_entities_mentioned": ["TSMC", "Port of Kaohsiung"],
        "evidence": ["Direct factual quotes"],
        "conflicting_claims": ["Disagreements between sources"]
    }, indent=2)

    system_prompt = (
        "You are an enterprise supply-chain intelligence extraction engine.\n"
        "Analyze external news sources for supply disruptions.\n"
        "CRITICAL RULES:\n"
        "1. Extract ONLY facts supported by the text.\n"
        "2. If the text does NOT describe a supply disruption affecting automotive or industrial manufacturing, "
        "set impacted_country and impacted_category to null.\n"
        "3. Standardize 'impacted_category' to one of: ['semiconductor', 'battery component', 'sensor'] or null.\n"
        "4. Standardize 'impacted_country' to the primary sovereign nation (e.g. Taiwan, Germany, Japan, Poland) or null.\n"
        "5. NEVER fabricate or default to Taiwan, semiconductor, or high severity unless explicitly confirmed.\n"
        f"Output MUST be valid JSON adhering to this schema:\n{schema_json}"
    )

    user_prompt = f"EVENT QUERY: {event_query}\n\nSOURCES:\n{sources_block if sources_block else 'No external sources found.'}"

    structured_sources = [
        SourceItem(id=s["id"], title=s["title"], url=s["url"], snippet=s["snippet"][:300])
        for s in sources
    ]

    parsed, raw_content, status = chat_json(
        client=nebius_client,
        model=active_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1000,
        temperature=0.1
    )

    db_countries, db_categories = get_db_vocabulary()

    if status == "degraded" or not parsed:
        return DisruptionAnalysis(
            event=event_query,
            impacted_country=None,
            impacted_category=None,
            severity="low",
            estimated_duration_days=None,
            real_world_entities_mentioned=[],
            evidence=[],
            conflicting_claims=[],
            confidence=0.1,
            extraction_method="degraded",
            sources=structured_sources
        )

    # Normalize extracted values against DB vocab
    norm_country = normalize_country(parsed.get("impacted_country"), db_countries)
    norm_category = normalize_category(parsed.get("impacted_category"), db_categories)

    duration = parsed.get("estimated_duration_days")
    if isinstance(duration, str) and duration.isdigit():
        duration = int(duration)
    elif not isinstance(duration, int):
        duration = None

    return DisruptionAnalysis(
        event=parsed.get("event") or event_query,
        impacted_country=norm_country,
        impacted_category=norm_category,
        severity=parsed.get("severity") or "medium",
        estimated_duration_days=duration,
        real_world_entities_mentioned=parsed.get("real_world_entities_mentioned") or [],
        evidence=parsed.get("evidence") or [],
        conflicting_claims=parsed.get("conflicting_claims") or [],
        confidence=0.85 if status == "model" else 0.3,
        extraction_method=status,
        sources=structured_sources
    )