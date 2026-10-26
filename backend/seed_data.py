"""
Seeds voltauto.db from schema.sql.
Run: python seed_data.py

Order matters: the Taiwan -> TaiwanChip -> MCU-X200 -> PO#10482 -> Stuttgart
chain is inserted FIRST and verified before any bulk data, per the charter.
"""
import sqlite3
import random

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "voltauto.db")
SCHEMA_PATH = str(BASE_DIR / "schema.sql")

random.seed(42)  # reproducible dataset across the team

PLANTS = [
    ("PL_STUTTGART", "Stuttgart Plant", "Germany"),
    ("PL_MUNICH", "Munich Plant", "Germany"),
    ("PL_LEIPZIG", "Leipzig Plant", "Germany"),
    ("PL_MANNHEIM", "Mannheim Plant", "Germany"),
    ("PL_BERLIN", "Berlin Plant", "Germany"),
]

# category, [(country, region)] — one Taiwan entry among 6, per teammate
# feedback, to keep Taiwan exposure a supporting signal, not half the spend
SUPPLIER_POOL = [
    ("semiconductor", "Taiwan", "East Asia"),
    ("semiconductor", "South Korea", "East Asia"),
    ("battery component", "Germany", "Europe"),
    ("battery component", "Poland", "Europe"),
    ("sensor", "Japan", "East Asia"),
    ("sensor", "Germany", "Europe"),
]

# category -> name template (search_terms removed — v2 feature per teammate
# feedback; MVP matching is supplier.country + supplier.category joins only)
MATERIAL_TEMPLATES = {
    "semiconductor": [
        "Microcontroller {n}",
        "Power Module {n}",
        "Sensor Controller {n}",
    ],
    "battery component": [
        "Battery Controller {n}",
        "Cell Module {n}",
    ],
    "sensor": [
        "Proximity Sensor {n}",
        "Radar Unit {n}",
    ],
}
MATERIAL_CATEGORIES = list(MATERIAL_TEMPLATES.keys())
LETTER_CODES = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # skip I/O to avoid 1/0 confusion


def build_schema(conn):
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())


def seed_the_chain(conn):
    """The one relationship chain that must exist, inserted as row 1."""
    conn.execute(
        "INSERT INTO supplier VALUES (?,?,?,?,?)",
        ("SUP001", "TaiwanChip Corp", "Taiwan", "East Asia", "semiconductor"),
    )
    conn.execute(
        "INSERT INTO supplier VALUES (?,?,?,?,?)",
        ("SUP014", "EuroSemi GmbH", "Germany", "Europe", "semiconductor"),
    )
    conn.execute(
        "INSERT INTO material VALUES (?,?,?)",
        ("MCU-X200", "MCU-X200", "semiconductor"),
    )
    conn.executemany("INSERT INTO plant VALUES (?,?,?)", PLANTS)
    conn.execute(
        "INSERT INTO purchase_order VALUES (?,?,?,?,?,?,?,?)",
        ("PO10482", "SUP001", "MCU-X200", "PL_STUTTGART",
         100000, 2400000.0, 18, "open"),
    )
    conn.execute(
        "INSERT INTO inventory VALUES (?,?,?,?)",
        ("MCU-X200", "PL_STUTTGART", 18000, 1650),
    )
    conn.execute(
        "INSERT INTO alt_supplier_map VALUES (?,?,?)",
        ("MCU-X200", "SUP001", "SUP014"),
    )
    conn.commit()


def seed_alt_suppliers(conn, materials, all_suppliers, n_critical=6):
    """Give a handful of other materials an alternative-supplier option too,
    so 'shift to alternative supplier' isn't only ever possible for MCU-X200."""
    by_category = {}
    for mid, cat in materials:
        by_category.setdefault(cat, []).append(mid)

    critical_materials = random.sample(materials, k=min(n_critical, len(materials)))
    for mid, cat in critical_materials:
        candidates = [s for s in all_suppliers if s["category"] == cat]
        if len(candidates) < 2:
            continue
        primary, alt = random.sample(candidates, 2)
        conn.execute(
            "INSERT OR IGNORE INTO alt_supplier_map VALUES (?,?,?)",
            (mid, primary["id"], alt["id"]),
        )
    conn.commit()


