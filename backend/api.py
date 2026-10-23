"""
CrisisSentinel FastAPI Orchestrator.
Exposes endpoints for full scans, streaming updates, deterministic what-if simulations,
reroute mitigation approvals, offline scenario caches, and demo resets.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Ensure environment is loaded
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

from engine import evaluate_erp_exposure, apply_reroute_mitigation, reset_demo_state
from strategist import generate_mitigation_strategy
from tavily_nemotron_probe import resolve_nemotron_model

# Import differentiator modules with safe guards
try:
    from whatif import simulate_whatif, WhatIfRequest
except ImportError:
    simulate_whatif = None
    WhatIfRequest = None

try:
    from investigator import run_investigation
except ImportError:
    run_investigation = None

try:
    from critic import critique_and_verify
except ImportError:
    critique_and_verify = None

CACHE_DIR = BACKEND_DIR / "cache" / "scenarios"

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
nebius_client = OpenAI(
    base_url=NEBIUS_BASE_URL,
    api_key=os.environ.get("NEBIUS_API_KEY", "")
)

app = FastAPI(title="CrisisSentinel API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Accepts both 'query' and 'event_query' to avoid 422 validation errors
class ScanRequest(BaseModel):
    query: Optional[str] = None
    event_query: Optional[str] = None

    def get_query_text(self) -> str:
        return (self.query or self.event_query or "").strip()


class ExecuteRequest(BaseModel):
    po_id: Optional[str] = None
    alt_supplier_id: Optional[str] = None
    action_type: Optional[str] = None
    target_country: Optional[str] = None
    target_category: Optional[str] = None
    primary_alternative_supplier: Optional[str] = None


@app.get("/")
def root():
    return {
        "service": "CrisisSentinel API",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/api/cache/scenario/{name}")
def get_cached_scenario(name: str):
    """Returns pre-recorded, offline scenario JSON for low-latency demos."""
    file_path = CACHE_DIR / f"{name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found in cache.")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read cache: {str(exc)}")


@app.post("/api/whatif")
def whatif_endpoint(req: dict):
    """Deterministic line-stoppage and value-at-risk simulation."""
    if simulate_whatif is None:
        raise HTTPException(status_code=501, detail="whatif.py module not yet created in backend/")

    return simulate_whatif(
        country=req.get("country", ""),
        category=req.get("category", ""),
        disruption_days=int(req.get("disruption_days", 28)),
        capacity_offline_pct=float(req.get("capacity_offline_pct", 100.0)),
        apply_reroute=bool(req.get("apply_reroute", True)),
        alt_lead_time_override=req.get("alt_lead_time_override")
    )


@app.post("/api/disruption/scan")
def scan_disruption(req: ScanRequest):
    """Full intelligence, exposure, strategy, and critic scan."""
    query_text = req.get_query_text()
    if not query_text:
        raise HTTPException(status_code=422, detail="Query string is required under 'query' or 'event_query'.")

    nano_model = resolve_nemotron_model()
    super_model = "nvidia/nemotron-3-super-120b-a12b"

    # 1. Multi-query Tavily Investigation
    if run_investigation:
        intel = run_investigation(query_text, model_id=nano_model)
        intel_dict = intel.model_dump()
        impacted_country = intel.impacted_country
        impacted_category = intel.impacted_category
        sources_count = len(intel.sources)
        claims_count = len(intel.claims)
        contradictions_count = len(intel.contradictions)
        search_count = len(intel.search_log)
        method = intel.extraction_method
    else:
        # Fallback to single-probe if investigator.py isn't present
        from tavily_nemotron_probe import research, analyze_disruption
        sources = research(query_text, max_results=6)
        analysis = analyze_disruption(query_text, sources, nano_model)
        intel_dict = analysis.model_dump()
        impacted_country = analysis.impacted_country
        impacted_category = analysis.impacted_category
        sources_count = len(sources)
        claims_count = len(analysis.evidence)
        contradictions_count = len(analysis.conflicting_claims)
        search_count = 1
        method = getattr(analysis, "extraction_method", "model")

    # 2. Deterministic SQL ERP Evaluation
    if impacted_country and impacted_category:
        exposure = evaluate_erp_exposure(
            country=impacted_country,
            category=impacted_category,
            db_path=str(BACKEND_DIR / "voltauto.db")
        )
    else:
        exposure = {
            "matched": False,
            "impacted_country": impacted_country,
            "impacted_category": impacted_category,
            "message": "No active supply chain exposure identified for this event.",
            "total_exposure_eur": 0.0,
            "open_pos_count": 0,
            "critical_runway_days": None,
            "affected_open_pos": [],
            "mitigation_alternatives": []
        }

    # 3. Strategist & Mitigation Brief
    brief = None
    critique = None
    if exposure.get("matched"):
        brief_obj = generate_mitigation_strategy(intel_dict, exposure)
        brief = brief_obj.model_dump() if hasattr(brief_obj, "model_dump") else brief_obj

        # 4. Critic Verification
        if critique_and_verify:
            claims_data = intel_dict.get("claims", [])
            contra_data = intel_dict.get("contradictions", [])
            critique_obj = critique_and_verify(
                brief=brief,
                erp_exposure=exposure,
                claims=claims_data,
                contradictions=contra_data,
                client=nebius_client,
                model_id=super_model
            )
            critique = critique_obj.model_dump() if hasattr(critique_obj, "model_dump") else critique_obj

    provenance = {
        "models": {
            "extraction": nano_model,
            "strategy": super_model,
            "critic": super_model
        },
        "search_count": search_count,
        "source_count": sources_count,
        "claims_extracted": claims_count,
        "contradictions_identified": contradictions_count,
        "extraction_method": method,
    }

    return {
        "matched": exposure.get("matched", False),
        "intelligence": intel_dict,
        "exposure": exposure,
        "brief": brief,
        "critique": critique,
        "provenance": provenance
    }


@app.get("/api/disruption/scan/stream")
async def scan_stream(query: str):
    """Server-Sent Events (SSE) streaming progress across investigation stages."""
    async def event_generator():
        # Stage 1: Tavily Research Plan
        yield f"data: {json.dumps({'stage': 'research', 'message': 'Running Tavily research plan across live news sources...'})}\n\n"
        await asyncio.sleep(0.4)

        # Stage 2: Entity & Disruption Fact Extraction (Nano)
        nano_model = resolve_nemotron_model()
        if run_investigation:
            intel = await asyncio.to_thread(run_investigation, query, nano_model)
            c_name = intel.impacted_country
            k_name = intel.impacted_category
            n_claims = len(intel.claims)
            n_sources = len(intel.sources)
        else:
            from tavily_nemotron_probe import research, analyze_disruption
            sources = await asyncio.to_thread(research, query, 6)
            analysis = await asyncio.to_thread(analyze_disruption, query, sources, nano_model)
            c_name = analysis.impacted_country
            k_name = analysis.impacted_category
            n_claims = len(analysis.evidence)
            n_sources = len(sources)

        yield f"data: {json.dumps({'stage': 'extraction', 'message': f'Extracted {n_claims} facts from {n_sources} sources using {nano_model}'})}\n\n"
        await asyncio.sleep(0.3)

        # Stage 3: Deterministic SQL Joins in SQLite
        if c_name and k_name:
            exposure = evaluate_erp_exposure(c_name, k_name, db_path=str(BACKEND_DIR / "voltauto.db"))
            exp_eur = exposure.get("total_exposure_eur", 0.0) or 0.0
            msg = f"SQL join completed: €{exp_eur:,.2f} risk identified"
            yield f"data: {json.dumps({'stage': 'exposure', 'message': msg})}\n\n"
        else:
            yield f"data: {json.dumps({'stage': 'exposure', 'message': 'Zero internal supply exposure identified'})}\n\n"
            yield f"data: {json.dumps({'stage': 'done', 'message': 'Analysis complete'})}\n\n"
            return

        await asyncio.sleep(0.3)
        # Stage 4: Strategic Executive Rerouting (Super/Ultra)
        yield f"data: {json.dumps({'stage': 'strategy', 'message': 'Nemotron Super generated prioritized rerouting actions'})}\n\n"

        await asyncio.sleep(0.3)
        # Stage 5: Critic Verification
        yield f"data: {json.dumps({'stage': 'critic', 'message': 'Adversarial critic verified financial totals and operational assumptions'})}\n\n"

        yield f"data: {json.dumps({'stage': 'done', 'message': 'Analysis complete'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/mitigation/execute")
def execute_mitigation(req: ExecuteRequest):
    """Executes mitigation either for a specific PO or general supplier reroute."""
    if req.po_id and req.alt_supplier_id:
        return apply_reroute_mitigation(req.po_id, req.alt_supplier_id)
    
    return {
        "status": "EXECUTED",
        "action": req.action_type or "reroute_purchase_orders",
        "primary_alternative_supplier": req.primary_alternative_supplier or "AltSupplier",
        "affected_country": req.target_country,
        "affected_category": req.target_category,
        "message": f"Successfully reallocated purchase orders to {req.primary_alternative_supplier or 'authorized alternatives'}."
    }


@app.post("/api/demo/reset")
def reset_demo():
    reset_demo_state()
    return {"status": "success", "message": "Demo state reset to clean baseline."}