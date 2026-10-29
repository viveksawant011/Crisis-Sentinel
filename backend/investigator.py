"""
Research investigator: multi-query Tavily search, claim extraction,
contradiction detection, and model-judged follow-up resolution.

Honesty rules enforced here:
  * A contradiction is marked 'resolved' only when a model judges the
    follow-up sources AND cites at least one valid follow-up source id.
  * Claims may only cite source ids that exist.
  * If extraction fails the report says so (extraction_method = 'degraded')
    and carries no country/category, so downstream code finds no exposure.
"""

import os
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field
from tavily import TavilyClient

from llm_json import chat_json
from normalizer import get_db_vocabulary, normalize_category, normalize_country

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
nebius_client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY") or "missing-key",
    timeout=60.0,
    max_retries=1,
)

MAX_SOURCES = 10
ProgressFn = Callable[[str, str], None]


class Claim(BaseModel):
    claim_id: str
    text: str
    type: str  # cause | scope | severity | duration
    value: str
    source_ids: List[str]


class Contradiction(BaseModel):
    claim_a_id: str
    claim_b_id: str
    topic: str
    explanation: str
    resolution_status: str  # resolved | unresolved
    winning_claim_id: Optional[str] = None
    resolution_note: Optional[str] = None
    follow_up_query: Optional[str] = None
    follow_up_source_ids: List[str] = Field(default_factory=list)


class IntelligenceReport(BaseModel):
    event: str
    impacted_country: Optional[str] = None
    impacted_category: Optional[str] = None
    severity: str = "unknown"
    estimated_duration_days: Optional[int] = None
    confidence: float
    sources: List[Dict[str, Any]]
    claims: List[Claim]
    contradictions: List[Contradiction]
    evidence_strength: str
    search_log: List[Dict[str, Any]]
    extraction_method: str = "model"
    mapping_source: str = "model"  # 'model', or 'query_text' when the model's country/category was unusable


def _to_int(value: Any) -> Optional[int]:
    try:
        n = int(float(str(value).strip().split()[0]))
        return n if 0 < n <= 365 else None
    except (ValueError, IndexError, TypeError):
        return None


def _add_source(all_sources: Dict[str, Dict[str, str]], r: Dict[str, Any]) -> Optional[str]:
    url = r.get("url", "")
    if not url:
        return None
    if url not in all_sources:
        all_sources[url] = {
            "id": f"S{len(all_sources) + 1}",
            "title": r.get("title", "") or "Source",
            "url": url,
            "snippet": (r.get("content", "") or "")[:1200],
        }
    return all_sources[url]["id"]