def verify_chain(conn):
    """Fail loudly before any bulk seeding if the core chain doesn't join."""
    row = conn.execute("""
        SELECT s.name, m.id, po.id, po.value_eur, pl.name,
               ROUND(i.current_stock * 1.0 / i.daily_consumption, 1) AS runway
        FROM purchase_order po
        JOIN supplier s ON s.id = po.supplier_id
        JOIN material m ON m.id = po.material_id
        JOIN plant pl ON pl.id = po.plant_id
        JOIN inventory i ON i.material_id = m.id AND i.plant_id = pl.id
        WHERE po.id = 'PO10482'
    """).fetchone()
    assert row is not None, "Core traceability chain failed to join"
    print("Chain verified:", row)


def seed_bulk(conn, n_suppliers=20, n_materials=50, n_pos=200,
              taiwan_semi_po_count=10, taiwan_semi_po_range=(50_000, 350_000)):
    """Scale up around the verified chain. IDs starting after the chain's.

    Taiwan-semiconductor open exposure is explicitly capped (not left to
    random chance) so PO10482 stays the dominant, easy-to-explain data
    point in the demo instead of being diluted by a large random slice.
    """
    suppliers, materials = [], []  # suppliers: list of dicts; materials: [(id, category)]

    for i in range(1, n_suppliers):
        cat, country, region = random.choice(SUPPLIER_POOL)
        sid = f"SUP1{i:03d}"  # SUP1xxx range — avoids colliding with SUP001/SUP014
        name = f"{country.replace(' ', '')}Parts {i:03d}"
        suppliers.append({"id": sid, "category": cat, "country": country})
        conn.execute(
            "INSERT INTO supplier VALUES (?,?,?,?,?)",
            (sid, name, country, region, cat),
        )

    for i in range(1, n_materials):
        cat = random.choice(MATERIAL_CATEGORIES)
        name_tpl = random.choice(MATERIAL_TEMPLATES[cat])
        letter = LETTER_CODES[i % len(LETTER_CODES)]
        n_label = f"{letter}{i}"          # unique by construction (i is unique)
        mid = f"MAT-{n_label}"
        name = name_tpl.format(n=n_label)
        materials.append((mid, cat))
        conn.execute(
            "INSERT INTO material VALUES (?,?,?)",
            (mid, name, cat),
        )

    plant_ids = [p[0] for p in PLANTS]
    semi_material_ids = [m for m, c in materials if c == "semiconductor"] + ["MCU-X200"]

    # Taiwan-semiconductor suppliers (chain's SUP001 excluded — its exposure
    # is already fixed at PO10482's €2.4M and shouldn't get MORE bulk POs).
    taiwan_semi_ids = [s["id"] for s in suppliers
                       if s["category"] == "semiconductor" and s["country"] == "Taiwan"]

    # Everyone else — used for the general random PO pool.
    other_supplier_ids = [s["id"] for s in suppliers if s["id"] not in taiwan_semi_ids] + ["SUP014"]
    all_material_ids = [m[0] for m in materials] + ["MCU-X200"]

    pid_counter = 2

    # 1. Explicit, capped Taiwan-semiconductor bulk POs.
    if taiwan_semi_ids:
        for _ in range(taiwan_semi_po_count):
            pid = f"PO{10000 + pid_counter}"
            pid_counter += 1
            conn.execute(
                "INSERT INTO purchase_order VALUES (?,?,?,?,?,?,?,?)",
                (pid, random.choice(taiwan_semi_ids), random.choice(semi_material_ids),
                 random.choice(plant_ids), random.randint(500, 20000),
                 round(random.uniform(*taiwan_semi_po_range), 2),
                 random.randint(5, 45), "open"),
            )

    # 2. Everyone else, drawn from the non-Taiwan-semiconductor pool.
    while pid_counter < n_pos:
        pid = f"PO{10000 + pid_counter}"
        pid_counter += 1
        conn.execute(
            "INSERT INTO purchase_order VALUES (?,?,?,?,?,?,?,?)",
            (pid, random.choice(other_supplier_ids), random.choice(all_material_ids),
             random.choice(plant_ids), random.randint(500, 50000),
             round(random.uniform(20000, 900000), 2),
             random.randint(5, 45), "open"),
        )

    for mid, _cat in materials:
        for plant_id in random.sample(plant_ids, k=random.randint(1, 3)):
            conn.execute(
                "INSERT OR IGNORE INTO inventory VALUES (?,?,?,?)",
                (mid, plant_id, random.randint(500, 20000),
                 random.randint(50, 2000)),
            )

    conn.commit()

    all_suppliers_full = suppliers + [
        {"id": "SUP001", "category": "semiconductor", "country": "Taiwan"},
        {"id": "SUP014", "category": "semiconductor", "country": "Germany"},
    ]
    seed_alt_suppliers(conn, materials, all_suppliers_full)


