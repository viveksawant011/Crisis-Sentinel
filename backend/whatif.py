"""
Deterministic What-If Simulation Engine for CrisisSentinel.
Simulates capacity disruptions, stockout timelines, and reroute benefits using pure SQL/math.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    country: str
    category: str
    disruption_days: int = Field(default=28, ge=1, le=90)
    capacity_offline_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    apply_reroute: bool = True
    alt_lead_time_override: Optional[int] = None


def simulate_whatif(
    country: str,
    category: str,
    disruption_days: int = 28,
    capacity_offline_pct: float = 100.0,
    apply_reroute: bool = True,
    alt_lead_time_override: Optional[int] = None,
    db_path: str = "voltauto.db"
) -> Dict[str, Any]:
    """Pure deterministic simulation of inventory depletion and line stoppage."""
    f = max(0.0, min(1.0, capacity_offline_pct / 100.0))
    D = float(disruption_days)

    query = """
    SELECT 
        po.id AS po_id,
        po.material_id,
        m.name AS material_name,
        po.plant_id,
        p.name AS plant_name,
        po.supplier_id,
        s.name AS supplier_name,
        po.quantity,
        po.value_eur,
        po.lead_time_days,
        inv.current_stock,
        inv.daily_consumption,
        asm.alt_supplier_id
    FROM purchase_order po
    JOIN supplier s ON po.supplier_id = s.id
    JOIN material m ON po.material_id = m.id
    JOIN plant p ON po.plant_id = p.id
    LEFT JOIN inventory inv ON (po.material_id = inv.material_id AND po.plant_id = inv.plant_id)
    LEFT JOIN alt_supplier_map asm ON (po.material_id = asm.material_id AND po.supplier_id = asm.primary_supplier_id)
    WHERE po.status = 'open'
      AND LOWER(s.country) = LOWER(?)
      AND LOWER(s.category) = LOWER(?)
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, (country, category)).fetchall()

    po_results = []
    pos_without_inventory = []
    plant_stats: Dict[str, Dict[str, Any]] = {}

    total_shortfall_base = 0.0
    total_shortfall_rerouted = 0.0
    total_val_risk_base = 0.0
    total_val_risk_rerouted = 0.0

    for r in rows:
        po_id = r["po_id"]
        qty = float(r["quantity"]) if r["quantity"] else 0.0
        val = float(r["value_eur"]) if r["value_eur"] else 0.0
        unit_price = val / qty if qty > 0 else 0.0
        lead_time = float(alt_lead_time_override or r["lead_time_days"] or 14.0)

        curr_stock = r["current_stock"]
        daily_cons = r["daily_consumption"]

        if curr_stock is None or daily_cons is None or daily_cons <= 0:
            pos_without_inventory.append(po_id)
            continue

        stock = float(curr_stock)
        daily = float(daily_cons)
        depletion = f * daily

        # 1. Baseline (No action)
        if depletion > 0:
            stockout_day = round(stock / depletion, 1)
            shortfall_units_base = max(0.0, (depletion * D) - stock)
            stoppage_days_base = max(0.0, D - stockout_day)
        else:
            stockout_day = 999.0
            shortfall_units_base = 0.0
            stoppage_days_base = 0.0

        val_at_risk_base = shortfall_units_base * unit_price

        # 2. With Reroute
        has_alt = bool(r["alt_supplier_id"])
        if has_alt:
            effective_D = min(D, lead_time)
            if depletion > 0:
                shortfall_units_reroute = max(0.0, (depletion * effective_D) - stock)
                stoppage_days_reroute = max(0.0, effective_D - stockout_day)
            else:
                shortfall_units_reroute = 0.0
                stoppage_days_reroute = 0.0
        else:
            shortfall_units_reroute = shortfall_units_base
            stoppage_days_reroute = stoppage_days_base

        val_at_risk_reroute = shortfall_units_reroute * unit_price

        # Accumulate
        total_shortfall_base += shortfall_units_base
        total_shortfall_rerouted += shortfall_units_reroute
        total_val_risk_base += val_at_risk_base
        total_val_risk_rerouted += val_at_risk_reroute

        p_name = r["plant_name"]
        if p_name not in plant_stats:
            plant_stats[p_name] = {
                "plant_name": p_name,
                "stoppage_days_baseline": 0.0,
                "stoppage_days_with_reroute": 0.0,
                "value_at_risk_baseline": 0.0,
                "value_at_risk_with_reroute": 0.0,
            }
        plant_stats[p_name]["stoppage_days_baseline"] = max(
            plant_stats[p_name]["stoppage_days_baseline"], stoppage_days_base
        )
        plant_stats[p_name]["stoppage_days_with_reroute"] = max(
            plant_stats[p_name]["stoppage_days_with_reroute"], stoppage_days_reroute
        )
        plant_stats[p_name]["value_at_risk_baseline"] += val_at_risk_base
        plant_stats[p_name]["value_at_risk_with_reroute"] += val_at_risk_reroute

        po_results.append({
            "po_id": po_id,
            "material_id": r["material_id"],
            "material_name": r["material_name"],
            "plant_name": p_name,
            "has_alternative": has_alt,
            "stockout_day": stockout_day if stockout_day < 999.0 else None,
            "baseline": {
                "stoppage_days": round(stoppage_days_base, 1),
                "shortfall_units": int(round(shortfall_units_base)),
                "value_at_risk_eur": round(val_at_risk_base, 2)
            },
            "with_reroute": {
                "stoppage_days": round(stoppage_days_reroute, 1),
                "shortfall_units": int(round(shortfall_units_reroute)),
                "value_at_risk_eur": round(val_at_risk_reroute, 2)
            }
        })

    plants_at_risk_base = sum(1 for p in plant_stats.values() if p["stoppage_days_baseline"] > 0)
    plants_at_risk_reroute = sum(1 for p in plant_stats.values() if p["stoppage_days_with_reroute"] > 0)
    max_stoppage_base = max([p["stoppage_days_baseline"] for p in plant_stats.values()], default=0.0)
    max_stoppage_reroute = max([p["stoppage_days_with_reroute"] for p in plant_stats.values()], default=0.0)

    return {
        "inputs": {
            "country": country,
            "category": category,
            "disruption_days": int(D),
            "capacity_offline_pct": capacity_offline_pct,
            "apply_reroute": apply_reroute
        },
        "totals": {
            "baseline": {
                "value_at_risk_eur": round(total_val_risk_base, 2),
                "units_short": int(round(total_shortfall_base)),
                "plants_at_risk": plants_at_risk_base,
                "max_stoppage_days": round(max_stoppage_base, 1),
            },
            "with_reroute": {
                "value_at_risk_eur": round(total_val_risk_rerouted, 2),
                "units_short": int(round(total_shortfall_rerouted)),
                "plants_at_risk": plants_at_risk_reroute,
                "max_stoppage_days": round(max_stoppage_reroute, 1),
            },
            "delta": {
                "avoided_value_at_risk_eur": round(total_val_risk_base - total_val_risk_rerouted, 2),
                "stoppage_reduction_days": round(max_stoppage_base - max_stoppage_reroute, 1),
                "units_saved": int(round(total_shortfall_base - total_shortfall_rerouted))
            }
        },
        "plants": list(plant_stats.values()),
        "pos": po_results,
        "pos_without_inventory_record": pos_without_inventory,
        "assumptions": [
            "Uniform capacity degradation across all regional suppliers",
            "Alternative supplier lead-time acts as ramp-up ceiling for rerouted POs",
            "Linear inventory depletion without demand reduction adjustments"
        ]
    }