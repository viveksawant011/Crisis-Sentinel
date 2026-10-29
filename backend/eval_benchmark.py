"""
Automated evaluation benchmark for the Enterprise Crisis Response Agent.

Three stages are measured SEPARATELY, so an error in one stage can never hide
or fake a result in another:

  1. EXTRACTION  run_investigation() -> impacted_country / impacted_category (the production path)
                 PASS only on an EXACT string match, because the SQL join is
                 `supplier.country = ? AND supplier.category = ?`. A value like
                 "Semiconductors" is reported as WARN: right idea, but it would
                 return zero rows unless the pipeline normalises it.
  2. TAVILY      run_investigation() sources -> are they real, valid, credible URLs?
  3. ERP         evaluate_erp_exposure() vs an INDEPENDENT SQL oracle written in
                 this file (open PO count, EUR exposure, inventory runway), plus
                 alternative-supplier coverage for the Strategist.
                 Always fed the scenario's ground-truth country/category, so it
                 is tested in isolation from extraction errors.

Usage (repo root, PowerShell / bash):
    python backend/eval_benchmark.py                   # full run (uses API credits)
    python backend/eval_benchmark.py --offline         # ERP + alt-supplier checks only
    python backend/eval_benchmark.py --scenario B      # one scenario
    python backend/eval_benchmark.py --limit 2         # first 2 cases only
    python backend/eval_benchmark.py --check-urls      # also HTTP-check each source URL

Exit code 1 if any check is FAIL (usable in CI). Results are saved to
backend/eval_results.json. Report exactly what this prints - nothing more.
"""
import argparse
import json
import sqlite3
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from alt_supplier_coverage import coverage_gaps, scenario_targets
from test_scenarios import iter_cases

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "voltauto.db"

# =====================================================================
# ADAPTER  -  Corrected to match tavily_nemotron_probe & engine signatures
# =====================================================================
_CACHED_MODEL_ID = None

def get_active_model():
    global _CACHED_MODEL_ID
    if _CACHED_MODEL_ID is None:
        try:
            from tavily_nemotron_probe import resolve_nemotron_model
            _CACHED_MODEL_ID = resolve_nemotron_model()
        except Exception:
            _CACHED_MODEL_ID = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    return _CACHED_MODEL_ID


_INTEL_CACHE = {}

from dotenv import load_dotenv
load_dotenv()

def call_research(query):
    """Runs the PRODUCTION investigator (3-query Tavily plan + claim extraction) once per query and
    returns its sources. Extraction below reuses the same run, so both stages measure what the app does."""
    from investigator import run_investigation
    _INTEL_CACHE[query] = run_investigation(query, model_id=get_active_model())
    return _INTEL_CACHE[query].sources


def call_analyze(research_output, query):
    return _INTEL_CACHE[query].model_dump()


def call_erp(country, category):
    from engine import evaluate_erp_exposure
    return evaluate_erp_exposure(country, category, db_path=str(DB_PATH))


# Key names to look for in your outputs. First match wins (searched recursively).
EXTRACTION_KEYS = {"country": ["impacted_country"], "category": ["impacted_category"]}
SOURCE_LIST_KEYS = ["results", "sources", "evidence", "articles"]
SOURCE_URL_KEYS = ["url", "link", "source_url"]

# Added 'open_pos_count' to fix UNVERIFIED error
ERP_KEYS = {
    "po_count": ["open_pos_count", "total_pos_affected", "affected_po_count", "po_count", "num_pos", "affected_pos"],
    "exposure_eur": ["total_exposure_eur", "total_exposure", "exposure_eur", "eur_exposure", "exposure"],
    "min_runway_days": ["critical_runway_days", "min_inventory_days", "min_runway_days", "inventory_runway_days",
                        "min_days_inventory", "runway_days"],
}

MIN_SOURCES = 3
MIN_CREDIBLE = 2
CREDIBLE_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "cnbc.com", "bbc.com", "bbc.co.uk",
    "apnews.com", "nikkei.com", "asia.nikkei.com", "scmp.com", "digitimes.com", "trendforce.com",
    "taiwannews.com.tw", "focustaiwan.tw", "japantimes.co.jp", "japantoday.com",
    "supplychaindive.com", "just-auto.com", "autonews.com", "electrive.com", "euronews.com",
    "dw.com", "theguardian.com", "economist.com", "spglobal.com", "mckinsey.com",
    "semiconductors.org", "semi.org", "ec.europa.eu", "iea.org",
]
_MISSING = object()


