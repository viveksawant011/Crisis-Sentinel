"""
Normalizes extracted categories and countries against the actual voltauto.db vocabulary.
Prevents false all-clears from pluralization or casing mismatches.
"""

import sqlite3
from typing import Optional, Set, Tuple

# Static fallbacks matching schema.sql
KNOWN_CATEGORIES = {
    "semiconductor": ["semiconductors", "chips", "microcontrollers", "mcu", "wafers", "fab"],
    "battery component": ["battery", "batteries", "lithium", "cells", "cathodes", "anodes", "battery cell"],
    "sensor": ["sensors", "radar", "lidar", "cameras", "ultrasonic", "proximity sensor"],
}

KNOWN_COUNTRIES = {
    "Taiwan": ["taiwan, r.o.c.", "republic of china", "tw"],
    "Germany": ["deutschland", "de"],
    "Poland": ["polska", "pl"],
    "Japan": ["nippon", "jp"],
}


def get_db_vocabulary(db_path: str = "voltauto.db") -> Tuple[Set[str], Set[str]]:
    """Reads distinct countries and categories directly from the supplier table."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT country FROM supplier")
            db_countries = {row[0] for row in cursor.fetchall() if row[0]}
            cursor.execute("SELECT DISTINCT category FROM supplier")
            db_categories = {row[0] for row in cursor.fetchall() if row[0]}
            return db_countries, db_categories
    except Exception:
        return set(KNOWN_COUNTRIES.keys()), set(KNOWN_CATEGORIES.keys())


def normalize_category(raw_category: Optional[str], db_categories: Optional[Set[str]] = None) -> Optional[str]:
    if not raw_category:
        return None
    cat_clean = raw_category.strip().lower()

    if db_categories:
        for dbc in db_categories:
            if cat_clean == dbc.lower() or cat_clean.rstrip("s") == dbc.lower().rstrip("s"):
                return dbc

    for canonical, aliases in KNOWN_CATEGORIES.items():
        if cat_clean == canonical or cat_clean in aliases:
            return canonical

    return raw_category.strip().lower().rstrip("s")


def normalize_country(raw_country: Optional[str], db_countries: Optional[Set[str]] = None) -> Optional[str]:
    if not raw_country:
        return None
    c_clean = raw_country.strip().lower()

    if db_countries:
        for dbc in db_countries:
            if c_clean == dbc.lower():
                return dbc

    for canonical, aliases in KNOWN_COUNTRIES.items():
        if c_clean == canonical.lower() or c_clean in aliases:
            return canonical

    return raw_country.strip().title()