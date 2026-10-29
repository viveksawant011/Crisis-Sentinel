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

## How it works

1. **Search the web** for the event (Tavily).
2. **Pull out the key facts** and which country and product category are affected (Nemotron Nano).
3. **Check for conflicting reports.** If sources disagree, search again to settle it.
4. **Look up the company's orders** with plain SQL: money at risk, which orders are affected, how many days of stock are left, and which backup suppliers are approved.
5. **Write a response plan** with up to 3 actions, each tied to a real order (Nemotron Super).
6. **Have a critic double-check it.** Every number is re-checked against the database, and the critic raises objections to the plan.
7. **A human approves.** Approved reroutes are saved to the database.

![How CrisisSentinel works](docs/architecture.png)

## Why you can trust the numbers

- Money, days of stock and order values always come from SQL, never from the AI.
- The AI cannot change which plant or part an action refers to. That comes from the order record.
- If the AI suggests a supplier that is not approved for that order, the suggestion is dropped.
- If a step fails, the app says so on screen. It does not quietly show made-up results.
- Every claim links back to the web page it came from.

## How we used NVIDIA, Nebius and Tavily

**NVIDIA Nemotron.** We use two sizes. Nano does the high-volume work (reading sources, judging conflicts). Super does the harder thinking (the plan, the critic, revisions). The app shows which model produced each step.

**Nebius Token Factory.** All model calls go through its OpenAI-compatible API. We look up model IDs at runtime, because their capitalization differs between models.

**Tavily.** Handles all web research: three planned searches first, then extra searches when sources disagree (6 at most per scan).

## Run it yourself

You need Python 3.10+, Node 18+, a Nebius Token Factory key and a Tavily key.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env                               # add NEBIUS_API_KEY and TAVILY_API_KEY
python seed_data.py                                   # creates the sample database
uvicorn api:app --port 8000

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

- Vivek Sawant: backend, calculation engine, Nebius and Nemotron integration
- Dhruva Makwana: database design, sample data, tests
- Dhruval Makwana: frontend

## License

MIT. See [LICENSE](LICENSE).