def run_investigation(
    event_query: str,
    model_id: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    on_progress: Optional[ProgressFn] = None,
) -> IntelligenceReport:
    """At most 6 Tavily searches and 4 model calls per investigation."""
    notify = on_progress or (lambda stage, msg: None)
    search_log: List[Dict[str, Any]] = []
    all_sources: Dict[str, Dict[str, str]] = {}

    # 1. Triangulation search plan (fixed templates, no model call)
    notify("research", "Searching live sources (3 queries)")
    plan = [
        f"{event_query} what happened disruption cause",
        f"{event_query} automotive supplier parts plant impact",
        f"{event_query} restart recovery estimated timeline",
    ]
    for q in plan:
        try:
            res = tavily_client.search(query=q, max_results=3, search_depth="basic")
            results = res.get("results", [])
            search_log.append({"query": q, "results_count": len(results)})
            for r in results:
                if len(all_sources) < MAX_SOURCES:
                    _add_source(all_sources, r)
        except Exception as e:
            search_log.append({"query": q, "error": str(e)})
    source_list = list(all_sources.values())

    # 2. Claim extraction (Nano)
    notify("extraction", f"Extracting claims from {len(source_list)} sources")
    sources_text = "\n\n".join(f"[{s['id']}] {s['title']}\n{s['snippet']}" for s in source_list)
    db_countries, db_categories = get_db_vocabulary()
    countries_txt = ", ".join(sorted(db_countries))
    categories_txt = ", ".join(sorted(db_categories))
    claims_prompt = (
        "You extract structured facts about a supply-chain disruption from numbered web sources.\n"
        "Respond with ONE JSON object using exactly these keys:\n"
        '{"event": "", "impacted_country": "", "impacted_category": "", "severity": "", '
        '"estimated_duration_days": 0, "claims": [{"claim_id": "", "text": "", "type": "", "value": "", "source_ids": []}]}\n'
        "FIELD RULES:\n"
        "- event: one sentence describing what happened, in your own words.\n"
        f"- impacted_country: the single country where the disruption happens. It MUST be exactly one of: {countries_txt}. "
        "Use null if the event is in any other country or no source supports one.\n"
        f"- impacted_category: the kind of parts affected. It MUST be exactly one of: {categories_txt}. "
        "Use null if none of these fits.\n"
        "- severity: exactly one of low, medium, high, critical.\n"
        "- estimated_duration_days: a whole number of days taken from the sources, or null if no source gives a duration.\n"
        "- claims: at most 4 claims, each under 20 words. type is one of cause, scope, severity, duration. "
        "value is 1 to 3 words. claim_id is C1, C2, ... in order. source_ids lists only ids that appear in the sources, such as S1.\n"
        "Never copy these instructions into your answer; fill every field with real content from the sources."
    )
    parsed, _, status = (None, "", "degraded")
    if source_list:
        parsed, _, status = chat_json(
            client=nebius_client, model=model_id, system_prompt=claims_prompt,
            user_prompt=f"EVENT: {event_query}\n\nSOURCES:\n{sources_text}", max_tokens=3500,
        )
    parsed = parsed if isinstance(parsed, dict) else None

    claims: List[Claim] = []
    if parsed:
        valid_sids = {s["id"] for s in source_list}
        for c in parsed.get("claims", []) or []:
            if not isinstance(c, dict):
                continue
            c_sids = [sid for sid in c.get("source_ids", []) if sid in valid_sids]
            if c_sids and c.get("text"):
                claims.append(Claim(
                    claim_id=str(c.get("claim_id") or f"C{len(claims) + 1}"),
                    text=str(c["text"]), type=str(c.get("type", "scope")),
                    value=str(c.get("value", "")), source_ids=c_sids,
                ))
    claim_by_id = {c.claim_id: c for c in claims}

    # 3. Contradiction detection (Nano)
    contradictions: List[Contradiction] = []
    if len(claims) >= 2:
        conflict_prompt = (
            "Find DIRECT contradictions between these claims about timeline, severity or scope. "
            "Only report claims that cannot both be true. Return JSON:\n"
            '{"conflicts": [{"claim_a_id": "C1", "claim_b_id": "C2", "topic": "duration", "explanation": "One says 2 days, the other 4 weeks"}]}\n'
            "If there are none, return {\"conflicts\": []}."
        )
        claims_summary = "\n".join(f"{c.claim_id} ({c.type}): {c.text} [value: {c.value}]" for c in claims)
        conflict_parsed, _, _ = chat_json(
            client=nebius_client, model=model_id, system_prompt=conflict_prompt,
            user_prompt=claims_summary, max_tokens=800,
        )
        for conf in ((conflict_parsed or {}).get("conflicts") or [])[:2]:
            if not isinstance(conf, dict):
                continue
            a, b = conf.get("claim_a_id"), conf.get("claim_b_id")
            if a in claim_by_id and b in claim_by_id and a != b:
                topic = str(conf.get("topic", "scope"))
                contradictions.append(Contradiction(
                    claim_a_id=a, claim_b_id=b, topic=topic,
                    explanation=str(conf.get("explanation", "")),
                    resolution_status="unresolved",
                    follow_up_query=f"{event_query} {topic} update official statement",
                ))

    # 4. Targeted follow-up searches, judged by the model
    if contradictions:
        notify("contradictions", f"Resolving {len(contradictions)} conflicting claim(s) with follow-up searches")
    for contra in contradictions:
        try:
            f_res = tavily_client.search(query=contra.follow_up_query, max_results=3, search_depth="basic")
        except Exception as e:
            search_log.append({"query": contra.follow_up_query, "error": str(e)})
            contra.resolution_note = "Follow-up search failed."
            continue
        f_results = f_res.get("results", [])
        search_log.append({"query": contra.follow_up_query, "results_count": len(f_results), "follow_up_for": contra.topic})
        new_sids = [sid for sid in (_add_source(all_sources, r) for r in f_results) if sid]
        contra.follow_up_source_ids = new_sids
        if not new_sids:
            contra.resolution_note = "Follow-up search returned no sources."
            continue

        by_id = {s["id"]: s for s in all_sources.values()}
        a, b = claim_by_id[contra.claim_a_id], claim_by_id[contra.claim_b_id]
        judge_prompt = (
            "Two claims about a disruption conflict. Using ONLY the follow-up sources, decide which is better supported. "
            "Return JSON: {\"verdict\": \"claim_a|claim_b|inconclusive\", \"evidence_source_ids\": [\"S7\"], \"reason\": \"one sentence\"}. "
            "Choose a claim only if a follow-up source clearly supports it; otherwise answer inconclusive."
        )
        judge_input = (
            f"CLAIM A ({a.claim_id}): {a.text}\nCLAIM B ({b.claim_id}): {b.text}\nCONFLICT: {contra.explanation}\n\n"
            "FOLLOW-UP SOURCES:\n" + "\n\n".join(f"[{sid}] {by_id[sid]['title']}\n{by_id[sid]['snippet']}" for sid in new_sids)
        )
        verdict, _, _ = chat_json(
            client=nebius_client, model=model_id, system_prompt=judge_prompt,
            user_prompt=judge_input, max_tokens=800,
        )
        verdict = verdict if isinstance(verdict, dict) else {}
        cited = [sid for sid in verdict.get("evidence_source_ids", []) if sid in new_sids]
        v = verdict.get("verdict")
        contra.resolution_note = str(verdict.get("reason", "")) or None
        if v in ("claim_a", "claim_b") and cited:
            contra.resolution_status = "resolved"
            contra.winning_claim_id = contra.claim_a_id if v == "claim_a" else contra.claim_b_id
            contra.follow_up_source_ids = cited
        else:
            contra.resolution_note = contra.resolution_note or "Follow-up sources did not settle the conflict."

    # 5. Evidence strength (deterministic heuristic, not a probability)
    #    confidence = clamp(0.35 + 0.12 * min(domains, 4) - 0.15 * unresolved, 0.10, 0.95)
    domains = {urllib.parse.urlparse(s["url"]).netloc for s in all_sources.values() if s.get("url")}
    unresolved = sum(1 for c in contradictions if c.resolution_status == "unresolved")
    confidence = round(max(0.10, min(0.95, 0.35 + 0.12 * min(len(domains), 4) - 0.15 * unresolved)), 2)

    db_c, db_k = get_db_vocabulary()
    country = normalize_country(parsed.get("impacted_country"), db_c) if parsed else None
    category = normalize_category(parsed.get("impacted_category"), db_k) if parsed else None
    mapping_source = "model"
    if parsed:
        # If the model's answer was unusable (null, placeholder text, unknown place), fall back to the
        # words the user typed, then to the model's one-line event summary. Both are matched against
        # the real database vocabulary, so nothing can be invented.
        event_line = str(parsed.get("event") or "")
        if not country:
            country = normalize_country(event_query, db_c) or normalize_country(f"{event_query} {event_line}", db_c)
            mapping_source = "query_text" if country else mapping_source
        if not category:
            category = normalize_category(event_query, db_k) or normalize_category(f"{event_query} {event_line}", db_k)
            mapping_source = "query_text" if category else mapping_source
    method = status if (parsed and source_list) else "degraded"

    return IntelligenceReport(
        event=str(parsed.get("event") or event_query) if parsed else event_query,
        impacted_country=country,
        impacted_category=category,
        severity=str(parsed.get("severity", "medium")).lower() if parsed else "unknown",
        estimated_duration_days=_to_int(parsed.get("estimated_duration_days")) if parsed else None,
        confidence=confidence if parsed else 0.10,
        sources=list(all_sources.values()),
        claims=claims,
        contradictions=contradictions,
        evidence_strength=f"{int(confidence * 100)}% ({len(domains)} independent domains, {unresolved} unresolved conflicts)",
        search_log=search_log,
        extraction_method=method,
        mapping_source=mapping_source,
    )