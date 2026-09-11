"""
Strategist Agent for CrisisSentinel.
Synthesizes deterministic ERP exposure into executive mitigation actions using Nemotron.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
FALLBACK_STRATEGIST_MODEL = "nvidia/NVIDIA-Nemotron-3-Super-120B-A3B"

client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ["NEBIUS_API_KEY"],
)

class MitigationAction(BaseModel):
    priority: int
    title: str
    action_type: str  # "reroute_supplier" | "air_freight" | "line_rebalancing" | "buffer_stock"
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

def resolve_reasoning_model() -> str:
    """Selects a high-reasoning model (Super or Ultra) for strategy generation."""
    try:
        models = client.models.list()
        nemotron_models = [m.id for m in models.data if "nemotron" in m.id.lower()]
        ultra_or_super = [m for m in nemotron_models if "ultra" in m.lower() or "super" in m.lower()]
        return ultra_or_super[0] if ultra_or_super else (nemotron_models[0] if nemotron_models else FALLBACK_STRATEGIST_MODEL)
    except Exception:
        return FALLBACK_STRATEGIST_MODEL

def generate_mitigation_strategy(crisis_context: Dict[str, Any], erp_exposure: Dict[str, Any]) -> ExecutiveBrief:
    """Feeds external context and internal SQL data into the Strategist model."""
    model_id = resolve_reasoning_model()

    system_prompt = (
        "You are the Chief Supply Chain Strategist for VoltAuto GmbH. "
        "Analyze the deterministic ERP exposure resulting from an external disruption. "
        "All calculations must be grounded strictly in the provided ERP data. "
        "If alternative suppliers are listed in the ERP data, prioritize rerouting orders. "
        "Provide prioritized, concrete operational actions with cost-benefit rationale.\n\n"
        f"Output MUST be valid JSON adhering to:\n{json.dumps(ExecutiveBrief.model_json_schema(), indent=2)}"
    )

    user_payload = {
        "external_disruption_event": crisis_context,
        "internal_erp_exposure": erp_exposure
    }

    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, indent=2)},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw_output = completion.choices[0].message.content or "{}"
    return ExecutiveBrief.model_validate_json(raw_output)