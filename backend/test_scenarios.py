"""
Ground-truth scenario dataset for the Enterprise Crisis Response Agent.

Each scenario = one real-world disruption TYPE, with several Tavily query
phrasings. The expected values are what Nemotron must extract and what the
SQL join (supplier.country + supplier.category) will then use.

Why several phrasings per scenario: one query per scenario would give 3 data
points. Three phrasings give 9, and reveal whether extraction is stable when
the same crisis is worded differently.

Used by:
  eval_benchmark.py          -> end-to-end evaluation runner
  alt_supplier_coverage.py   -> checks/seeds alternative suppliers per scenario
  pytest                     -> sanity tests at the bottom of this file
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "voltauto.db"

SCENARIOS = [
    {
        "id": "A",
        "name": "Taiwan earthquake / TSMC fab shutdown",
        "expected_category": "semiconductor",
        "expected_country": "Taiwan",
        "accepted_countries": ["Taiwan"],
        "queries": [
            "Taiwan earthquake TSMC fab shutdown semiconductor supply",
            "Taiwan chip production halted automotive semiconductor shortage",
            "TSMC fab disruption impact on automotive chip supply",
        ],
    },
    {
        "id": "B",
        "name": "European lithium / battery cell supply shock",
        "expected_category": "battery component",
        "expected_country": "Poland",
        # The scenario brief says "Poland or Germany": both are scored as correct,
        # but eval_benchmark.py also reports how often the strict value matched.
        "accepted_countries": ["Poland", "Germany"],
        "queries": [
            "Europe lithium battery cell supply shortage Poland Germany automotive",
            "Poland battery cell plant production disruption EV supply chain",
            "lithium supply shock European battery manufacturers delays",
        ],
    },
    {
        "id": "C",
        "name": "Japan radar / proximity sensor logistics failure",
        "expected_category": "sensor",
        "expected_country": "Japan",
        "accepted_countries": ["Japan"],
        "queries": [
            "Japan port logistics disruption automotive radar sensor shipments delayed",
            "Japan proximity sensor supply delay automotive logistics failure",
            "Japanese radar sensor exports disrupted automakers",
        ],
    },
]


def iter_cases():
    """Flatten to one dict per (scenario, query) - the unit the benchmark runs."""
    for sc in SCENARIOS:
        for q in sc["queries"]:
            yield {
                "scenario_id": sc["id"],
                "scenario_name": sc["name"],
                "query": q,
                "expected_country": sc["expected_country"],
                "accepted_countries": sc["accepted_countries"],
                "expected_category": sc["expected_category"],
            }


# ----------------------------------------------------------------- pytest
def _db_vocab():
    with sqlite3.connect(DB_PATH) as conn:
        countries = {r[0] for r in conn.execute("SELECT DISTINCT country FROM supplier")}
        categories = {r[0] for r in conn.execute("SELECT DISTINCT category FROM supplier")}
    return countries, categories


def test_scenario_values_exist_in_database():
    """Ground truth must be matchable: every expected value must exist in the DB."""
    countries, categories = _db_vocab()
    for sc in SCENARIOS:
        assert sc["expected_category"] in categories, sc["id"]
        assert sc["expected_country"] in sc["accepted_countries"], sc["id"]
        for c in sc["accepted_countries"]:
            assert c in countries, f"{sc['id']}: {c} has no supplier in the database"


def test_each_scenario_has_distinct_queries():
    for sc in SCENARIOS:
        assert len(sc["queries"]) == len(set(sc["queries"])) >= 2, sc["id"]
