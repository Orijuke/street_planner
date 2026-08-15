"""
Access to the standards database (app/data/standards.json).

Two kinds of entries:
  * road_types           -- per-category car_lane/sidewalk widths, design speed,
                             lane count, and which elements are relevant on that road.
  * street_components    -- widths for elements that aren't (yet) split by road
                             category: bike_lane, bus_lane, parking_lane, grass_verge, shoulder.

For now, callers should use the *_typical_* functions everywhere. min/max are
stored for later, once the generator needs to pick a width based on context.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_STANDARDS_PATH = Path(__file__).resolve().parent.parent / "data" / "standards.json"


class UnknownRoadTypeError(Exception):
    """Raised when a requested road type isn't in the standards database."""


class UnknownComponentError(Exception):
    """Raised when a requested street component isn't in the standards database."""


def _load_raw() -> Dict:
    with open(_STANDARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_road_types() -> Dict[str, Dict]:
    """Return the full road_types dict, keyed by internal id (e.g. 'local_street')."""
    return _load_raw()["road_types"]


def get_road_type(road_type: str) -> Dict:
    road_types = list_road_types()
    if road_type not in road_types:
        raise UnknownRoadTypeError(
            f"Unknown road type '{road_type}'. Known: {', '.join(road_types)}"
        )
    return road_types[road_type]


def get_allowed_elements(road_type: str) -> List[str]:
    """Which street components make sense for this road type, e.g. no bus_lane on a proezd."""
    return get_road_type(road_type)["allowed_elements"]


def get_typical_width(component: str, road_type: str | None = None) -> float:
    """
    Return the typical width (in meters) for a street component.

    'car_lane' and 'sidewalk' are road-type-specific -- pass road_type to get the
    correct value for that category. Other components (bike_lane, bus_lane,
    parking_lane, grass_verge, shoulder) come from the flat street_components table.
    """
    if component in ("car_lane", "sidewalk"):
        if road_type is None:
            raise ValueError(f"'{component}' width depends on road_type; please provide one.")
        return get_road_type(road_type)[component]["typical"]

    components = _load_raw()["street_components"]
    if component not in components:
        raise UnknownComponentError(
            f"Unknown street component '{component}'. Known: car_lane, sidewalk, "
            f"{', '.join(components)}"
        )
    return components[component]["typical"]