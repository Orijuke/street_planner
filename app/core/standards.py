"""
Access to the standard street-component width database (app/data/standards.json).

For now, callers should use get_typical_width() everywhere. min/max are stored
for later, once the generator needs to pick a width based on context (e.g. a
narrow plot forcing minimum widths).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

_STANDARDS_PATH = Path(__file__).resolve().parent.parent / "data" / "standards.json"


class UnknownComponentError(Exception):
    """Raised when a requested street component isn't in the standards database."""


def _load_raw() -> Dict:
    with open(_STANDARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_typical_width(component: str) -> float:
    """Return the typical width (in meters) for a street component, e.g. 'bike_lane'."""
    components = _load_raw()["street_components"]
    if component not in components:
        raise UnknownComponentError(
            f"Unknown street component '{component}'. Known: {', '.join(components)}"
        )
    return components[component]["typical"]


def list_components() -> Dict[str, Dict]:
    """Return the full street_components dict (min/typical/max/source per component)."""
    return _load_raw()["street_components"]