# CrisisSentinel

**An agent that investigates a real-world supply disruption, measures what it means for a company's open purchase orders with SQL, and prepares an audited response for a human to approve.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Built for the **Nebius x NVIDIA Global AI Hackathon**. Models: NVIDIA Nemotron on **Nebius Token Factory**. Live web research: **Tavily**.

---

## The problem

When a fab shuts down in Taiwan or a port closes in Japan, a manufacturer needs three answers within hours: *does this actually affect us, how badly, and what do we do?* News tells you what happened. It never says that purchase order PO10482 for part MCU-X200 ships to the Stuttgart plant and that stock there covers 10.9 days.

Language models are good at reading the news and bad at arithmetic. Left alone, they invent supplier names and business numbers. CrisisSentinel uses each tool for what it is good at.

## How it works

| Stage | Done by | Output |
|---|---|---|
| 1. Web research | Tavily, 3 planned queries (what happened, automotive impact, recovery timeline) | Up to 10 sources |
| 2. Claim extraction | Nemotron Nano | Claims that cite source ids, plus the affected country and category |
| 3. Conflict check | Nemotron Nano + a follow-up Tavily search | Conflicting claims; a conflict is `resolved` only if a model cites a follow-up source that supports one side |
| 4. ERP exposure | **SQL only** | Value at risk, exposed POs, inventory runway per plant, approved alternative suppliers |
| 5. Response plan | Nemotron Super | Up to 3 actions, each tied to a real PO |
| 6. Critic audit | Rule checks, then Nemotron Super | Every number re-verified against SQL; model-written challenges to the plan |
| 7. Human approval | You | Reroutes are written to the database, each validated against the approved alternatives for that PO |

```
 Event text ──► Tavily ──► Nemotron Nano ──► country + category
                                                   │
                                                   ▼
              SQLite ERP  ◄──────────  SQL join (no AI): exposure, runway, alternatives
                   │                               │
                   │                               ▼
                   │                     Nemotron Super: plan
                   │                               │
                   │                               ▼
                   │              Critic: rule checks + Nemotron Super challenges
                   │                               │
                   ▼                               ▼
          What-if simulator            Human approves ──► validated reroute in the database
          (SQL arithmetic)
```

### Design rules that make it trustworthy

- **AI never produces a number you act on.** Value at risk, runway, stoppage days and order values come from SQL or Python.
- **The model cannot point at the wrong thing.** The plant, material and value of every action are copied from the PO's ERP record. A reroute to a supplier the ERP does not approve for that PO is dropped.
- **Failure is visible.** If a model call fails, the stage is labelled (`SQL fallback`, `Not independently reviewed`, `Degraded`) and the model is not credited. An event that cannot be interpreted reports "no exposure identified"; it never defaults to a canned scenario.
- **Claims are traceable.** Every claim links to the web page it came from.
- **A verdict is earned.** The critic's verdict comes from failed checks and challenge severity. There is no score. After a revision the critic audits the new plan again and may still object.

## Where Nebius, NVIDIA and Tavily are used

- **Nebius Token Factory** serves all inference through its OpenAI-compatible API. Model IDs are resolved from `models.list()` at runtime (casing differs between models), with documented fallbacks.
- **NVIDIA Nemotron**, tiered by task: **Nano** for high-volume extraction and conflict judging, **Super** for the plan, the critic and the revision. The UI shows which model produced each stage.
- **Tavily** is the research layer: a planned multi-query search, then targeted follow-up searches when claims conflict. At most 6 searches per scan.

## Run it

Prerequisites: Python 3.10+, Node 18+, a Nebius Token Factory key and a Tavily key.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env                                # then add NEBIUS_API_KEY and TAVILY_API_KEY
python seed_data.py                                    # creates voltauto.db
uvicorn api:app --port 8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

The backend works from any directory. Without API keys the UI starts in **Recorded** mode, which replays three live runs saved in `backend/cache/scenarios/` and needs no network.

Useful commands:

