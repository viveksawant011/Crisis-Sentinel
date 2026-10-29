"""
Strategist agent for CrisisSentinel.

Turns deterministic ERP exposure into a short list of mitigation actions with
Nemotron (Super). The model proposes; the code decides what is allowed:

  * Every action must reference an exposed open PO from the SQL result.
  * Plant and material are always taken from that PO's ERP record, never from
    the model, so an action can never point at a mismatched plant or part.
  * Reroute actions must use a supplier that alt_supplier_map approves for
    THAT PO. Anything else is dropped.
  * Money and runway figures always come from SQL, never from the model.
  * If the model fails, a deterministic brief is built from SQL and labelled
    brief_source = 'deterministic_fallback' so the UI can say so.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from llm_json import chat_json
from tavily_nemotron_probe import nebius_client as client, resolve_super_model

REROUTE = "reroute_supplier"
ALLOWED_ACTION_TYPES = {REROUTE, "expedite", "buffer_stock", "verify_capacity"}


class MitigationAction(BaseModel):
    priority: int = 1
    title: str
    action_type: str = REROUTE
    po_id: str
    target_supplier_id: str = ""
    target_plant: str = ""
    target_material: str = ""
    rationale: str = ""
    # Order value of the PO this action touches, taken from SQL. The name is
    # kept for API compatibility; it is NOT a model estimate of cost.
    estimated_cost_eur: float = 0.0
    value_rerouted_eur: float = 0.0


class ExecutiveBrief(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    headline: str
    criticality_summary: str
    financial_risk_eur: float
    assembly_line_deadline_days: Optional[float] = None
    recommended_actions: List[MitigationAction]
    brief_source: str = "nemotron"  # "nemotron" | "deterministic_fallback"
    model_used: Optional[str] = None


def resolve_reasoning_model() -> str:
    """Single source of truth for the strategist/critic model ID."""
    return resolve_super_model()


def _unwrap_payload(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    for wrapper in ("analysis_report", "executive_brief", "report", "brief", "data"):
        if isinstance(data.get(wrapper), dict):
            return data[wrapper]
    return data


def _alt_pairs(exposure: Dict[str, Any]) -> Dict[tuple, Dict[str, Any]]:
    return {(a["po_id"], a["alt_supplier_id"]): a for a in exposure.get("mitigation_alternatives", [])}


def _po_lookup(exposure: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {po["po_id"]: po for po in exposure.get("affected_open_pos", []) if "po_id" in po}


def _finalize_action(action: MitigationAction, po: Dict[str, Any], alt: Optional[Dict[str, Any]]) -> MitigationAction:
    """Overwrite every ERP-derived field from the PO record."""
    action.target_plant = po["plant_name"]
    action.target_material = po["material_id"]
    action.estimated_cost_eur = float(po["value_eur"])
    action.value_rerouted_eur = float(po["value_eur"])
    if action.action_type == REROUTE and alt:
        action.target_supplier_id = alt["alt_supplier_id"]
    return action


def validate_actions(actions: List[MitigationAction], exposure: Dict[str, Any]) -> List[MitigationAction]:
    pos = _po_lookup(exposure)
    pairs = _alt_pairs(exposure)
    alt_for_po = {a["po_id"]: a for a in exposure.get("mitigation_alternatives", [])}
    kept: List[MitigationAction] = []
    seen_pos = set()
    for a in actions:
        if a.po_id not in pos or a.po_id in seen_pos:
            continue
        if a.action_type not in ALLOWED_ACTION_TYPES:
            a.action_type = "verify_capacity"
        if a.action_type == REROUTE:
            if (a.po_id, a.target_supplier_id) not in pairs:
                continue  # unapproved supplier for this PO
            alt = pairs[(a.po_id, a.target_supplier_id)]
        else:
            alt = alt_for_po.get(a.po_id)
        kept.append(_finalize_action(a, pos[a.po_id], alt))
        seen_pos.add(a.po_id)
    for i, a in enumerate(kept, start=1):
        a.priority = i
    return kept[:3]


def deterministic_actions(exposure: Dict[str, Any], limit: int = 3) -> List[MitigationAction]:
    """Most urgent reroutable POs first (shortest runway, then highest value)."""
    pos = _po_lookup(exposure)
    candidates = []
    for alt in exposure.get("mitigation_alternatives", []):
        po = pos.get(alt["po_id"])
        if po:
            runway = po.get("runway_days")
            candidates.append((runway if runway is not None else 9e9, -float(po["value_eur"]), po, alt))
    candidates.sort(key=lambda c: (c[0], c[1]))
    actions, used = [], set()
    for runway, _, po, alt in candidates:
        if po["po_id"] in used:
            continue
        used.add(po["po_id"])
        runway_txt = f"{po['runway_days']} days of stock" if po.get("runway_days") is not None else "no stock record"
        a = MitigationAction(
            priority=len(actions) + 1,
            title=f"Reroute {po['material_id']} ({po['po_id']}) to {alt['alt_supplier_name']}",
            action_type=REROUTE,
            po_id=po["po_id"],
            target_supplier_id=alt["alt_supplier_id"],
            rationale=f"{po['plant_name']} has {runway_txt}; {alt['alt_supplier_name']} is the ERP-approved alternative for this PO.",
        )
        actions.append(_finalize_action(a, po, alt))
        if len(actions) >= limit:
            break
    return actions


def _compact_context(crisis_context: Dict[str, Any], exposure: Dict[str, Any]) -> Dict[str, Any]:
    pos = exposure.get("affected_open_pos", [])
    return {
        "event": {
            "headline": crisis_context.get("event"),
            "country": crisis_context.get("impacted_country"),
            "category": crisis_context.get("impacted_category"),
            "severity": crisis_context.get("severity"),
            "estimated_duration_days": crisis_context.get("estimated_duration_days"),
            "claims": [c.get("text") for c in crisis_context.get("claims", [])][:4],
        },
        "erp": {
            "total_exposure_eur": exposure.get("total_exposure_eur"),
            "open_pos_count": exposure.get("open_pos_count"),
            "critical_runway_days": exposure.get("critical_runway_days"),
            "top_exposed_pos": [
                {k: po.get(k) for k in ("po_id", "material_id", "material_name", "plant_name",
                                        "supplier_name", "value_eur", "runway_days", "has_alternative")}
                for po in pos[:8]
            ],
            "approved_alternatives": [
                {k: a.get(k) for k in ("po_id", "material_id", "alt_supplier_id", "alt_supplier_name")}
                for a in exposure.get("mitigation_alternatives", [])[:12]
            ],
        },
    }


def generate_mitigation_strategy(
    crisis_context: Dict[str, Any],
    erp_exposure: Dict[str, Any],
    critique_feedback: Optional[List[Dict[str, Any]]] = None,
    model_id: Optional[str] = None,
) -> ExecutiveBrief:
    model_id = model_id or resolve_reasoning_model()
    total = float(erp_exposure.get("total_exposure_eur") or 0.0)
    runway = erp_exposure.get("critical_runway_days")
    runway = float(runway) if runway is not None else None

    system_prompt = (
        "You are the Chief Supply Chain Strategist for VoltAuto GmbH, an EV manufacturer. "
        "You are given a real-world disruption and the company's deterministic ERP exposure. "
        "Propose AT MOST 3 prioritized actions, most urgent first.\n"
        "RULES:\n"
        "- Every action must reference one po_id from top_exposed_pos.\n"
        "- For action_type 'reroute_supplier', target_supplier_id MUST be the alt_supplier_id listed for that po_id in approved_alternatives. Never invent suppliers.\n"
        "- Other allowed action_types: expedite, buffer_stock, verify_capacity (target_supplier_id may be empty).\n"
        "- Do not state that capacity, quotes or qualification are already verified; phrase them as things to confirm.\n"
        "- Keep each rationale under 25 words. Do not compute money; amounts are filled in from SQL.\n"
        "Return ONLY a JSON object with keys: headline, criticality_summary, recommended_actions "
        "(each: priority, title, action_type, po_id, target_supplier_id, rationale)."
    )
    user_payload: Dict[str, Any] = _compact_context(crisis_context, erp_exposure)
    if critique_feedback:
        user_payload["critic_challenges_to_address"] = critique_feedback
        system_prompt += "\nThe critic reviewed your previous plan. Address every challenge it raised within these rules."

    parsed, _, status = chat_json(
        client=client, model=model_id, system_prompt=system_prompt,
        user_prompt=json.dumps(user_payload, indent=2), max_tokens=3500, temperature=0.1,
    )

    if status == "model" and parsed:
        data = _unwrap_payload(parsed)
        raw_actions = []
        for item in data.get("recommended_actions", []) or []:
            try:
                raw_actions.append(MitigationAction.model_validate(
                    {**item, "po_id": str(item.get("po_id", "")), "title": item.get("title", "Action")}))
            except Exception:
                continue
        actions = validate_actions(raw_actions, erp_exposure)
        if actions:
            return ExecutiveBrief(
                headline=str(data.get("headline") or f"Disruption in {crisis_context.get('impacted_country', 'supplier region')}"),
                criticality_summary=str(data.get("criticality_summary") or ""),
                financial_risk_eur=total,
                assembly_line_deadline_days=runway,
                recommended_actions=actions,
                brief_source="nemotron",
                model_used=model_id,
            )

    runway_txt = f"{runway} days" if runway is not None else "unknown"
    return ExecutiveBrief(
        headline=f"{crisis_context.get('impacted_country', 'Regional')} {crisis_context.get('impacted_category', 'supply')} disruption: €{total:,.0f} exposed",
        criticality_summary=f"{erp_exposure.get('open_pos_count', 0)} open purchase orders are exposed; shortest inventory runway is {runway_txt}.",
        financial_risk_eur=total,
        assembly_line_deadline_days=runway,
        recommended_actions=deterministic_actions(erp_exposure),
        brief_source="deterministic_fallback",
        model_used=None,
    )