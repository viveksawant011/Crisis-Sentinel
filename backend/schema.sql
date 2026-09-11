-- VoltAuto GmbH synthetic enterprise database
-- Enterprise Crisis Response Agent — Week 1 schema

PRAGMA foreign_keys = ON;

CREATE TABLE supplier (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL,
    region      TEXT,
    category    TEXT NOT NULL          -- e.g. 'semiconductor', 'battery component'
);

CREATE TABLE material (
    id            TEXT PRIMARY KEY,     -- e.g. 'MCU-X200' — used as the natural key
    name          TEXT NOT NULL,
    category      TEXT NOT NULL         -- matched against, alongside supplier.country
    -- search_terms intentionally omitted for MVP — v2 feature, per team decision.
    -- MVP matching is: supplier.country + supplier.category, via standard joins.
);

CREATE TABLE plant (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL
);

CREATE TABLE purchase_order (
    id                TEXT PRIMARY KEY,
    supplier_id       TEXT NOT NULL REFERENCES supplier(id),
    material_id       TEXT NOT NULL REFERENCES material(id),
    plant_id          TEXT NOT NULL REFERENCES plant(id),
    quantity          INTEGER NOT NULL,
    value_eur         REAL NOT NULL,
    lead_time_days    INTEGER NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open'   -- 'open' | 'fulfilled'
);

CREATE TABLE inventory (
    material_id         TEXT NOT NULL REFERENCES material(id),
    plant_id            TEXT NOT NULL REFERENCES plant(id),
    current_stock       INTEGER NOT NULL,
    daily_consumption   INTEGER NOT NULL,
    PRIMARY KEY (material_id, plant_id)
);

CREATE TABLE alt_supplier_map (
    material_id            TEXT NOT NULL REFERENCES material(id),
    primary_supplier_id    TEXT NOT NULL REFERENCES supplier(id),
    alt_supplier_id        TEXT NOT NULL REFERENCES supplier(id),
    PRIMARY KEY (material_id, primary_supplier_id, alt_supplier_id)
);

-- Lookup columns hit on every disruption query
CREATE INDEX idx_po_material ON purchase_order(material_id);
CREATE INDEX idx_po_supplier ON purchase_order(supplier_id);
CREATE INDEX idx_po_status   ON purchase_order(status);
CREATE INDEX idx_supplier_country ON supplier(country);
