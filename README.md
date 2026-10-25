Here is the comprehensive, production-grade `README.md` for **CrisisSentinel**.

It specifically addresses all four judging criteria (**Technological Implementation**, **Design**, **Potential Impact**, and **Quality of the Idea**) and highlights how you utilized **NVIDIA Nemotron on Nebius Token Factory** and the **Tavily Search API**.

---

```markdown
# ◉ CrisisSentinel

### Autonomous Supply Chain Command Center Powered by NVIDIA Nemotron & Nebius Token Factory

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Nebius%20Token%20Factory-7928CA)](https://tokenfactory.nebius.com)
[![Models](https://img.shields.io/badge/Models-Nemotron--3--Nano%20%7C%20Nemotron--3--Super-76B900)](https://build.nvidia.com)
[![Search](https://img.shields.io/badge/Search-Tavily%20API-00B4D8)](https://tavily.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2F%20SQLite-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%2F%20Vite-61DAFB)](https://react.dev/)

> **CrisisSentinel** bridges the critical gap between unstructured, real-world geopolitical shock signals and internal corporate balance sheets. It transforms live web intelligence into deterministic ERP impact analysis, models plant stoppage timelines with zero-hallucination inventory math, triggers an adversarial red-team audit, and executes transactional purchase order reroutes in real-time.

---

## 📌 Executive Summary & Problem Space

When global supply chain shocks hit—such as semiconductor fab halts in Taiwan, battery cathode logistics strikes in Poland, or sensor export embargoes in Japan—automotive manufacturers face stoppage costs exceeding **€500,000+ per hour per plant**.

### The Core Flaw in Current AI Approaches

Most LLM agents hallucinate arithmetic, invent fictional supplier entities, and generate ungrounded mitigation advice. Furthermore, real-world news articles (via Tavily) report on real entities (like TSMC or ASE Group) and will never mention an enterprise's internal ERP part numbers (e.g., `MCU-X200`). Asking an LLM to guess internal suppliers directly leads to catastrophic hallucinations.

### The CrisisSentinel Solution: The AI vs. Deterministic Split

1. **AI Never Does Accounting:** Internal inventory runway, balance sheet exposure (€), and stockout projections are computed strictly via pure SQL joins and inventory math.
2. **AI Acts as Operational Researcher, Strategist & Adversarial Critic:** Models handle multi-source taxonomy extraction, operational strategy drafting, and red-team audits.
3. **Transactional Mutation:** Operators don't just read suggestions—they click to execute purchase order reallocations directly against the database, driving exposure to €0.

---

## 🏛️ System Architecture

CrisisSentinel operates on a tier-orchestrated pipeline combining **NVIDIA Nemotron models via Nebius Token Factory**, **Tavily AI Search**, and a deterministic **SQLite ERP Engine**:
```

```
                   ┌─────────────────────────────────────┐
                   │     Live Geopolitical Signal        │
                   │   (e.g., Taiwan Chip Disruption)    │
                   └──────────────────┬──────────────────┘
                                      │
                                      ▼
                   ┌─────────────────────────────────────┐
                   │     Tavily Multi-Query Engine       │
                   │  3-Query Research & Contradiction   │
                   └──────────────────┬──────────────────┘
                                      │ Raw Sources & Citations
                                      ▼
                   ┌─────────────────────────────────────┐
                   │       NVIDIA Nemotron-3-Nano        │
                   │ Structured Fact Extraction (Nebius) │
                   └──────────────────┬──────────────────┘
                                      │ Taxonomy: (Country, Category)
                                      ▼
                   ┌─────────────────────────────────────┐
                   │     Deterministic SQLite Engine     │
                   │  WHERE s.country = ? AND cat = ?    │
                   └──────────────────┬──────────────────┘
                                      │
             ┌────────────────────────┴────────────────────────┐
             ▼                                                 ▼

```

┌───────────────────────────────┐ ┌─────────────────────────────────┐
│ Deterministic What-If │ │ NVIDIA Nemotron-3-Super │
│ Duration × Capacity Slider │ │ Mitigation Brief Generation │
└───────────────────────────────┘ └────────────────┬────────────────┘
│
▼
┌─────────────────────────────────┐
│ Nemotron Super Adversarial Audit│
│ Red-Teams Brief for Bottlenecks│
└────────────────┬────────────────┘
│ (Revise Plan Loop)
▼
┌─────────────────────────────────┐
│ One-Click ERP State Mutation │
│ Reroutes POs in voltauto.db │
└─────────────────────────────────┘

````

---

## 🌟 Key Differentiators & Features

### 1. Multi-Model Tiering via Nebius Token Factory
- **Nemotron-3-Nano (`nvidia/nemotron-3-nano-30b-a3b`):** Fast, low-latency structured extraction using Pydantic JSON mode. It filters web noise, extracts real-world entities, identifies timeline duration, and resolves claim contradictions.
- **Nemotron-3-Super (`nvidia/nemotron-3-super-120b-a12b`):** High-reasoning executive strategist that formulates mitigation protocols, prioritizes bottleneck components, and coordinates buffer logistics.

### 2. Adversarial AI Critic & Single-Turn Revision Loop
- Nemotron-3-Super acts as an independent auditor evaluating the generated plan.
- Checks operational feasibility, identifies single-source bottleneck risks (e.g., over-relying on a single alternate like *EuroSemi GmbH*), and issues a scorecard (`revise • 92/100`).
- Clicking **"Revise Plan"** sends flagged challenges back into a bounded revision loop, synthesizing an audited, dual-sourcing strategy (`VERIFIED • 98/100`).

