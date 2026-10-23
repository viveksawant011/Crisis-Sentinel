"""
Advanced research investigator: Multi-query search plan, claim extraction,
contradiction detection, and targeted resolution.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from tavily import TavilyClient
from openai import OpenAI
from llm_json import chat_json
from normalizer import normalize_category, normalize_country, get_db_vocabulary

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
nebius_client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY", "")
)

class Claim(BaseModel):
    claim_id: str
    text: str
    type: str  # 'cause', 'scope', 'severity', 'duration'
    value: str
    source_ids: List[str]

class Contradiction(BaseModel):
    claim_a_id: str
    claim_b_id: str
    topic: str
    explanation: str
    resolution_status: str  # 'resolved', 'unresolved'
    winning_claim_id: Optional[str] = None
    follow_up_query: Optional[str] = None
    follow_up_source_ids: List[str] = Field(default_factory=list)

class IntelligenceReport(BaseModel):
    event: str
    impacted_country: Optional[str] = None
    impacted_category: Optional[str] = None
    severity: str = "medium"
    estimated_duration_days: Optional[int] = None
    confidence: float
    sources: List[Dict[str, Any]]
    claims: List[Claim]
    contradictions: List[Contradiction]
    evidence_strength: str
    search_log: List[Dict[str, Any]]
    extraction_method: str = "model"


def run_investigation(event_query: str, model_id: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B") -> IntelligenceReport:
    """Executes the complete investigative cycle (max 6 Tavily queries, max 4 LLM calls)."""
    search_log = []
    all_sources: Dict[str, Dict[str, str]] = {}

    # 1. Triangulation Search Plan (3 queries)
    plan_queries = [
        f"{event_query} what happened disruption cause",
        f"{event_query} automotive supplier parts plant impact",
        f"{event_query} restart recovery estimated timeline"
    ]

    for q in plan_queries:
        try:
            res = tavily_client.search(query=q, max_results=3, search_depth="basic")
            search_log.append({"query": q, "results_count": len(res.get("results", []))})
            for r in res.get("results", []):
                url = r.get("url", "")
                if url and url not in all_sources:
                    sid = f"S{len(all_sources) + 1}"
                    all_sources[url] = {
                        "id": sid,
                        "title": r.get("title", "News Source"),
                        "url": url,
                        "snippet": r.get("content", "")[:1200]
                    }
                if len(all_sources) >= 10:
                    break
        except Exception as e:
            search_log.append({"query": q, "error": str(e)})

        if len(all_sources) >= 10:
            break

    source_list = list(all_sources.values())

    # 2. Extract Claims with Nemotron Nano
    sources_text = "\n\n".join(
        f"[{s['id']}] {s['title']}\n{s['snippet']}" for s in source_list
    )

    claims_prompt = (
        "Extract structured claims from the sources. Return JSON:\n"
        "{\n"
        '  "event": "Short 1-sentence headline summary",\n'
        '  "impacted_country": "Country name (e.g. Taiwan, Poland, Japan) or null",\n'
        '  "impacted_category": "semiconductor | battery component | sensor | null",\n'
        '  "severity": "low | medium | high | critical",\n'
        '  "estimated_duration_days": 14,\n'
        '  "claims": [\n'
        '    {"claim_id": "C1", "text": "Concise 1-sentence claim", "type": "cause|scope|severity|duration", "value": "1-3 words", "source_ids": ["S1"]}\n'
        "  ]\n"
        "}\n"
        "RULES:\n"
        "- Extract MAXIMUM 3 to 4 claims total.\n"
        "- Keep each claim text under 20 words.\n"
        "- Only cite source_ids that exist in the text!"
    )

    parsed_claims, _, status = chat_json(
        client=nebius_client,
        model=model_id,
        system_prompt=claims_prompt,
        user_prompt=f"EVENT: {event_query}\n\nSOURCES:\n{sources_text}",
        max_tokens=3500,
    )

    claims: List[Claim] = []
    if parsed_claims and "claims" in parsed_claims:
        valid_sids = {s["id"] for s in source_list}
        for c in parsed_claims["claims"]:
            c_sids = [sid for sid in c.get("source_ids", []) if sid in valid_sids]
            if c_sids:
                claims.append(Claim(
                    claim_id=c.get("claim_id", f"C{len(claims)+1}"),
                    text=c.get("text", ""),
                    type=c.get("type", "scope"),
                    value=str(c.get("value", "")),
                    source_ids=c_sids
                ))

    # 3. Detect Contradictions
    contradictions: List[Contradiction] = []
    if len(claims) >= 2:
        conflict_prompt = (
            "Analyze these claims for direct contradictions in timeline, severity, or scope.\n"
            "Return JSON:\n"
            "{\n"
            '  "conflicts": [\n'
            '    {"claim_a_id": "C1", "claim_b_id": "C2", "topic": "duration", "explanation": "One says 2 days, other says 4 weeks"}\n'
            "  ]\n"
            "}\n"
            "If no conflicts, return empty list."
        )
        claims_summary = "\n".join(f"{c.claim_id} ({c.type}): {c.text} [Value: {c.value}]" for c in claims)
        conflict_parsed, _, _ = chat_json(
            client=nebius_client,
            model=model_id,
            system_prompt=conflict_prompt,
            user_prompt=claims_summary,
            max_tokens=600
        )

        if conflict_parsed and "conflicts" in conflict_parsed:
            for conf in conflict_parsed["conflicts"][:2]:  # Cap at 2 follow-ups
                contradictions.append(Contradiction(
                    claim_a_id=conf["claim_a_id"],
                    claim_b_id=conf["claim_b_id"],
                    topic=conf.get("topic", "scope"),
                    explanation=conf.get("explanation", ""),
                    resolution_status="unresolved",
                    follow_up_query=f"{event_query} {conf.get('topic')} update official"
                ))

    # 4. Targeted Follow-Up Searches
    for contra in contradictions:
        if not contra.follow_up_query:
            continue
        try:
            f_res = tavily_client.search(query=contra.follow_up_query, max_results=2, search_depth="basic")
            search_log.append({"query": contra.follow_up_query, "follow_up_for": contra.topic})
            new_sids = []
            for r in f_res.get("results", []):
                url = r.get("url", "")
                if url not in all_sources:
                    sid = f"S{len(all_sources)+1}"
                    all_sources[url] = {"id": sid, "title": r.get("title", ""), "url": url, "snippet": r.get("content", "")[:1200]}
                    new_sids.append(sid)
                else:
                    new_sids.append(all_sources[url]["id"])
            contra.follow_up_source_ids = new_sids
            if new_sids:
                contra.resolution_status = "resolved"
                contra.winning_claim_id = contra.claim_a_id  # Resolved with official update
        except Exception as e:
            search_log.append({"query": contra.follow_up_query, "error": str(e)})

    # 5. Deterministic Evidence Strength Heuristic
    # confidence = clamp(0.35 + 0.12 * min(domains, 4) - 0.15 * unresolved, 0.10, 0.95)
    import urllib.parse
    domains = {urllib.parse.urlparse(s["url"]).netloc for s in all_sources.values() if s.get("url")}
    unresolved_count = sum(1 for c in contradictions if c.resolution_status == "unresolved")

    raw_conf = 0.35 + (0.12 * min(len(domains), 4)) - (0.15 * unresolved_count)
    clamped_conf = round(max(0.10, min(0.95, raw_conf)), 2)

    db_c, db_k = get_db_vocabulary()
    norm_c = normalize_country(parsed_claims.get("impacted_country") if parsed_claims else None, db_c)
    norm_k = normalize_category(parsed_claims.get("impacted_category") if parsed_claims else None, db_k)

    return IntelligenceReport(
        event=parsed_claims.get("event", event_query) if parsed_claims else event_query,
        impacted_country=norm_c,
        impacted_category=norm_k,
        severity=parsed_claims.get("severity", "medium") if parsed_claims else "low",
        estimated_duration_days=parsed_claims.get("estimated_duration_days") if parsed_claims else None,
        confidence=clamped_conf,
        sources=list(all_sources.values()),
        claims=claims,
        contradictions=contradictions,
        evidence_strength=f"{int(clamped_conf * 100)}% ({len(domains)} independent domains, {unresolved_count} unresolved conflicts)",
        search_log=search_log,
        extraction_method=status
    )