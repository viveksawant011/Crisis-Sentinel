"""
Critic and Verification Agent for CrisisSentinel.
Validates business logic deterministically, critiques assumptions with Nemotron Super/Ultra,
and executes at most one bounded revision.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from llm_json import chat_json


class Challenge(BaseModel):
    target: str  # e.g. "Action priority 1" or "Claim C2"
    issue_type: str  # weak_evidence | unresolved_conflict | unsupported_assumption | missing_alternative | numeric_mismatch
    severity: str  # low | medium | high
    explanation: str
    suggested_fix: str


class CritiqueReport(BaseModel):
    deterministic_flags: List[str]
    challenges: List[Challenge]
    verdict: str  # accept | revise | escalate
    revised: bool = False


def critique_and_verify(
    brief: Dict[str, Any],
    erp_exposure: Dict[str, Any],
    claims: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
    client: OpenAI,
    model_id: str = "nvidia/nemotron-3-super-120b-a12b"
) -> CritiqueReport:
    """Runs deterministic checks followed by a single critic LLM evaluation."""
    deterministic_flags = []

    # 1. Deterministic Verification
    erp_total = erp_exposure.get("total_exposure_eur", 0.0)
    brief_total = brief.get("financial_risk_eur", 0.0)
    if abs(erp_total - brief_total) > 1.0:
        deterministic_flags.append(
            f"Numeric mismatch: Brief reports €{brief_total:,.2f} risk but SQL engine computes €{erp_total:,.2f}"
        )

    min_runway = erp_exposure.get("critical_runway_days")
    brief_deadline = brief.get("assembly_line_deadline_days")
    if min_runway is not None and brief_deadline is not None:
        if abs(float(min_runway) - float(brief_deadline)) > 0.1:
            deterministic_flags.append(
                f"Deadline mismatch: Critical runway is {min_runway}d but brief states {brief_deadline}d"
            )

    valid_alt_ids = {
        alt["alt_supplier_id"]
        for alt in erp_exposure.get("mitigation_alternatives", [])
    }
    for act in brief.get("recommended_actions", []):
        target_supp = act.get("target_supplier_id")
        if target_supp and target_supp not in valid_alt_ids:
            deterministic_flags.append(
                f"Invalid supplier: Action recommends {target_supp} which is not in alt_supplier_map"
            )

    # 2. Single Critic Call (Super / Ultra)
    system_prompt = (
        "You are an adversarial supply chain executive reviewing a crisis mitigation brief.\n"
        "Your job is to identify weak assumptions, logistics bottlenecks, or unaddressed risks.\n"
        "Output JSON:\n"
        "{\n"
        '  "challenges": [\n'
        '    {"target": "Action 1", "issue_type": "unsupported_assumption", "severity": "high", "explanation": "...", "suggested_fix": "..."}\n'
        "  ],\n"
        '  "verdict": "accept | revise | escalate"\n'
        "}\n"
        "RULE: Set verdict to 'revise' ONLY if there is a genuine high-severity flaw."
    )

    user_payload = f"""
BRIEF:
Headline: {brief.get('headline')}
Actions: {brief.get('recommended_actions')}

DETERMINISTIC FLAGS:
{deterministic_flags}

UNRESOLVED CONFLICTS:
{[c for c in contradictions if c.get('resolution_status') == 'unresolved']}
"""

    parsed, _, _ = chat_json(
        client=client,
        model=model_id,
        system_prompt=system_prompt,
        user_prompt=user_payload,
        max_tokens=2500,
        temperature=0.2
    )

    challenges = []
    verdict = "accept"

    if deterministic_flags:
        verdict = "revise"
        for flag in deterministic_flags:
            challenges.append(Challenge(
                target="Deterministic Guardrail",
                issue_type="numeric_mismatch",
                severity="high",
                explanation=flag,
                suggested_fix="Synchronize brief fields directly with verified SQL engine output."
            ))

    if parsed and "challenges" in parsed:
        for ch in parsed["challenges"]:
            challenges.append(Challenge(
                target=ch.get("target", "Strategy"),
                issue_type=ch.get("issue_type", "unsupported_assumption"),
                severity=ch.get("severity", "medium"),
                explanation=ch.get("explanation", ""),
                suggested_fix=ch.get("suggested_fix", "")
            ))
        if not deterministic_flags:
            verdict = parsed.get("verdict", "accept")

    return CritiqueReport(
        deterministic_flags=deterministic_flags,
        challenges=challenges,
        verdict=verdict,
        revised=False
    )