# CrisisSentinel

When a factory shuts down or a port closes, CrisisSentinel tells a manufacturer which of its orders are at risk, how much money is involved, and what to do about it. A human approves the final plan.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Built for the Nebius x NVIDIA Global AI Hackathon, **Best Apps and Agents** track.

- **Live demo:** ADD_DEMO_URL_HERE
- **Demo video (3 min):** ADD_YOUTUBE_URL_HERE

## The problem

Say a chip factory in Taiwan shuts down. A car maker needs answers fast: does this hit us, how badly, and what do we do?

News tells you what happened. It does not tell you that purchase order PO10482 for part MCU-X200 goes to the Stuttgart plant, where stock lasts only 10.9 more days.

AI models are good at reading news but bad at math, and they sometimes make up numbers. So we split the work. Models read and reason. A database does all the counting.

## How It Works

1. **Investigate:** Tavily searches live news via 3 targeted queries (disruption cause, automotive impact, recovery timeline).
2. **Extract Facts:** Nemotron-3-Nano extracts key claims, impacted countries, and material categories, normalized against database vocabulary.
3. **Resolve Conflicts:** If sources report conflicting timelines, Nemotron Nano triggers a follow-up query to settle the claim with citations.
4. **Calculate ERP Exposure:** Pure SQL joins the event to open purchase orders—calculating exposed capital (€), days of inventory runway per plant, and approved alternative vendors.
5. **Draft Response Plan:** Nemotron-3-Super proposes up to 3 prioritized reroute actions, bound strictly to exposed open POs.
6. **Adversarial Audit:** Deterministic checks verify that every quantity and plant matches the ERP; Nemotron Super red-teams operational assumptions (e.g., supplier concentration).
7. **Human Authorization:** An operator reviews and approves reroutes. Validated updates are written directly to the database.

![How CrisisSentinel works](docs/architecture.png)

## Data Integrity Guarantees

- **No Hallucinated Financials:** Value at risk, inventory runway, and assembly stoppage days are computed via SQL arithmetic.
- **Immutable Purchase Orders:** Material IDs and plant locations are populated directly from the ERP record, preventing mismatched parts or facilities.
- **Strict Supplier Validation:** Reroutes to vendors not explicitly registered in `alt_supplier_map` are rejected before execution.
- **Auditable Provenance:** Every claim extracted from news links directly to its source domain and article URL.
- **Honest Telemetry:** If a model call times out or degrades, the UI explicitly marks the stage as degraded rather than substituting synthetic fallback values.

## Technology Stack

- **NVIDIA Nemotron (via Nebius Token Factory):**
  - **Nemotron-3-Nano (30B):** High-throughput claim extraction, entity classification, and contradiction judging.
  - **Nemotron-3-Super (120B):** Executive mitigation planning, adversarial plan critique, and iterative revision loops.
- **Tavily Search API:** Targeted multi-query web intelligence and real-time conflict-resolution queries.
- **Deterministic Core:** SQLite ERP engine (`voltauto.db`), FastAPI backend (Python 3.13), React + Vite command console.

## Quickstart

### Prerequisites

- Python 3.10+
- Node.js 18+
- Nebius Token Factory API key (`NEBIUS_API_KEY`)
- Tavily API key (`TAVILY_API_KEY`)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env                               # add NEBIUS_API_KEY and TAVILY_API_KEY
python seed_data.py                                   # creates the sample database
uvicorn api:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                           # opens at http://localhost:5173
```

No API keys? The app starts in **Recorded** mode and replays three saved runs, no internet needed.

To try the full pipeline in the terminal:

```bash
python backend/main.py "Taiwan semiconductor supply chain disruption"
```

## Try the demo

1. Run the Taiwan semiconductor scenario in Live mode.
2. Look at the four numbers at the top (tagged `SQL`) and open Evidence to see the sources.
3. Read the critic's objections, then click **Revise plan**. The plan is rewritten and checked again.
4. Move the what-if sliders. Results update instantly with no AI call.
5. Click **Approve**. The reroutes are saved and the value at risk drops.

## The sample data

The database is made up. It describes a fictional German car maker, VoltAuto GmbH, with 21 suppliers, 50 materials, 5 plants and 199 purchase orders. It is not connected to SAP or any real system.

| Scenario              | Orders at risk | Value at risk | Shortest stock |
| --------------------- | -------------- | ------------- | -------------- |
| Taiwan semiconductors | 11             | €4.72M        | 3.2 days       |
| Poland batteries      | 12             | €6.17M        | 2.2 days       |
| Germany batteries     | 11             | €6.78M        | 4.2 days       |
| Japan sensors         | 42             | €17.15M       | 1.0 day        |

## Tests

```bash
cd backend && pytest -q          # 31 tests, no internet needed
cd frontend && npm test          # 12 UI tests
python backend/eval_benchmark.py --offline   # 20 of 20 checks pass
```

Accuracy of the live AI extraction depends on your own keys. Run `python backend/eval_benchmark.py` to measure it.

## Limits

- The data is fake, and there is no real ERP connection.
- Suppliers are matched by country and product type, so every supplier in that group is treated as equally affected.
- The what-if tool assumes the same capacity loss across a whole region and a steady drop in stock.
- We cannot check supplier capacity from the data, so the critic flags it for a human to check.
- Built for a single-user demo: no login, SQLite database.

## Feedback on the platforms

- **Token Factory:** model IDs are capitalized inconsistently (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` vs `nvidia/nemotron-3-super-120b-a12b`). Looking them up with `models.list()` is safer than hard-coding.
- **Nemotron:** reasoning models sometimes return output that is not clean JSON (empty content, reasoning tags, code fences), even in JSON mode. We wrote a forgiving parser with retries.
- **Tavily:** snippets are short, so search wording and source quality matter more than the number of results.

## Team

- Vivek Sawant: Multi-agent pipeline orchestration, deterministic ERP engine, Nebius/Nemotron integrations
- Dhruva Makwana: ERP database architecture, SQL seed datasets, automated oracle benchmarks
- Dhruval Makwana: Frontend architecture, real-time telemetry streaming, interactive what-if simulator

## License

MIT. See [LICENSE](LICENSE).
