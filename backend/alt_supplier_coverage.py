"""
Alternative-supplier coverage for every scenario in test_scenarios.py.

A "critical component" = a (material, primary supplier) pair that has an OPEN
purchase order with a supplier in the disrupted country + category.
It is "covered" when alt_supplier_map holds at least one alternative that is
  * a different supplier,
  * in a DIFFERENT country than the disruption (otherwise it is hit too),
  * in the SAME category (a sensor supplier cannot replace a chip).

Usage (from the repo root, PowerShell):
    python backend\\alt_supplier_coverage.py          # report only, exit 1 if gaps
    python backend\\alt_supplier_coverage.py --fix    # seed missing mappings, re-check

Idempotent: INSERT OR IGNORE, deterministic ordering, safe to run repeatedly.
To make it permanent, call seed_all_scenarios(conn) at the end of
seed_data.py's main() so a rebuilt database is always covered.
"""
import sqlite3
import sys
from pathlib import Path

from test_scenarios import SCENARIOS

DB_PATH = Path(__file__).parent / "voltauto.db"
ALTS_PER_PAIR = 2


def scenario_targets():
    """Every (country, category) a scenario can resolve to, with its label."""
    seen = set()
    for sc in SCENARIOS:
        for country in sc["accepted_countries"]:
            key = (country, sc["expected_category"])
            if key not in seen:
                seen.add(key)
                yield sc["id"], country, sc["expected_category"]


def critical_pairs(conn, country, category):
    return conn.execute("""
        SELECT DISTINCT po.material_id, po.supplier_id
        FROM purchase_order po JOIN supplier s ON s.id = po.supplier_id
        WHERE po.status = 'open' AND s.country = ? AND s.category = ?
        ORDER BY po.material_id, po.supplier_id""", (country, category)).fetchall()


def _valid_alt_count(conn, material, primary, country, category):
    return conn.execute("""
        SELECT COUNT(*) FROM alt_supplier_map a
        JOIN supplier als ON als.id = a.alt_supplier_id
        WHERE a.material_id = ? AND a.primary_supplier_id = ?
          AND als.country <> ? AND als.category = ?""",
        (material, primary, country, category)).fetchone()[0]


def coverage_gaps(conn, country, category):
    return [(m, p) for m, p in critical_pairs(conn, country, category)
            if _valid_alt_count(conn, m, p, country, category) == 0]


def _candidates(conn, material, primary, country, category):
    """Eligible alternatives, best first: suppliers that already ship this
    material, then everyone else in the category outside the disrupted country."""
    return [r[0] for r in conn.execute("""
        SELECT s.id FROM supplier s
        WHERE s.category = ? AND s.country <> ? AND s.id <> ?
        ORDER BY (SELECT COUNT(*) FROM purchase_order po
                  WHERE po.supplier_id = s.id AND po.material_id = ?) DESC, s.id""",
        (category, country, primary, material)).fetchall()]


def seed_missing(conn, country, category):
    """Insert alternatives for every gap. Returns (rows_added, unfixable_pairs)."""
    added, unfixable = 0, []
    for material, primary in coverage_gaps(conn, country, category):
        cands = _candidates(conn, material, primary, country, category)[:ALTS_PER_PAIR]
        if not cands:
            unfixable.append((material, primary))
            continue
        for alt in cands:
            cur = conn.execute("INSERT OR IGNORE INTO alt_supplier_map VALUES (?,?,?)",
                               (material, primary, alt))
            added += cur.rowcount
    conn.commit()
    return added, unfixable


def seed_all_scenarios(conn):
    """Call this from seed_data.py so a rebuilt DB is always scenario-ready."""
    total = 0
    for _sid, country, category in scenario_targets():
        added, _ = seed_missing(conn, country, category)
        total += added
    return total


def report(conn):
    """Print coverage per scenario target. Returns the total number of gaps."""
    total_gaps = 0
    print(f"{'Scen':<5}{'Country':<10}{'Category':<20}{'Critical pairs':>15}{'Gaps':>7}")
    for sid, country, category in scenario_targets():
        pairs = critical_pairs(conn, country, category)
        gaps = coverage_gaps(conn, country, category)
        total_gaps += len(gaps)
        print(f"{sid:<5}{country:<10}{category:<20}{len(pairs):>15}{len(gaps):>7}")
        for m, p in gaps[:5]:
            print(f"        gap: {m} (primary {p}) has no valid alternative")
    return total_gaps


def main(argv):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    print("== Before ==")
    gaps = report(conn)
    if "--fix" in argv and gaps:
        total_added, unfixable = 0, []
        for _sid, country, category in scenario_targets():
            added, unf = seed_missing(conn, country, category)
            total_added += added
            unfixable += unf
        print(f"\nSeeded {total_added} alt_supplier_map rows.")
        if unfixable:
            print("Unfixable (no eligible supplier exists):", unfixable)
        print("\n== After ==")
        gaps = report(conn)
    conn.close()
    print("\nRESULT:", "all critical components covered" if gaps == 0
          else f"{gaps} uncovered component(s)")
    return 0 if gaps == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
