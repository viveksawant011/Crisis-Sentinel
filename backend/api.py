"""
CrisisSentinel API: Exposes external intelligence scanning,
ERP exposure evaluation, and mitigation execution.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from tavily_nemotron_probe import research, analyze_disruption, resolve_nemotron_model
from engine import evaluate_erp_exposure, apply_reroute_mitigation, reset_demo_state
from strategist import generate_mitigation_strategy

app = FastAPI(
    title="CrisisSentinel API",
    description="Enterprise Supply Chain Disruption Intelligence Engine for VoltAuto GmbH",
    version="1.0.0"
)

# Enable CORS so the frontend dashboard can communicate across ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DisruptionRequest(BaseModel):
    query: str

class MitigationApprovalRequest(BaseModel):
    po_id: str
    alt_supplier_id: str

@app.get("/api/health")
def health_check():
    return {"status": "operational", "system": "CrisisSentinel"}

@app.post("/api/disruption/scan")
def scan_disruption(payload: DisruptionRequest):
    """
    Executes:
    1. Tavily Search + Nemotron Nano (External Extraction)
    2. SQLite Engine (Deterministic ERP Math & Inventory Runway)
    3. Nemotron Super/Ultra (Executive Mitigation Brief)
    """
    try:
        active_model = resolve_nemotron_model()
        
        # 1. External Web Intelligence
        sources = research(payload.query)
        analysis = analyze_disruption(payload.query, sources, active_model)

        # 2. Deterministic ERP Math
        erp_exposure = evaluate_erp_exposure(
            country=analysis.impacted_country,
            category=analysis.impacted_category
        )

        if not erp_exposure["matched"]:
            return {
                "matched": False,
                "intelligence": analysis.model_dump(),
                "exposure": erp_exposure,
                "brief": None
            }

        # 3. High-Reasoning Mitigation Strategy
        brief = generate_mitigation_strategy(analysis.model_dump(), erp_exposure)

        return {
            "matched": True,
            "intelligence": analysis.model_dump(),
            "exposure": erp_exposure,
            "brief": brief.model_dump()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mitigation/execute")
def execute_mitigation(action: MitigationApprovalRequest):
    """
    Stage 4: Updates the database when the human operator approves a reroute.
    """
    try:
        result = apply_reroute_mitigation(action.po_id, action.alt_supplier_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.post("/api/demo/reset")
def reset_demo():
    """Rebuild the demo database so the scenario can be replayed from scratch."""
    result = reset_demo_state()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get("/")
def root():
    """Redirect root visitors directly to Swagger API docs."""
    return RedirectResponse(url="/docs")