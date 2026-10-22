"""
Writes docs/data_dictionary.md from the live voltauto.db, so table structure,
primary keys and row counts always match the database that is actually committed.

Run (repo root, PowerShell), and re-run whenever seed_data.py or the DB changes:
    python backend\\gen_data_dictionary.py
"""
import sqlite3
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "voltauto.db"
OUT_PATH = HERE.parent / "docs" / "data_dictionary.md"

TABLES = [  # (table, purpose) - in dependency order
    ("supplier", "Companies VoltAuto buys from. `country` is the real-world bridge to news events."),
    ("material", "Parts and components VoltAuto purchases, grouped by `category`."),
    ("plant", "VoltAuto's five German production sites."),
    ("purchase_order", "Orders placed with suppliers. Open POs are what a disruption puts at risk."),
    ("inventory", "Stock on hand and daily consumption, per material per plant. Runway = stock / consumption."),
    ("alt_supplier_map", "Pre-approved alternative suppliers per material and primary supplier."),
]


def fmt(v):
    return "NULL" if v is None else str(v)


def main():
    conn = sqlite3.connect(DB_PATH)
    lines = [
        "# VoltAuto Data Dictionary",
        "",
        f"_Generated from `backend/voltauto.db` on {date.today().isoformat()} "
        "by `backend/gen_data_dictionary.py`._",
        "",
        "**This is representative synthetic data, not a live SAP system.** VoltAuto GmbH, its "
        "suppliers, materials and plants are fictional. Only `country` values are real; they are "
        "the only link between real-world news and the database.",
        "",
        "ER diagram: [voltauto_erd_v2.html](voltauto_erd_v2.html)",
        "",
        "## Overview",
        "",
        "| Table | Rows | Primary key | Foreign keys | Purpose |",
        "|---|---:|---|---|---|",
    ]

    details = []
    for table, purpose in TABLES:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        # cid, name, type, notnull, dflt, pk
        pk = [c[1] for c in sorted((c for c in cols if c[5]), key=lambda c: c[5])]
        fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        fk_txt = ", ".join(f"`{f[3]}` → `{f[2]}.{f[4]}`" for f in fks) or "-"
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        lines.append(f"| `{table}` | {n:,} | {', '.join(f'`{k}`' for k in pk)} | {fk_txt} | {purpose} |")

        fk_cols = {f[3] for f in fks}
        rows = ["", f"### `{table}`", "", purpose, "",
                "| Column | Type | Notes |", "|---|---|---|"]
        for _cid, name, ctype, notnull, default, is_pk in cols:
            notes = []
            if is_pk:
                notes.append("PK")
            if name in fk_cols:
                notes.append("FK")
            if notnull and not is_pk:
                notes.append("NOT NULL")
            if default is not None:
                notes.append(f"default {default}")
            rows.append(f"| `{name}` | {ctype} | {', '.join(notes)} |")
        example = conn.execute(f"SELECT * FROM {table} ORDER BY rowid LIMIT 1").fetchone()
        if example:
            names = [c[1] for c in cols]
            rows += ["", "Example row: " + ", ".join(f"`{n}`={fmt(v)}" for n, v in zip(names, example))]
        details.append("\n".join(rows))

    lines += details
    lines += [
        "",
        "## Matching rule used by the pipeline",
        "",
        "A disruption is reduced to `(country, category)`. Affected rows are found with plain SQL "
        "joins on `supplier.country` and `supplier.category`; entity names are never matched against news text.",
        "",
    ]
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
