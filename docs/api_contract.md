# CrisisSentinel API contract

Base URL in development: `http://localhost:8000` (the Vite dev server proxies `/api`, so the frontend uses relative URLs).
Interactive docs: `/docs`.

All money values are EUR and come from SQL. Fields named `*_source` or `degraded` tell the client when a stage did **not** use the model.

## `GET /api/health`
Preflight. Never returns secrets.
```json
{ "ok": true, "database": true, "keys": { "nebius": true, "tavily": true }, "recorded_scenarios": ["japan_sensor", "poland_battery", "taiwan_semiconductor"] }
```

## `POST /api/disruption/scan`
Runs the whole pipeline and returns one JSON document. Body: `{ "query": "..." }`. Rate limited per IP (`SCAN_RATE_LIMIT`, default 8 per 10 minutes, HTTP 429).

Response keys:

| Key | Meaning |
|---|---|
| `matched` | `true` only if the event mapped to a country and category **and** SQL found open POs |
| `intelligence` | Event, severity, `impacted_country`, `impacted_category`, `estimated_duration_days`, `sources[]`, `claims[]`, `contradictions[]`, `evidence_strength`, `search_log[]`, `extraction_method` (`model` or `degraded`) |
| `exposure` | SQL result: `total_exposure_eur`, `open_pos_count`, `critical_runway_days`, `affected_open_pos[]`, `mitigation_alternatives[]` (approved `po_id` → `alt_supplier_id` pairs) |
| `brief` | Plan: `headline`, `recommended_actions[]`, `brief_source` (`nemotron` or `deterministic_fallback`), `model_used`. Plant, material and order values are copied from the PO record |
| `critique` | `checks[]` (rule checks, each `passed`), `challenges[]` (`origin`: `deterministic` or `model`), `verdict` (`accept`, `revise`, `escalate`, `unverified`), `status`, `model_used`, `revised` |
| `provenance` | Models actually used per stage (`null` when a stage fell back), search and source counts, `contradictions_resolved`, `degraded[]`, `timings_s`, `total_s`, `generated_at` |

## `GET /api/disruption/scan/stream?query=...`
Server-sent events from the same pipeline. Each event is `data: {json}`:

- `{"stage": "research|extraction|contradictions|exposure|strategy|critic", "status": "running|done", "message": "...", "elapsed_s": 12.3}` emitted when a stage really starts or finishes
- `{"stage": "result", "data": { ...same payload as /scan... }}` final event
- `{"stage": "error", "message": "..."}` on failure

## `POST /api/whatif`
Deterministic simulation. Body: `country`, `category`, `disruption_days` (1 to 90), `capacity_offline_pct` (0 to 100), `apply_reroute`, optional `alt_lead_time_override`. Returns `totals.baseline`, `totals.with_reroute`, `totals.delta`, per-`plants[]`, per-`pos[]`, `pos_without_inventory_record[]`, `assumptions[]`. Each PO is counted once regardless of how many alternatives it has.

## `POST /api/mitigation/execute`
Approves reroutes. Every pair is validated against `alt_supplier_map` for that PO.
```json
{ "actions": [{ "po_id": "PO10482", "alt_supplier_id": "SUP014" }], "target_country": "Taiwan", "target_category": "semiconductor" }
```
Returns `execution` (per-PO `results[]`) and `updated_exposure`. HTTP 409 if nothing could be applied (unapproved supplier, already rerouted, unknown PO).

## `POST /api/mitigation/revise`
One bounded revision. Body: `brief`, `critique`, `intelligence`. The strategist rewrites the plan against the critic's challenges, then the critic audits the **new** plan; the verdict returned is the real one. HTTP 502 if the model cannot produce a valid plan (the original plan is unchanged).

## `POST /api/demo/reset`
Rebuilds `voltauto.db` from `seed_data.py`.

## `GET /api/cache/scenario/{name}`
Recorded live runs (`taiwan_semiconductor`, `poland_battery`, `japan_sensor`). AI-written content is served as recorded; exposure, order values and rule checks are recomputed from the current database, and recorded actions that are no longer valid are removed (`cache_notice` says so). Adds `cached: true` and `recorded_at`.
