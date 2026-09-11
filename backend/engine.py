"""
Deterministic ERP Engine for CrisisSentinel.
Executes pure SQL joins against voltauto.db based on external crisis indicators.
"""

import sqlite3
from typing import Dict, Any, List

DB_PATH = "voltauto.db"

def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def evaluate_erp_exposure(country: str, category: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Matches external disruption factors against internal VoltAuto ERP records."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Fetch Open POs matching the country & category
    po_query = """
        SELECT 
            s.name AS supplier_name,
            s.country AS supplier_country,
            po.id AS po_id,
            po.material_id,
            po.quantity,
            po.value_eur,
            po.lead_time_days,
            pl.name AS plant_name
        FROM purchase_order po
        JOIN supplier s ON s.id = po.supplier_id
        JOIN plant pl ON pl.id = po.plant_id
        WHERE po.status = 'open'
          AND LOWER(s.country) = LOWER(?)
          AND LOWER(s.category) = LOWER(?)
    """
    cursor.execute(po_query, (country, category))
    open_pos = [dict(row) for row in cursor.fetchall()]

    # Graceful exit if no records match
    if not open_pos:
        conn.close()
        return {
            "matched": False,
            "impacted_country": country,
            "impacted_category": category,
            "total_exposure_eur": 0.0,
            "open_pos_count": 0,
            "critical_runway_days": None,
            "message": f"Zero open purchase orders exposed to {category} operations in {country}."
        }

    total_exposure = sum(po["value_eur"] for po in open_pos)
    affected_materials = list(set(po["material_id"] for po in open_pos))
    placeholders = ",".join("?" for _ in affected_materials)

    # 2. Inventory Runway: Current Stock / Daily Consumption
    inv_query = f"""
        SELECT 
            i.material_id,
            pl.name AS plant_name,
            i.current_stock,
            i.daily_consumption,
            ROUND(CAST(i.current_stock AS FLOAT) / i.daily_consumption, 1) AS runway_days
        FROM inventory i
        JOIN plant pl ON pl.id = i.plant_id
        WHERE i.material_id IN ({placeholders})
    """
    cursor.execute(inv_query, affected_materials)
    runway_records = [dict(row) for row in cursor.fetchall()]

    # 3. Discover Alternative Suppliers for Mitigation Routing
    alt_query = f"""
        SELECT 
            asm.material_id,
            s_orig.name AS primary_supplier,
            s_alt.id AS alt_supplier_id,
            s_alt.name AS alt_supplier_name,
            s_alt.country AS alt_supplier_country
        FROM alt_supplier_map asm
        JOIN supplier s_orig ON s_orig.id = asm.primary_supplier_id
        JOIN supplier s_alt ON s_alt.id = asm.alt_supplier_id
        WHERE asm.material_id IN ({placeholders})
    """
    cursor.execute(alt_query, affected_materials)
    alternative_options = [dict(row) for row in cursor.fetchall()]

    conn.close()

    min_runway = min((r["runway_days"] for r in runway_records), default=0.0)

    return {
        "matched": True,
        "impacted_country": country,
        "impacted_category": category,
        "total_exposure_eur": total_exposure,
        "open_pos_count": len(open_pos),
        "critical_runway_days": min_runway,
        "affected_open_pos": open_pos,
        "inventory_runways": runway_records,
        "mitigation_alternatives": alternative_options,
    }