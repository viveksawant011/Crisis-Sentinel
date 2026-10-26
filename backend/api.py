"""
CrisisSentinel FastAPI orchestrator.

Endpoints
  POST /api/disruption/scan          full pipeline, one JSON response
  GET  /api/disruption/scan/stream   same pipeline, streamed as server-sent events
  POST /api/whatif                   deterministic stoppage / value-at-risk simulation
  POST /api/mitigation/execute       approve reroutes (each validated against alt_supplier_map)
  POST /api/mitigation/revise        one real revision: new plan + fresh critic audit
  POST /api/demo/reset               rebuild the demo database
  GET  /api/cache/scenario/{name}    recorded live runs for offline demos
  GET  /api/health                   preflight (no secrets are returned)
"""

import asyncio
import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from critic import critique_and_verify, run_deterministic_checks
from engine import apply_reroute_mitigation, evaluate_erp_exposure, reset_demo_state
from investigator import run_investigation
from strategist import MitigationAction, generate_mitigation_strategy, validate_actions
from tavily_nemotron_probe import nebius_client, resolve_nemotron_model, resolve_super_model
from whatif import WhatIfRequest, simulate_whatif

DB_PATH = str(BACKEND_DIR / "voltauto.db")
if not Path(DB_PATH).exists():  # fresh clone or fresh deploy: build the demo database
    reset_demo_state()
CACHE_DIR = BACKEND_DIR / "cache" / "scenarios"

app = FastAPI(title="CrisisSentinel API", version="2.1.0")

_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_origins, allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Simple per-IP limiter so a public demo URL cannot burn the API credits.
# ---------------------------------------------------------------------------
_RATE_WINDOW_S = 600
_rate_hits: Dict[str, List[float]] = {}


def rate_limit(request: Request) -> None:
    limit = int(os.environ.get("SCAN_RATE_LIMIT", "8"))
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = [t for t in _rate_hits.get(ip, []) if now - t < _RATE_WINDOW_S]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail=f"Live scan limit reached ({limit} per 10 minutes). Use the recorded runs or try again shortly.")
    hits.append(now)
    _rate_hits[ip] = hits


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
Emit = Callable[[Dict[str, Any]], None]