```bash
python backend/main.py "Taiwan semiconductor supply chain disruption"   # full pipeline in the terminal
python scripts/record_scenarios.py                                      # re-record the three scenarios (needs keys)
python backend/eval_benchmark.py --offline                              # check the SQL engine against an independent oracle
python backend/eval_benchmark.py                                        # also measures live extraction accuracy (needs keys)
```

Optional environment variables: `SCAN_RATE_LIMIT` (live scans per IP per 10 minutes, default 8), `CORS_ORIGINS` (comma-separated, default `*`), `VITE_API_URL` (frontend, when the backend is on another origin).

## Demo script (3 minutes)

1. **Investigate** the Taiwan semiconductor scenario in Live mode. Watch each pipeline stage start and finish as it really happens.
2. **Read the numbers.** The four KPIs are tagged `SQL`. Open *Evidence* and click a source link.
3. **Challenge the plan.** The critic lists failed rule checks (if any), single-supplier concentration, and model-written objections. Click *Revise plan*: the plan is rewritten and **audited again**.
4. **What-if.** Drag the disruption length and capacity sliders. Rerouting's benefit recomputes instantly, with no model call.
5. **Approve.** The reroutes are written to the database; value at risk drops accordingly. *Reset demo data* restores the starting state.

## The data

`voltauto.db` is a **synthetic**, SAP-inspired dataset for a fictional German EV manufacturer (VoltAuto GmbH): 21 suppliers, 50 materials, 5 plants, 199 purchase orders, and approved alternative suppliers. It is not connected to SAP and makes no claim to be. The relationships are what matter: supplier country and category, material, PO, plant, inventory, and approved alternative.

| Scenario | Exposed open POs | Value at risk | Shortest runway |
|---|---|---|---|
| Taiwan semiconductors | 11 | €4.72M | 3.2 days |
| Poland batteries | 12 | €6.17M | 2.2 days |
| Germany batteries | 11 | €6.78M | 4.2 days |
| Japan sensors | 42 | €17.15M | 1.0 day |

## Testing and verification

- `cd backend && pytest -q`: 31 offline tests (no network; models and Tavily are stubbed). They cover the failure modes above: no fabricated events, contradictions resolved only with cited evidence, unapproved suppliers refused, plant/material taken from the ERP, honest provenance, real revisions, streaming order, rate limiting.
- `cd frontend && npm test`: 12 component tests running the real UI against payloads produced by the real backend.
- `python backend/eval_benchmark.py --offline`: 20 of 20 checks, comparing the engine to an independent SQL oracle for four scenarios.
- **Live extraction accuracy has to be measured with your own keys** (`python backend/eval_benchmark.py`). Results are written to `backend/eval_results.json`. Do not quote a figure that has not been produced by that run.

## Known limitations

- Data is synthetic; there is no live ERP integration.
- The what-if model assumes uniform capacity loss across a region, linear inventory depletion, and uses the PO lead time as a proxy for an alternative supplier's lead time. These are listed in the UI.
- Matching an event to suppliers is by country and category, so every supplier in that country and category is treated as equally affected.
- *Evidence strength* is a transparent heuristic (distinct domains minus unresolved conflicts), not a probability.
- Supplier capacity and qualification cannot be checked from the data; the critic raises them as questions for a human.
- SQLite and an in-memory rate limiter suit a single-instance demo, not production. There is no authentication.

## Feedback on the platforms

Observations from building this (edit with your own before submitting):

- **Token Factory model IDs are inconsistent in casing** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` versus `nvidia/nemotron-3-super-120b-a12b`), so resolving IDs from `models.list()` is safer than hard-coding.
- **Nemotron reasoning models can return output that is not plain JSON** (empty `content`, reasoning tags, or fenced blocks) even in JSON mode, so every call goes through a tolerant parser with explicit `max_tokens` and retries.
- **Tavily snippets are short.** Claim extraction works from snippets, so source quality and query wording matter more than result count.

## Team

- **Vivek Sawant**: backend orchestration, deterministic engine, Nebius and Nemotron integration
- **Dhruva Makwana**: ERP database design, seeding, benchmark and test scenarios
- **Dhruval Patel**: frontend

## License

MIT. See [LICENSE](LICENSE).