# Every disruption the demo can raise must have approved alternatives, otherwise "reroute" is impossible
# after a reset. Two options per critical (material, primary supplier) pair makes dual-sourcing real.
SCENARIO_TARGETS = [("Taiwan", "semiconductor"), ("Poland", "battery component"),
                    ("Germany", "battery component"), ("Japan", "sensor")]
ALTS_PER_PAIR = 2


def ensure_scenario_alternatives(conn):
    for country, category in SCENARIO_TARGETS:
        pairs = conn.execute("""
            SELECT DISTINCT po.material_id, po.supplier_id FROM purchase_order po
            JOIN supplier s ON s.id = po.supplier_id
            WHERE po.status = 'open' AND s.country = ? AND s.category = ?
            ORDER BY po.material_id, po.supplier_id""", (country, category)).fetchall()
        for material_id, primary in pairs:
            have = {r[0] for r in conn.execute(
                """SELECT a.alt_supplier_id FROM alt_supplier_map a JOIN supplier s ON s.id = a.alt_supplier_id
                   WHERE a.material_id = ? AND a.primary_supplier_id = ? AND s.country <> ? AND s.category = ?""",
                (material_id, primary, country, category))}
            need = ALTS_PER_PAIR - len(have)
            if need <= 0:
                continue
            cands = [r[0] for r in conn.execute(
                """SELECT s.id FROM supplier s WHERE s.category = ? AND s.country <> ? AND s.id <> ?
                   ORDER BY s.id""", (category, country, primary)) if r[0] not in have]
            if not cands:
                continue
            shippers = {r[0] for r in conn.execute(
                "SELECT DISTINCT supplier_id FROM purchase_order WHERE material_id = ?", (material_id,))}
            preferred = [c for c in cands if c in shippers]
            rest = [c for c in cands if c not in shippers]
            if rest:  # rotate deterministically so volume is not forced onto one supplier
                k = sum(map(ord, material_id)) % len(rest)
                rest = rest[k:] + rest[:k]
            for alt in (preferred + rest)[:need]:
                conn.execute("INSERT OR IGNORE INTO alt_supplier_map VALUES (?,?,?)", (material_id, primary, alt))
    conn.commit()


def ensure_coverage(conn):
    """Make the data internally consistent so the engine's joins are meaningful.
    1) Every (material, plant) that has a PO gets an inventory row, so runway
       can be computed at the plant the PO actually ships to.
    2) Every open PO from a non-European semiconductor supplier gets a valid
       alternative supplier, so 'reroute' is always possible in the demo.
    Runs after all random seeding, so it doesn't change earlier rows."""
    missing = conn.execute("""
        SELECT DISTINCT po.material_id, po.plant_id FROM purchase_order po
        LEFT JOIN inventory i ON i.material_id = po.material_id AND i.plant_id = po.plant_id
        WHERE i.material_id IS NULL
    """).fetchall()
    for material_id, plant_id in sorted(missing):
        daily = random.randint(200, 1500)
        stock = int(daily * random.uniform(4, 30))     # 4-30 days of cover
        conn.execute("INSERT INTO inventory VALUES (?,?,?,?)",
                     (material_id, plant_id, stock, daily))

    ensure_scenario_alternatives(conn)
    conn.commit()


def export_vocabulary(conn):
    """Flat lists for the AI/Data Science teammate's Nemotron prompts."""
    materials = [r[0] for r in conn.execute("SELECT id FROM material")]
    suppliers = [r[0] for r in conn.execute("SELECT name FROM supplier")]
    print(f"Exported {len(materials)} materials, {len(suppliers)} suppliers")
    return {"materials": materials, "suppliers": suppliers}


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    build_schema(conn)
    seed_the_chain(conn)
    verify_chain(conn)          # stop here if the chain is broken
    seed_bulk(conn)
    ensure_coverage(conn)
    export_vocabulary(conn)
    conn.close()
    print(f"Done — {DB_PATH} ready.")