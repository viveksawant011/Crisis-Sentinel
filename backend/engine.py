"""
Deterministic ERP Engine for CrisisSentinel.
Pure SQL + Python. No AI in this file.

Fixes vs the previous version:
  * Runway is computed at the plant each PO ships to (material + plant join),
    not across every plant that happens to stock the material.
  * Alternatives are matched per PO: (material, that PO's supplier).
  * POs with no inventory record are reported, not silently ignored.
  * DB path is absolute, so the API works from any working directory.
  * reset_demo_state() rebuilds the database from seed_data.py.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "voltauto.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def evaluate_erp_exposure(country: str, category: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Match an external disruption (country + category) against open POs."""
    conn = get_db_connection(db_path)

    rows = conn.execute("""
        SELECT
            po.id              AS po_id,
            po.material_id,
            m.name             AS material_name,
            po.quantity,
            po.value_eur,
            po.lead_time_days,
            po.supplier_id,
            s.name             AS supplier_name,
            s.country          AS supplier_country,
            po.plant_id,
            pl.name            AS plant_name,
            i.current_stock,
            i.daily_consumption,
            CASE WHEN i.daily_consumption > 0
                 THEN ROUND(CAST(i.current_stock AS FLOAT) / i.daily_consumption, 1)
            END                AS runway_days
        FROM purchase_order po
        JOIN supplier s  ON s.id  = po.supplier_id
        JOIN material m  ON m.id  = po.material_id
        JOIN plant pl    ON pl.id = po.plant_id
        LEFT JOIN inventory i
               ON i.material_id = po.material_id AND i.plant_id = po.plant_id
        WHERE po.status = 'open'
          AND LOWER(s.country)  = LOWER(?)
          AND LOWER(s.category) = LOWER(?)
        ORDER BY po.value_eur DESC
    """, (country, category)).fetchall()
    open_pos = [dict(r) for r in rows]

    if not open_pos:
        conn.close()
        return {
            "matched": False,
            "impacted_country": country,
            "impacted_category": category,
            "total_exposure_eur": 0.0,
            "open_pos_count": 0,
            "critical_runway_days": None,
            "message": f"Zero open purchase orders exposed to {category} operations in {country}.",
        }

    # Alternatives, matched per (material, this PO's supplier)
    alt_rows = conn.execute("""
        SELECT DISTINCT
            po.id            AS po_id,
            asm.material_id,
            s_orig.name      AS primary_supplier,
            s_alt.id         AS alt_supplier_id,
            s_alt.name       AS alt_supplier_name,
            s_alt.country    AS alt_supplier_country
        FROM purchase_order po
        JOIN supplier s ON s.id = po.supplier_id
        JOIN alt_supplier_map asm
              ON asm.material_id = po.material_id
             AND asm.primary_supplier_id = po.supplier_id
        JOIN supplier s_orig ON s_orig.id = asm.primary_supplier_id
        JOIN supplier s_alt  ON s_alt.id  = asm.alt_supplier_id
        WHERE po.status = 'open'
          AND LOWER(s.country)  = LOWER(?)
          AND LOWER(s.category) = LOWER(?)
    """, (country, category)).fetchall()
    alternatives = [dict(r) for r in alt_rows]
    conn.close()

    alt_po_ids = {a["po_id"] for a in alternatives}
    for po in open_pos:
        po["has_alternative"] = po["po_id"] in alt_po_ids

    # One runway record per (material, plant) that is actually exposed
    seen, runways = set(), []
    for po in open_pos:
        key = (po["material_id"], po["plant_id"])
        if key in seen or po["runway_days"] is None:
            continue
        seen.add(key)
        runways.append({
            "material_id": po["material_id"],
            "material_name": po["material_name"],
            "plant_name": po["plant_name"],
            "current_stock": po["current_stock"],
            "daily_consumption": po["daily_consumption"],
            "runway_days": po["runway_days"],
        })
    runways.sort(key=lambda r: r["runway_days"])

    no_inventory = [p["po_id"] for p in open_pos if p["runway_days"] is None]
    critical = runways[0] if runways else None

    return {
        "matched": True,
        "impacted_country": country,
        "impacted_category": category,
        "total_exposure_eur": round(sum(p["value_eur"] for p in open_pos), 2),
        "open_pos_count": len(open_pos),
        "affected_suppliers": sorted({p["supplier_name"] for p in open_pos}),
        "affected_plants": sorted({p["plant_name"] for p in open_pos}),
        "critical_runway_days": critical["runway_days"] if critical else None,
        "critical_runway_detail": critical,
        "affected_open_pos": open_pos,
        "inventory_runways": runways,
        "pos_without_inventory_record": no_inventory,
        "mitigation_alternatives": alternatives,
        "reroutable_value_eur": round(
            sum(p["value_eur"] for p in open_pos if p["has_alternative"]), 2
        ),
    }


def apply_reroute_mitigation(po_id: str, new_supplier_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Execute an approved reroute. Validates against alt_supplier_map first."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM purchase_order WHERE id = ?", (po_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"Purchase Order '{po_id}' not found."}

        po = dict(row)
        if po["status"] == "rerouted":
            return {"success": False,
                    "error": f"PO {po_id} has already been rerouted to {po['supplier_id']}."}
        if po["status"] != "open":
            return {"success": False, "error": f"PO {po_id} is '{po['status']}', not open."}

        valid = conn.execute("""
            SELECT 1 FROM alt_supplier_map
            WHERE material_id = ? AND primary_supplier_id = ? AND alt_supplier_id = ?
        """, (po["material_id"], po["supplier_id"], new_supplier_id)).fetchone()
        if not valid:
            return {"success": False,
                    "error": f"Supplier {new_supplier_id} is not an authorized alternative "
                             f"for {po['material_id']} from {po['supplier_id']}."}

        conn.execute("UPDATE purchase_order SET supplier_id = ?, status = 'rerouted' WHERE id = ?",
                     (new_supplier_id, po_id))
        conn.commit()
        return {"success": True, "po_id": po_id, "material_id": po["material_id"],
                "previous_supplier": po["supplier_id"], "new_supplier": new_supplier_id,
                "status": "rerouted"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Database transaction failed: {e}"}
    finally:
        conn.close()


def apply_batch_reroute_mitigation(po_ids: list, alt_supplier_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Reroutes a list of exposed purchase orders to an approved alternative supplier,
    updating status to 'rerouted' in the SQLite database.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    
    updated_count = 0
    try:
        for po_id in po_ids:
            cur.execute("""
                UPDATE purchase_order 
                SET supplier_id = ?, status = 'rerouted'
                WHERE id = ?
            """, (alt_supplier_id, str(po_id)))
            updated_count += cur.rowcount
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return {"status": "ERROR", "error": str(exc), "rerouted_pos_count": 0}
    finally:
        conn.close()

    return {
        "status": "SUCCESS",
        "rerouted_pos_count": updated_count,
        "new_supplier_id": alt_supplier_id,
        "message": f"Successfully rerouted {updated_count} purchase orders to {alt_supplier_id}."
    }

def reset_demo_state() -> Dict[str, Any]:
    """Rebuild voltauto.db from seed_data.py so the demo can be replayed."""
    db = Path(DB_PATH)
    if db.exists():
        db.unlink()
    result = subprocess.run(
        [sys.executable, "seed_data.py"], cwd=BASE_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr[-500:]}
    return {"success": True, "message": "Demo database reset to initial state."}