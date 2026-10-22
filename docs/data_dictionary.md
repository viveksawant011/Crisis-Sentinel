# VoltAuto Data Dictionary

_Generated from `backend/voltauto.db` on 2026-10-19 by `backend/gen_data_dictionary.py`._

**This is representative synthetic data, not a live SAP system.** VoltAuto GmbH, its suppliers, materials and plants are fictional. Only `country` values are real; they are the only link between real-world news and the database.

ER diagram: [voltauto_erd_v2.html](voltauto_erd_v2.html)

## Overview

| Table | Rows | Primary key | Foreign keys | Purpose |
|---|---:|---|---|---|
| `supplier` | 21 | `id` | - | Companies VoltAuto buys from. `country` is the real-world bridge to news events. |
| `material` | 50 | `id` | - | Parts and components VoltAuto purchases, grouped by `category`. |
| `plant` | 5 | `id` | - | VoltAuto's five German production sites. |
| `purchase_order` | 199 | `id` | `plant_id` → `plant.id`, `material_id` → `material.id`, `supplier_id` → `supplier.id` | Orders placed with suppliers. Open POs are what a disruption puts at risk. |
| `inventory` | 96 | `material_id`, `plant_id` | `plant_id` → `plant.id`, `material_id` → `material.id` | Stock on hand and daily consumption, per material per plant. Runway = stock / consumption. |
| `alt_supplier_map` | 116 | `material_id`, `primary_supplier_id`, `alt_supplier_id` | `alt_supplier_id` → `supplier.id`, `primary_supplier_id` → `supplier.id`, `material_id` → `material.id` | Pre-approved alternative suppliers per material and primary supplier. |

### `supplier`

Companies VoltAuto buys from. `country` is the real-world bridge to news events.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL |
| `country` | TEXT | NOT NULL |
| `region` | TEXT |  |
| `category` | TEXT | NOT NULL |

Example row: `id`=SUP001, `name`=TaiwanChip Corp, `country`=Taiwan, `region`=East Asia, `category`=semiconductor

### `material`

Parts and components VoltAuto purchases, grouped by `category`.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL |
| `category` | TEXT | NOT NULL |

Example row: `id`=MCU-X200, `name`=MCU-X200, `category`=semiconductor

### `plant`

VoltAuto's five German production sites.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | PK |
| `name` | TEXT | NOT NULL |
| `country` | TEXT | NOT NULL |

Example row: `id`=PL_STUTTGART, `name`=Stuttgart Plant, `country`=Germany

### `purchase_order`

Orders placed with suppliers. Open POs are what a disruption puts at risk.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | PK |
| `supplier_id` | TEXT | FK, NOT NULL |
| `material_id` | TEXT | FK, NOT NULL |
| `plant_id` | TEXT | FK, NOT NULL |
| `quantity` | INTEGER | NOT NULL |
| `value_eur` | REAL | NOT NULL |
| `lead_time_days` | INTEGER | NOT NULL |
| `status` | TEXT | NOT NULL, default 'open' |

Example row: `id`=PO10482, `supplier_id`=SUP001, `material_id`=MCU-X200, `plant_id`=PL_STUTTGART, `quantity`=100000, `value_eur`=2400000.0, `lead_time_days`=18, `status`=open

### `inventory`

Stock on hand and daily consumption, per material per plant. Runway = stock / consumption.

| Column | Type | Notes |
|---|---|---|
| `material_id` | TEXT | PK, FK |
| `plant_id` | TEXT | PK, FK |
| `current_stock` | INTEGER | NOT NULL |
| `daily_consumption` | INTEGER | NOT NULL |

Example row: `material_id`=MCU-X200, `plant_id`=PL_STUTTGART, `current_stock`=18000, `daily_consumption`=1650

### `alt_supplier_map`

Pre-approved alternative suppliers per material and primary supplier.

| Column | Type | Notes |
|---|---|---|
| `material_id` | TEXT | PK, FK |
| `primary_supplier_id` | TEXT | PK, FK |
| `alt_supplier_id` | TEXT | PK, FK |

Example row: `material_id`=MCU-X200, `primary_supplier_id`=SUP001, `alt_supplier_id`=SUP014

## Matching rule used by the pipeline

A disruption is reduced to `(country, category)`. Affected rows are found with plain SQL joins on `supplier.country` and `supplier.category`; entity names are never matched against news text.