### 3. Pure SQL Deterministic What-If Simulator
- Pure SQL and inventory math ($Stockout = CurrentStock - (Days \times Consumption)$).
- Interactive duration (1–90 days) and regional capacity offline (0–100%) sliders.
- Displays line-stoppage days with vs. without intervention with instant recalibration.

### 4. Interactive State Mutation & Baseline Reset
- Clicking **"Approve Primary Reroute"** executes `POST /api/mitigation/execute`, writing directly to SQLite (`UPDATE purchase_order SET supplier_id = ?, status = 'rerouted' WHERE id = ?`).
- Recomputes exposure dynamically, dropping the risk metric to **€0,00** and setting remaining exposure to 0 POs.
- Includes a **"↺ Reset DB Baseline"** button to replay the demo idempotently from clean seed data.

### 5. Verifiable Evidence Trail (Tavily Prize Track)
- Multi-query investigation logging queries, depth, and credits.
- Every extracted claim is attributed to clickable source URLs (`S1`, `S2`), ensuring zero unverifiable claims.

---

## 📊 Database Schema (`voltauto.db`)

The internal ERP data architecture models enterprise automotive operations across 5 German manufacturing plants:

| Table | Records | Purpose |
| :--- | :--- | :--- |
| `supplier` | 20 suppliers | Global supply base (Taiwan, Poland, Japan, Germany) categorized by industry |
| `material` | 50 parts | Critical bill of materials (microcontrollers, battery cells, LiDAR modules) |
| `plant` | 5 plants | Assembly facilities: Stuttgart, Berlin, Leipzig, Mannheim, Munich |
| `purchase_order`| 200 orders | Open & delivered POs tracking unit quantities, values (€), and lead times |
| `inventory` | Plant $\times$ Mat | Local factory current stock levels and daily consumption burn rates |
| `alt_supplier_map`| Verified routes | Pre-qualified, validated alternative suppliers for fast rerouting |

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Nebius Token Factory](https://tokenfactory.nebius.com) API Key
- [Tavily Search](https://tavily.com) API Key

---

### Step 1: Clone Repository & Setup Environment
```bash
git clone [https://github.com/viveksawant011/crisis-sentinel.git](https://github.com/viveksawant011/crisis-sentinel.git)
cd crisis-sentinel

# Configure backend environment
cp .env.example backend/.env

````

Edit `backend/.env` with your API credentials:

```env
NEBIUS_API_KEY=your_nebius_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

```

---

### Step 2: Initialize & Launch the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Seed the VoltAuto ERP database
python seed_data.py

# Launch FastAPI orchestrator
uvicorn api:app --reload --port 8000

```

Backend API will be live at `http://localhost:8000` (Swagger docs available at `http://localhost:8000/docs`).

---

### Step 3: Launch Frontend Cockpit

Open a second terminal window:

```bash
cd frontend
npm install
npm run dev

```

Navigate to **`http://localhost:5173`** in your browser.

---

## 🎬 How to Run the Demo Scenarios

1. **Taiwan Semiconductor Fab Disruption (Hero Scenario):**

- Click the **"Taiwan chips"** scenario chip or type `Taiwan semiconductor supply chain disruption 2026`.
- Click **Analyze**. Observe live SSE streaming telemetry across all 5 agent stages.
- Review the metrics: **€4,72 Mio. Value at Risk**, **11 Exposed Open POs**, **3.2d Critical Runway** on Berlin assembly lines.
- Observe the Adversarial Critic panel: Nemotron Super flags single-source dependencies on EuroSemi GmbH (`revise • 92/100`).
- Click **"Revise Plan"**: The strategy rewrites to a dual-sourced mitigation, achieving `VERIFIED • 98/100`.
- Click **"Approve Primary Reroute"**: Executes SQL mutation, dropping Value at Risk to `0 €`.
- Click **"↺ Reset DB Baseline"** to wipe mutations and restore baseline data.

2. **Poland Lithium Battery Strike:**

- Click **"Poland battery"** to test cathode cell supply halts impacting Leipzig & Munich.

3. **Offline Demo Reliability Mode:**

- Toggle **"Demo Reliability Mode"** to test instantly using pre-recorded golden runs in `backend/cache/scenarios/` with zero network dependency.

---

## 🔬 Benchmark & Evaluation Metrics

To prove model extraction accuracy and zero hallucination mathematically, run the automated evaluation suite:

```bash
cd backend
python eval_benchmark.py

```

- **Extraction Accuracy:** 100% ground-truth country & category extraction across multi-scenario tests.
- **Arithmetic Integrity:** 100% of financial figures ground directly in deterministic SQLite calculations.

---

## 💬 Feedback on Nebius Token Factory & NVIDIA Nemotron

As part of the hackathon submission requirements, our operational feedback includes:

- **NVIDIA Nemotron-3-Nano (`nano-30b-a3b`):** Extremely reliable for strict JSON schema compliance. When given Pydantic definitions, it produced zero malformed syntax, making it the ideal low-latency extractor.
- **NVIDIA Nemotron-3-Super (`super-120b-a12b`):** Exceptional capability for adversarial auditing. Unlike typical models that unconditionally praise previous outputs, Nemotron Super successfully identified unstated operational assumptions (e.g., tooling qualification and fab bottlenecks).
- **Nebius Token Factory:** Sub-second time-to-first-token (TTFT) and an OpenAI-compatible interface allowed our team to implement agent streaming (SSE) without complex custom SDK wrappers.

---

## 👥 Team & License

- **Vivek Sawant** — Backend Orchestration, Deterministic Engine, & Nebius/Nemotron Integration
- **Dhruva Makwana** — Enterprise Database Architecture, Seeding, & Benchmark Evaluations
- **Dhruval Patel** — Frontend Cockpit, What-If Simulator UI, & Telemetry Streaming

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

```

---

```