# ------------------------------------------------------------------ helpers
def to_plain(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return obj.dict()
        except Exception:
            pass
    return obj


def find_key(obj, names):
    """Depth-first search for the first key in `names`. Returns _MISSING if absent."""
    obj = to_plain(obj)
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj[n]
        for v in obj.values():
            hit = find_key(v, names)
            if hit is not _MISSING:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_key(v, names)
            if hit is not _MISSING:
                return hit
    return _MISSING


def top_level_keys(obj):
    obj = to_plain(obj)
    return sorted(obj.keys()) if isinstance(obj, dict) else [type(obj).__name__]


def get_sources(research_output):
    out = to_plain(research_output)
    items = out
    if isinstance(out, dict):
        items = find_key(out, SOURCE_LIST_KEYS)
        items = [] if items is _MISSING else items
    sources = []
    for it in items if isinstance(items, list) else []:
        it = to_plain(it)
        if isinstance(it, str):
            sources.append({"url": it})
        elif isinstance(it, dict):
            url = next((it[k] for k in SOURCE_URL_KEYS if k in it), None)
            sources.append({"url": url, "title": it.get("title")})
    return sources


def valid_url(u):
    if not isinstance(u, str):
        return False
    p = urlparse(u.strip())
    return p.scheme in ("http", "https") and "." in p.netloc


def domain_of(u):
    return urlparse(u).netloc.lower().removeprefix("www.")


def is_credible(u):
    d = domain_of(u)
    return any(d == c or d.endswith("." + c) for c in CREDIBLE_DOMAINS)


def reachable(u, timeout=8):
    try:
        req = Request(u, headers={"User-Agent": "Mozilla/5.0 (eval-benchmark)"})
        with urlopen(req, timeout=timeout) as r:
            return r.status < 400
    except Exception:
        return False


def db_vocab():
    with sqlite3.connect(DB_PATH) as conn:
        return ({r[0] for r in conn.execute("SELECT DISTINCT country FROM supplier")},
                {r[0] for r in conn.execute("SELECT DISTINCT category FROM supplier")})


def sql_oracle(country, category):
    """Independent ground truth, written without touching the engine under test."""
    with sqlite3.connect(DB_PATH) as c:
        n, eur = c.execute("""
            SELECT COUNT(*), COALESCE(SUM(po.value_eur), 0)
            FROM purchase_order po JOIN supplier s ON s.id = po.supplier_id
            WHERE po.status = 'open' AND s.country = ? AND s.category = ?""",
            (country, category)).fetchone()
        runway = c.execute("""
            SELECT MIN(i.current_stock * 1.0 / i.daily_consumption) FROM inventory i
            WHERE EXISTS (SELECT 1 FROM purchase_order po
                          JOIN supplier s ON s.id = po.supplier_id
                          WHERE po.material_id = i.material_id AND po.plant_id = i.plant_id
                            AND po.status = 'open' AND s.country = ? AND s.category = ?)""",
            (country, category)).fetchone()[0]
    return {"po_count": n, "exposure_eur": round(eur, 2),
            "min_runway_days": None if runway is None else round(runway, 1)}


def number_or_len(v):
    if isinstance(v, (list, tuple, set)):
        return len(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ stage 1+2
def run_case(case, vocab, args):
    countries, categories = vocab
    res = {"scenario": case["scenario_id"], "query": case["query"],
           "extraction": {}, "tavily": {}, "error": None}
    try:
        t0 = time.time()
        research_out = call_research(case["query"])
        res["tavily"]["seconds"] = round(time.time() - t0, 1)

        sources = get_sources(research_out)
        urls = [s["url"] for s in sources]
        n_valid = sum(valid_url(u) for u in urls)
        n_cred = sum(valid_url(u) and is_credible(u) for u in urls)
        n_unique = len({u for u in urls if valid_url(u)})
        t = res["tavily"]
        t.update(n_sources=len(sources), n_valid_urls=n_valid, n_unique=n_unique,
                 n_credible=n_cred, domains=sorted({domain_of(u) for u in urls if valid_url(u)}))
        if args.check_urls:
            t["n_reachable"] = sum(reachable(u) for u in urls if valid_url(u))
        if len(sources) == 0 or n_valid < len(sources):
            t["status"] = "FAIL"
            t["detail"] = f"{len(sources)} sources, {n_valid} valid URLs"
        elif len(sources) < MIN_SOURCES or n_cred < MIN_CREDIBLE:
            t["status"] = "WARN"
            t["detail"] = f"{len(sources)} sources, only {n_cred} from the credible-domain list"
        elif args.check_urls and t["n_reachable"] < n_valid:
            t["status"] = "WARN"
            t["detail"] = f"{n_valid - t['n_reachable']} URL(s) unreachable (some sites block bots)"
        else:
            t["status"] = "PASS"
            t["detail"] = f"{len(sources)} sources, {n_cred} credible"

        if args.sleep:
            time.sleep(args.sleep)

        t0 = time.time()
        analysis = call_analyze(research_out, case["query"])
        res["extraction"]["seconds"] = round(time.time() - t0, 1)
        got_c = find_key(analysis, EXTRACTION_KEYS["country"])
        got_k = find_key(analysis, EXTRACTION_KEYS["category"])
        res["extraction"].update(
            country=None if got_c is _MISSING else got_c,
            category=None if got_k is _MISSING else got_k)
        ex = res["extraction"]
        ex["country_status"], ex["country_note"] = judge(
            ex["country"], case["accepted_countries"], countries, "country")
        ex["category_status"], ex["category_note"] = judge(
            ex["category"], [case["expected_category"]], categories, "category")
        ex["strict_country"] = ex["country"] == case["expected_country"]
    except Exception as e:                      # noqa: BLE001 - benchmark must not crash
        res["error"] = f"{type(e).__name__}: {e}"
        res["traceback"] = traceback.format_exc(limit=3)
    return res


def judge(got, accepted, vocab, label):
    if not isinstance(got, str) or not got.strip():
        return "FAIL", f"no {label} extracted"
    if got in accepted:
        return "PASS", ""
    if got.strip() in accepted:
        return "WARN", "extra whitespace - SQL equality would miss it"
    if got.strip().casefold().rstrip("s") in {a.casefold().rstrip("s") for a in accepted}:
        return "WARN", f"'{got}' is close to {accepted} but not exact - SQL equality would return 0 rows"
    note = f"got '{got}', expected {accepted}"
    if got not in vocab:
        note += f"; '{got}' is not a {label} in the database (hallucinated or out of vocabulary)"
    return "FAIL", note


# ------------------------------------------------------------------ stage 3
def run_erp_target(country, category):
    out = {"country": country, "category": category, "checks": {}, "error": None}
    oracle = sql_oracle(country, category)
    out["oracle"] = oracle
    try:
        eng = call_erp(country, category)
    except Exception as e:                      # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
        out["checks"]["runs_without_error"] = ("FAIL", out["error"])
        return out
    out["checks"]["runs_without_error"] = ("PASS", "")

    def compare(name, tolerance):
        raw = find_key(eng, ERP_KEYS[name])
        if raw is _MISSING:
            return "UNVERIFIED", (f"no key from {ERP_KEYS[name]} in engine output "
                                  f"(top-level keys: {top_level_keys(eng)}) - edit ERP_KEYS")
        val = number_or_len(raw)
        if val is None:
            return "UNVERIFIED", f"value {raw!r} is not numeric"
        want = oracle[name]
        if want is None:
            return ("PASS", "") if val in (0, None) else ("FAIL", f"engine {val}, oracle has no rows")
        ok = abs(val - want) <= tolerance
        fmt = (lambda x: f"{x:,.2f}") if name == "exposure_eur" else (lambda x: f"{x:g}")
        return ("PASS", fmt(val)) if ok else ("FAIL" if name != "min_runway_days" else "WARN",
                                              f"engine {fmt(val)} vs SQL oracle {fmt(want)}")

    out["checks"]["open_po_count"] = compare("po_count", 0)
    out["checks"]["eur_exposure"] = compare("exposure_eur", 1.0)
    runway = compare("min_runway_days", 0.1)
    if runway[0] == "WARN":
        runway = ("WARN", runway[1] + " (engine may define runway per-plant vs overall)")
    out["checks"]["inventory_runway"] = runway

    with sqlite3.connect(DB_PATH) as conn:
        gaps = coverage_gaps(conn, country, category)
    out["checks"]["alt_supplier_coverage"] = (
        ("PASS", "") if not gaps else
        ("FAIL", f"{len(gaps)} critical component(s) without an alternative - run alt_supplier_coverage.py --fix"))
    return out


# ------------------------------------------------------------------ reporting
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="skip Tavily + Nemotron stages")
    ap.add_argument("--scenario", help="only this scenario id (A, B or C)")
    ap.add_argument("--limit", type=int, help="max number of query cases")
    ap.add_argument("--check-urls", action="store_true", help="HTTP-check every source URL")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between API calls")
    ap.add_argument("--json", default=str(HERE / "eval_results.json"))
    args = ap.parse_args(argv)

    cases = [c for c in iter_cases() if not args.scenario or c["scenario_id"] == args.scenario.upper()]
    if args.limit:
        cases = cases[:args.limit]
    vocab = db_vocab()
    results = {"cases": [], "erp": []}

    if not args.offline:
        print(f"Running {len(cases)} case(s): Tavily -> Nemotron extraction\n")
        for c in cases:
            r = run_case(c, vocab, args)
            results["cases"].append(r)
            if r["error"]:
                print(f"[{c['scenario_id']}] ERROR  {c['query'][:55]}\n      {r['error']}")
                continue
            ex, t = r["extraction"], r["tavily"]
            print(f"[{c['scenario_id']}] {c['query'][:55]}")
            print(f"      extraction  country={ex['country']!r:<12} {ex['country_status']:<5} "
                  f"category={ex['category']!r:<20} {ex['category_status']}")
            for note in (ex["country_note"], ex["category_note"]):
                if note:
                    print(f"                  ! {note}")
            print(f"      tavily      {t['status']:<5} {t['detail']}")

    print("\nERP stage (engine vs independent SQL oracle, ground-truth inputs)\n")
    targets = {(c, k) for sid, c, k in scenario_targets()
               if not args.scenario or sid == args.scenario.upper()}
    for country, category in sorted(targets):
        r = run_erp_target(country, category)
        results["erp"].append(r)
        o = r["oracle"]
        print(f"{country} / {category}   oracle: {o['po_count']} open POs, "
              f"EUR {o['exposure_eur']:,.0f}, min runway {o['min_runway_days']} d")
        for name, (status, note) in r["checks"].items():
            print(f"      {name:<22}{status:<11}{note}")

    # ---- summary
    ok = [r for r in results["cases"] if not r["error"]]
    n = len(ok)
    def count(stage, key, status):
        return sum(1 for r in ok if r[stage].get(key) == status)
    print("\n" + "=" * 62 + "\nSUMMARY")
    if not args.offline:
        print(f"  Cases run        {len(results['cases'])}  ({len(results['cases']) - n} errored)")
        print(f"  Country exact    {count('extraction', 'country_status', 'PASS')}/{n}"
              f"   (strict expected value: {sum(1 for r in ok if r['extraction'].get('strict_country'))}/{n})")
        print(f"  Category exact   {count('extraction', 'category_status', 'PASS')}/{n}")
        print(f"  Tavily sources   PASS {count('tavily', 'status', 'PASS')}  "
              f"WARN {count('tavily', 'status', 'WARN')}  FAIL {count('tavily', 'status', 'FAIL')}")
    flat = [s for r in results["erp"] for s, _ in r["checks"].values()]
    print(f"  ERP checks       PASS {flat.count('PASS')}  WARN {flat.count('WARN')}  "
          f"FAIL {flat.count('FAIL')}  UNVERIFIED {flat.count('UNVERIFIED')}")

    Path(args.json).write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved {args.json}")

    any_fail = (any(r["error"] for r in results["cases"]) or
                any(r["extraction"].get("country_status") == "FAIL"
                    or r["extraction"].get("category_status") == "FAIL"
                    or r["tavily"].get("status") == "FAIL" for r in ok) or "FAIL" in flat)
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())