"""
Maps extracted country and category text onto the real voltauto.db vocabulary.

Strict by design: the result is ALWAYS a value that exists in the database, or None.
Unrecognised, ambiguous ('Poland and Germany') or placeholder text ('semiconductor | sensor | null')
returns None, so a bad model answer becomes an honest "event does not map to our supplier base"
instead of a SQL query on garbage.
"""

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

KNOWN_CATEGORIES: Dict[str, List[str]] = {
    "semiconductor": ["chips", "chip", "microcontroller", "microcontrollers", "mcu", "wafer", "wafers", "fab", "fabs", "foundry", "semiconductors"],
    "battery component": ["battery", "batteries", "lithium", "cell", "cells", "cathode", "cathodes", "anode", "anodes", "battery cell", "battery cells"],
    "sensor": ["sensors", "radar", "lidar", "camera", "cameras", "ultrasonic", "proximity sensor"],
}

KNOWN_COUNTRIES: Dict[str, List[str]] = {
    "Taiwan": ["taiwan, r.o.c.", "republic of china", "roc", "tw"],
    "Germany": ["deutschland", "de"],
    "Poland": ["polska", "pl"],
    "Japan": ["nippon", "jp"],
    "South Korea": ["korea", "republic of korea", "rok", "kr"],
}

_EMPTY = {"", "null", "none", "n/a", "na", "unknown", "not specified", "unspecified", "nil", "-"}


def get_db_vocabulary(db_path: str = str(Path(__file__).resolve().parent / "voltauto.db")) -> Tuple[Set[str], Set[str]]:
    """Reads distinct countries and categories directly from the supplier table."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT country FROM supplier")
            countries = {row[0] for row in cur.fetchall() if row[0]}
            cur.execute("SELECT DISTINCT category FROM supplier")
            categories = {row[0] for row in cur.fetchall() if row[0]}
            if countries and categories:
                return countries, categories
    except Exception:
        pass
    return set(KNOWN_COUNTRIES), set(KNOWN_CATEGORIES)


def _resolve(raw: Optional[str], vocabulary: Set[str], aliases: Dict[str, List[str]]) -> Optional[str]:
    """Return the single vocabulary entry the text refers to, else None."""
    if not raw or not isinstance(raw, str):
        return None
    clean = re.sub(r"\s+", " ", raw.strip().lower())
    if clean in _EMPTY:
        return None

    found: Set[str] = set()
    for canonical in vocabulary:
        names = [canonical.lower()] + [a.lower() for a in aliases.get(canonical, [])]
        for name in names:
            if len(name) <= 3:                       # short codes ('de', 'pl'): exact match only
                hit = clean == name
            else:                                    # whole word/phrase, tolerating a plural 's'
                hit = re.search(rf"(?<![a-z]){re.escape(name)}s?(?![a-z])", clean) is not None
            if hit:
                found.add(canonical)
                break
    return next(iter(found)) if len(found) == 1 else None


def normalize_category(raw_category: Optional[str], db_categories: Optional[Set[str]] = None) -> Optional[str]:
    return _resolve(raw_category, db_categories or set(KNOWN_CATEGORIES), KNOWN_CATEGORIES)


def normalize_country(raw_country: Optional[str], db_countries: Optional[Set[str]] = None) -> Optional[str]:
    return _resolve(raw_country, db_countries or set(KNOWN_COUNTRIES), KNOWN_COUNTRIES)