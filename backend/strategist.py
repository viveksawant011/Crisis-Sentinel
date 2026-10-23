"""
Strategist Agent for CrisisSentinel.
Synthesizes deterministic ERP exposure into executive mitigation actions using Nemotron.
Enforces honest financial metrics calculated directly from SQL purchase order records.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
FALLBACK_STRATEGIST_MODEL = "nvidia/nemotron-3-super-120b-a12b"

client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ.get("NEBIUS_API_KEY", ""),
)

class MitigationAction(BaseModel):
    priority: int = 1
    title: str
    action_type: str = "reroute_supplier"  # "reroute_supplier" | "air_freight" | "line_rebalancing" | "buffer_stock"
    po_id: str
    target_supplier_id: str
    target_plant: str
    target_material: str
    rationale: str
    estimated_cost_eur: float

class ExecutiveBrief(BaseModel):
    headline: str
    criticality_summary: str
    financial_risk_eur: float
    assembly_line_deadline_days: float
    recommended_actions: List[MitigationAction]
    brief_source: str = "nemotron"  # "nemotron" | "deterministic_fallback"


def resolve_reasoning_model() -> str:
    """Selects a high-reasoning model (Super or Ultra) for strategy generation."""
    try:
        models = client.models.list()
        nemotron_models = [m.id for m in models.data if "nemotron" in m.id.lower()]
        ultra_or_super = [m for m in nemotron_models if "ultra" in m.lower() or "super" in m.lower()]
        return ultra_or_super[0] if ultra_or_super else (nemotron_models[0] if nemotron_models else FALLBACK_STRATEGIST_MODEL)
    except Exception:
        return FALLBACK_STRATEGIST_MODEL


def _unwrap_payload(data: Any) -> Dict[str, Any]:
    """If the LLM wraps the output inside a container key, unpack it."""
    if not isinstance(data, dict):
        return {}
    
    # Common nested keys models invent
    for wrapper in ["analysis_report", "executive_brief", "report", "brief", "data"]:
        if wrapper in data and isinstance(data[wrapper], dict):
            return data[wrapper]
            
    return data


def generate_mitigation_strategy(crisis_context: Dict[str, Any], erp_exposure: Dict[str, Any]) -> ExecutiveBrief:
    """Feeds external context and internal SQL data into the Strategist model.
    Guarantees that all financial numbers are derived strictly from ERP SQL data.
    """
    model_id = resolve_reasoning_model()

    total_exposure = float(erp_exposure.get("total_exposure_eur", 0.0))
    critical_runway = erp_exposure.get("critical_runway_days", 1.0)
    critical_runway = float(critical_runway) if critical_runway is not None else 1.0
    open_pos = erp_exposure.get("affected_open_pos", [])
    alts = erp_exposure.get("mitigation_alternatives", [])

    # Fast lookup mapping: po_id -> open PO row from SQL
    po_lookup: Dict[str, Dict[str, Any]] = {
        po["po_id"]: po for po in open_pos if "po_id" in po
    }

    compact_open_pos = open_pos[:5]

    system_prompt = (
        "You are the Chief Supply Chain Strategist for VoltAuto GmbH. "
        "Analyze the deterministic ERP exposure resulting from an external disruption. "
        "All calculations must be grounded strictly in the provided ERP data. "
        "If alternative suppliers are listed in the ERP data, prioritize rerouting orders. "
        "Provide a concise executive brief with MAXIMUM 3 high-priority operational actions.\n\n"
        "CRITICAL RULES:\n"
        "- Generate AT MOST 3 recommended_actions.\n"
        "- Keep rationale under 25 words per action.\n"
        "Output MUST be a valid JSON object adhering to this schema:\n"
        f"{json.dumps(ExecutiveBrief.model_json_schema(), indent=2)}"
    )

    user_payload = {
        "external_disruption_event": crisis_context,
        "internal_erp_exposure": {
            "matched": erp_exposure.get("matched"),
            "impacted_country": erp_exposure.get("impacted_country"),
            "impacted_category": erp_exposure.get("impacted_category"),
            "total_exposure_eur": total_exposure,
            "critical_runway_days": critical_runway,
            "open_pos_count": erp_exposure.get("open_pos_count"),
            "sample_open_pos": compact_open_pos,
            "mitigation_alternatives": alts[:5]
        }
    }
    
    user_payload = {
        "external_disruption_event": crisis_context,
        "internal_erp_exposure": erp_exposure
    }

    valid_plants = set(erp_exposure.get("affected_plants", []))
    # If affected_plants wasn't explicitly populated in erp_exposure, extract from open_pos
    if not valid_plants:
        valid_plants = {po["plant_name"] for po in open_pos if "plant_name" in po}

    valid_materials = set()
    for po in open_pos:
        if "material_id" in po:
            valid_materials.add(po["material_id"])
        if "material_name" in po and po["material_name"]:
            valid_materials.add(po["material_name"])

    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, indent=2)},
                ],
                temperature=0.1,
                max_tokens=3500,  
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or "{}"
            parsed_data = json.loads(raw)
            clean_data = _unwrap_payload(parsed_data)

            # Backfill required top-level fields if omitted by the model
            clean_data.setdefault("financial_risk_eur", total_exposure)
            clean_data.setdefault("assembly_line_deadline_days", critical_runway)
            clean_data.setdefault("headline", f"Disruption in {crisis_context.get('impacted_country', 'Supplier Region')}")
            clean_data.setdefault("criticality_summary", f"Critical inventory runway is {critical_runway} days.")
            clean_data.setdefault("recommended_actions", [])
            clean_data["brief_source"] = "nemotron"

            brief = ExecutiveBrief.model_validate(clean_data)

            # Deterministic guardrails: Enforce exact SQL calculations for brief totals
            brief.financial_risk_eur = total_exposure
            brief.assembly_line_deadline_days = critical_runway
            brief.brief_source = "nemotron"

            # Filter actions: Keep only recognized plants and materials
            filtered_actions: List[MitigationAction] = []
            for a in brief.recommended_actions:
                if a.target_plant in valid_plants and a.target_material in valid_materials:
                    # OVERWRITE MODEL COST: Link to the exact open PO value in SQL
                    if a.po_id in po_lookup:
                        a.estimated_cost_eur = float(po_lookup[a.po_id].get("value_eur", 0.0))
                    elif open_pos:
                        a.estimated_cost_eur = float(open_pos[0].get("value_eur", 0.0))
                    filtered_actions.append(a)

            # If model dropped all actions or failed validation, construct deterministic fallback action
            if not filtered_actions and open_pos and alts:
                matched_po_id = alts[0].get("po_id", open_pos[0]["po_id"])
                actual_po_val = float(po_lookup.get(matched_po_id, open_pos[0]).get("value_eur", 0.0))

                filtered_actions = [
                    MitigationAction(
                        priority=1,
                        title=f"Reroute {alts[0]['material_id']} to {alts[0]['alt_supplier_name']}",
                        action_type="reroute_supplier",
                        po_id=matched_po_id,
                        target_supplier_id=alts[0]["alt_supplier_id"],
                        target_plant=open_pos[0]["plant_name"],
                        target_material=open_pos[0]["material_id"],
                        rationale=f"Deterministic fallback: Mitigates disruption. Critical plant runway is {critical_runway} days.",
                        estimated_cost_eur=actual_po_val
                    )
                ]

            brief.recommended_actions = filtered_actions
            return brief

        except Exception:
            continue

    # Graceful fallback: Pure deterministic brief constructed strictly from SQL data
    default_actions: List[MitigationAction] = []
    if open_pos and alts:
        matched_po_id = alts[0].get("po_id", open_pos[0]["po_id"])
        actual_po_val = float(po_lookup.get(matched_po_id, open_pos[0]).get("value_eur", 0.0))

        default_actions.append(
            MitigationAction(
                priority=1,
                title=f"Reroute {alts[0]['material_id']} to {alts[0]['alt_supplier_name']}",
                action_type="reroute_supplier",
                po_id=matched_po_id,
                target_supplier_id=alts[0]["alt_supplier_id"],
                target_plant=open_pos[0]["plant_name"],
                target_material=open_pos[0]["material_id"],
                rationale=f"Deterministic fallback: Plant runway is {critical_runway} days.",
                estimated_cost_eur=actual_po_val
            )
        )

    return ExecutiveBrief(
        headline=f"Supply Disruption: {crisis_context.get('impacted_country', 'Global')} {crisis_context.get('impacted_category', 'Component')}",
        criticality_summary=f"Assembly line stoppage risk identified with {critical_runway} days remaining.",
        financial_risk_eur=total_exposure,
        assembly_line_deadline_days=critical_runway,
        recommended_actions=default_actions,
        brief_source="deterministic_fallback"
    )