def run_scan(query_text: str, emit: Optional[Emit] = None) -> Dict[str, Any]:
    """The one pipeline used by both the JSON and the streaming endpoint.
    Events are emitted when a stage really starts or finishes."""
    emit = emit or (lambda ev: None)
    t0 = time.time()
    timings: Dict[str, float] = {}
    started: Dict[str, float] = {}
    state = {"current": None}
    degraded: List[str] = []

    def start(stage: str, message: str) -> None:
        started[stage] = time.time()
        state["current"] = stage
        emit({"stage": stage, "status": "running", "message": message, "elapsed_s": round(time.time() - t0, 1)})

    def done(stage: str, message: str) -> None:
        timings[stage] = round(time.time() - started.get(stage, time.time()), 1)
        emit({"stage": stage, "status": "done", "message": message, "elapsed_s": round(time.time() - t0, 1)})

    def on_progress(stage: str, message: str) -> None:
        if state["current"] and state["current"] != stage:
            done(state["current"], "Complete")
        start(stage, message)

    nano_model = resolve_nemotron_model()
    super_model = resolve_super_model()

    # 1-3. Research, extraction, contradictions
    intel = run_investigation(query_text, model_id=nano_model, on_progress=on_progress)
    if state["current"]:
        done(state["current"], "Complete")
    if "contradictions" not in started:
        start("contradictions", "Checking claims for conflicts")
        done("contradictions", "No conflicting claims detected" if intel.claims else "Skipped: no claims to compare")
    intel_dict = intel.model_dump()
    n_resolved = sum(1 for c in intel.contradictions if c.resolution_status == "resolved")
    if intel.extraction_method != "model":
        degraded.append("extraction")

    # 4. Deterministic ERP exposure
    start("exposure", "Joining the event to open purchase orders in SQL")
    if intel.impacted_country and intel.impacted_category:
        exposure = evaluate_erp_exposure(intel.impacted_country, intel.impacted_category, db_path=DB_PATH)
    else:
        exposure = {
            "matched": False, "impacted_country": intel.impacted_country,
            "impacted_category": intel.impacted_category,
            "message": ("The event could not be interpreted (search or model unavailable)."
                        if intel.extraction_method != "model"
                        else "The event does not map to a country and category in the supplier base."),
            "total_exposure_eur": 0.0, "open_pos_count": 0, "critical_runway_days": None,
            "affected_open_pos": [], "mitigation_alternatives": [],
        }
    done("exposure", f"€{exposure.get('total_exposure_eur', 0):,.0f} across {exposure.get('open_pos_count', 0)} open POs"
         if exposure.get("matched") else exposure.get("message", "No exposure identified"))

    brief: Optional[Dict[str, Any]] = None
    critique: Optional[Dict[str, Any]] = None
    if exposure.get("matched"):
        start("strategy", "Nemotron Super is drafting mitigation actions")
        brief_obj = generate_mitigation_strategy(intel_dict, exposure, model_id=super_model)
        brief = brief_obj.model_dump()
        if brief_obj.brief_source != "nemotron":
            degraded.append("strategy")
        done("strategy", f"{len(brief_obj.recommended_actions)} action(s) proposed"
             + ("" if brief_obj.brief_source == "nemotron" else " (SQL fallback)"))

        start("critic", "Running deterministic checks, then the adversarial critic")
        critique_obj = critique_and_verify(
            brief=brief, erp_exposure=exposure, claims=intel_dict.get("claims", []),
            contradictions=intel_dict.get("contradictions", []), client=nebius_client, model_id=super_model,
        )
        critique = critique_obj.model_dump()
        if critique_obj.status != "model":
            degraded.append("critic")
        done("critic", f"Verdict: {critique_obj.verdict}")

    provenance = {
        "models": {
            "extraction": nano_model,
            "strategy": brief.get("model_used") if brief else None,
            "critic": critique.get("model_used") if critique else None,
        },
        "search_count": sum(1 for s in intel.search_log if "error" not in s),
        "source_count": len(intel.sources),
        "claims_extracted": len(intel.claims),
        "contradictions_identified": len(intel.contradictions),
        "contradictions_resolved": n_resolved,
        "extraction_method": intel.extraction_method,
        "degraded": degraded,
        "timings_s": timings,
        "total_s": round(time.time() - t0, 1),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return {
        "matched": bool(exposure.get("matched")),
        "intelligence": intel_dict, "exposure": exposure,
        "brief": brief, "critique": critique, "provenance": provenance,
    }


class ScanRequest(BaseModel):
    query: Optional[str] = None
    event_query: Optional[str] = None

    def get_query_text(self) -> str:
        return (self.query or self.event_query or "").strip()


@app.get("/")
def root():
    return {"service": "CrisisSentinel API", "status": "online", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "database": Path(DB_PATH).exists(),
        "keys": {"nebius": bool(os.environ.get("NEBIUS_API_KEY")), "tavily": bool(os.environ.get("TAVILY_API_KEY"))},
        "recorded_scenarios": sorted(p.stem for p in CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else [],
    }


@app.post("/api/disruption/scan")
def scan_disruption(req: ScanRequest, _rl: None = Depends(rate_limit)):
    query_text = req.get_query_text()
    if not query_text:
        raise HTTPException(status_code=422, detail="A query is required.")
    return run_scan(query_text)


@app.get("/api/disruption/scan/stream")
async def scan_stream(query: str, _rl: None = Depends(rate_limit)):
    """Server-sent events. Each event reflects work that has actually started or finished;
    the final event ('stage': 'result') carries the complete scan payload."""
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="A query is required.")
    q: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()

    def worker() -> None:
        try:
            q.put({"stage": "result", "status": "done", "data": run_scan(query, emit=q.put)})
        except Exception as exc:  # surfaced to the UI, never swallowed
            q.put({"stage": "error", "status": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def events():
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/whatif")
def whatif_endpoint(req: WhatIfRequest):
    return simulate_whatif(
        country=req.country, category=req.category, disruption_days=req.disruption_days,
        capacity_offline_pct=req.capacity_offline_pct, apply_reroute=req.apply_reroute,
        alt_lead_time_override=req.alt_lead_time_override, db_path=DB_PATH,
    )


class ActionRef(BaseModel):
    po_id: str
    alt_supplier_id: str


class ExecuteRequest(BaseModel):
    actions: Optional[List[ActionRef]] = None
    po_ids: Optional[List[str]] = None  # legacy
    po_id: Optional[str] = None  # legacy
    alt_supplier_id: Optional[str] = None  # legacy
    target_country: Optional[str] = None
    target_category: Optional[str] = None


@app.post("/api/mitigation/execute")
def execute_mitigation(req: ExecuteRequest):
    """Every reroute is validated against alt_supplier_map for that specific PO."""
    pairs: List[tuple] = []
    if req.actions:
        pairs = [(a.po_id, a.alt_supplier_id) for a in req.actions]
    elif req.alt_supplier_id and (req.po_ids or req.po_id):
        pairs = [(p, req.alt_supplier_id) for p in (req.po_ids or [req.po_id])]
    if not pairs:
        raise HTTPException(status_code=422, detail="Provide 'actions' (po_id + alt_supplier_id) to execute.")

    results = [apply_reroute_mitigation(po, alt, db_path=DB_PATH) for po, alt in pairs]
    ok = [r for r in results if r.get("success")]
    if not ok:
        raise HTTPException(status_code=409, detail={"message": "No reroute could be applied.", "results": results})

    updated = None
    if req.target_country and req.target_category:
        updated = evaluate_erp_exposure(req.target_country, req.target_category, db_path=DB_PATH)
    return {
        "execution": {
            "status": "SUCCESS" if len(ok) == len(results) else "PARTIAL",
            "rerouted_pos_count": len(ok), "failed_pos_count": len(results) - len(ok), "results": results,
        },
        "updated_exposure": updated,
    }


class ReviseRequest(BaseModel):
    brief: Dict[str, Any]
    critique: Dict[str, Any]
    exposure: Optional[Dict[str, Any]] = None
    intelligence: Optional[Dict[str, Any]] = None
    claims: Optional[list] = None
    query: Optional[str] = None


@app.post("/api/mitigation/revise", dependencies=[Depends(rate_limit)])
def revise_strategy(req: ReviseRequest):
    """One bounded revision. The strategist rewrites the plan against the critic's challenges,
    then the critic audits the NEW plan. The verdict returned is the real one."""
    intel = req.intelligence or {}
    exposure = req.exposure or {}
    if intel.get("impacted_country") and intel.get("impacted_category"):
        exposure = evaluate_erp_exposure(intel["impacted_country"], intel["impacted_category"], db_path=DB_PATH)
    if not exposure.get("matched"):
        raise HTTPException(status_code=422, detail="No exposure to revise a plan against.")

    super_model = resolve_super_model()
    challenges = req.critique.get("challenges", [])
    new_brief = generate_mitigation_strategy(intel, exposure, critique_feedback=challenges, model_id=super_model)
    if new_brief.brief_source != "nemotron":
        raise HTTPException(status_code=502, detail="Revision unavailable: the model did not return a valid plan. The original plan is unchanged.")

    claims = req.claims or intel.get("claims", [])
    new_critique = critique_and_verify(
        brief=new_brief.model_dump(), erp_exposure=exposure, claims=claims,
        contradictions=intel.get("contradictions", []), client=nebius_client, model_id=super_model, revised=True,
    )
    return {
        "status": "revised", "previous_verdict": req.critique.get("verdict"),
        "brief": new_brief.model_dump(), "critique": new_critique.model_dump(), "exposure": exposure,
    }


@app.post("/api/demo/reset")
def reset_demo():
    result = reset_demo_state()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Reset failed"))
    return {"status": "success", "message": "Demo state reset to the clean baseline."}


@app.get("/api/cache/scenario/{name}")
def get_cached_scenario(name: str):
    """Recorded live runs for offline demos.

    The AI-written parts (claims, sources, headline, rationales, critic challenges) are served exactly
    as recorded. Everything deterministic is recomputed from the current database, so a recording can
    never disagree with the ERP: exposure is fresh, and recorded actions that are no longer valid for
    their PO are removed (and the response says so)."""
    if not name.replace("_", "").isalnum():
        raise HTTPException(status_code=404, detail="Unknown scenario.")
    path = CACHE_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found in cache.")
    data = json.loads(path.read_text(encoding="utf-8"))

    intel, brief, crit = data.get("intelligence") or {}, data.get("brief"), data.get("critique")
    if intel.get("impacted_country") and intel.get("impacted_category"):
        fresh = evaluate_erp_exposure(intel["impacted_country"], intel["impacted_category"], db_path=DB_PATH)
        data["exposure"] = fresh
        data["matched"] = bool(fresh.get("matched"))
        if brief and fresh.get("matched"):
            recorded = [MitigationAction.model_validate(a) for a in brief.get("recommended_actions", [])]
            kept = validate_actions(recorded, fresh)
            if len(kept) < len(recorded):
                data["cache_notice"] = (f"{len(recorded) - len(kept)} recorded action(s) were removed because the ERP baseline "
                                        "changed since this run was recorded. Re-record scenarios to refresh them.")
            brief["recommended_actions"] = [a.model_dump() for a in kept]
            brief["financial_risk_eur"] = fresh["total_exposure_eur"]
            brief["assembly_line_deadline_days"] = fresh.get("critical_runway_days")
            if crit is not None:
                crit["checks"] = [c.model_dump() for c in run_deterministic_checks(brief, fresh)]
                crit.setdefault("status", "model")

    data["cached"] = True
    data["recorded_at"] = (data.get("provenance") or {}).get("generated_at") or datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    return data
