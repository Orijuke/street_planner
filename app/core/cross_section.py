"""
Turns a road type + a chosen set of street elements into an ordered
cross-section (a list of (element_name, width) pairs) using typical
widths from the standards database.

Ordering is fixed and symmetric-ish (sidewalk/verge on the outside,
car lanes in the middle) so the drawn road looks like a real street
rather than a random stack of strips. This can be made configurable
later if you want to reorder elements per project.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.core.standards import get_typical_width

# Left-to-right layout order. Anything not listed falls back to the end.
_ELEMENT_ORDER = [
    "grass_verge",
    "sidewalk",
    "parking_lane",
    "bike_lane",
    "bus_lane",
    "car_lane",
]


@dataclass
class CrossSection:
    road_type: str
    elements: List[str]                 # element names, in layout order
    widths: List[Tuple[str, float]]      # (element_name, width_m), in layout order

    @property
    def total_width(self) -> float:
        return sum(w for _, w in self.widths)


def build_cross_section(road_type: str, chosen_elements: List[str], lanes: int = 2) -> CrossSection:
    """
    Build a symmetric cross-section: verge/sidewalk on both outer edges (if
    chosen), then parking/bike/bus lanes, then `lanes` car lanes in the middle.

    `chosen_elements` should be a subset of that road type's allowed_elements
    (the UI is responsible for enforcing that; this function doesn't re-check
    against the database to keep it simple and testable).
    """
    ordered = sorted(set(chosen_elements), key=lambda e: _ELEMENT_ORDER.index(e) if e in _ELEMENT_ORDER else 999)

    left_side: List[str] = []
    right_side: List[str] = []
    car_lanes: List[str] = []

    # Elements other than car_lane get mirrored on both sides of the road,
    # in the order defined by _ELEMENT_ORDER (outermost first).
    for element in ordered:
        if element == "car_lane":
            continue
        left_side.append(element)
        right_side.insert(0, element)

    car_lanes = ["car_lane"] * (lanes if "car_lane" in chosen_elements else 0)

    layout_order = left_side + car_lanes + right_side

    widths: List[Tuple[str, float]] = []
    for element in layout_order:
        width = get_typical_width(element, road_type=road_type if element in ("car_lane", "sidewalk") else None)
        widths.append((element, width))

    return CrossSection(road_type=road_type, elements=layout_order, widths=widths)