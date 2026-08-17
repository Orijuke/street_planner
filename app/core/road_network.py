"""
Street generation between two chosen border edges, now built from a full
cross-section (list of element strips) rather than a single width.

Current capability: a single straight road axis from the entry edge's
midpoint to a point found by casting a ray (perpendicular to the entry
edge, rotatable via angle_offset_deg) until it re-hits the border. Each
cross-section element (grass_verge, sidewalk, car_lane, ...) becomes its
own rectangular strip along that axis, clipped to the plot.

If the cross-section's total width doesn't fit between the two edges it
touches, every strip is scaled down proportionally so the whole thing
still fits -- this keeps relative proportions sane rather than just
chopping off whichever element happens to be built last.

Not handled yet (future work): curved/multi-segment alignments,
intersections, multiple roads.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.cross_section import CrossSection
from app.core.models import Plot

Edge = Tuple[Tuple[float, float], Tuple[float, float]]


class RoadGenerationError(Exception):
    """Raised when a road can't be generated from the given entry/exit selection."""


@dataclass
class RoadResult:
    entry_edge_idx: int
    exit_edge_idx: int          # edge the user selected as "exit"
    actual_exit_edge_idx: int   # edge the generated road actually reaches (may differ)
    entry_point: Tuple[float, float]
    exit_point: Tuple[float, float]
    centerline: LineString
    strips: List[Tuple[str, Polygon]] = field(default_factory=list)  # (element_name, polygon), outer-to-outer order
    total_width: float = 0.0    # actual width used (after any scale-down)
    scale_factor: float = 1.0   # 1.0 if the desired cross-section fit as-is


def polygon_edges(polygon: Polygon) -> List[Edge]:
    """Return the exterior ring's edges as a list of (start, end) coordinate pairs."""
    coords = list(polygon.exterior.coords)
    if coords[0] == coords[-1]:
        coords = coords[:-1]  # drop the closing duplicate point
    return [(coords[i], coords[(i + 1) % len(coords)]) for i in range(len(coords))]


def edge_length(edge: Edge) -> float:
    (x1, y1), (x2, y2) = edge
    return math.hypot(x2 - x1, y2 - y1)


def edge_midpoint(edge: Edge) -> Tuple[float, float]:
    (x1, y1), (x2, y2) = edge
    return (x1 + x2) / 2, (y1 + y2) / 2


def _inward_normal_angle(edge: Edge, polygon: Polygon) -> float:
    """Angle (radians) of the unit normal to `edge` that points into `polygon`."""
    (x1, y1), (x2, y2) = edge
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    dx, dy = dx / length, dy / length

    candidates = [(-dy, dx), (dy, -dx)]
    mx, my = edge_midpoint(edge)
    probe_dist = max(length * 0.01, 1e-3)

    for nx, ny in candidates:
        probe = Point(mx + nx * probe_dist, my + ny * probe_dist)
        if polygon.contains(probe):
            return math.atan2(ny, nx)

    nx, ny = candidates[0]  # fallback, shouldn't normally happen for a simple polygon
    return math.atan2(ny, nx)


def _edge_containing_point(edges: List[Edge], point: Tuple[float, float], tol: float = 1e-6) -> Optional[int]:
    px, py = point
    for i, ((x1, y1), (x2, y2)) in enumerate(edges):
        seg = LineString([(x1, y1), (x2, y2)])
        if seg.distance(Point(px, py)) <= tol:
            return i
    return None


def _find_road_axis(
    polygon: Polygon,
    edges: List[Edge],
    entry_edge_idx: int,
    exit_edge_idx: int,
    angle_offset_deg: float,
) -> Tuple[Tuple[float, float], Tuple[float, float], int, float]:
    """Returns (entry_point, exit_point, actual_exit_edge_idx, max_allowed_width)."""
    entry_edge = edges[entry_edge_idx]
    entry_point = edge_midpoint(entry_edge)

    base_angle = _inward_normal_angle(entry_edge, polygon)
    angle = base_angle + math.radians(angle_offset_deg)
    direction = (math.cos(angle), math.sin(angle))

    far_point = (entry_point[0] + direction[0] * 1e6, entry_point[1] + direction[1] * 1e6)
    ray = LineString([entry_point, far_point])
    boundary_hits = polygon.exterior.intersection(ray)

    candidate_points: List[Point] = []
    if boundary_hits.is_empty:
        pass
    elif boundary_hits.geom_type == "Point":
        candidate_points = [boundary_hits]
    elif boundary_hits.geom_type == "MultiPoint":
        candidate_points = list(boundary_hits.geoms)
    elif boundary_hits.geom_type in ("GeometryCollection", "MultiLineString"):
        for geom in boundary_hits.geoms:
            if geom.geom_type == "Point":
                candidate_points.append(geom)

    min_travel = max(edge_length(entry_edge) * 0.05, 0.1)
    far_hits = [p for p in candidate_points if Point(entry_point).distance(p) > min_travel]

    if not far_hits:
        raise RoadGenerationError(
            "Couldn't find where the road re-crosses the border. Try a smaller angle offset."
        )

    exit_point_geom = min(far_hits, key=lambda p: Point(entry_point).distance(p))
    exit_point = (exit_point_geom.x, exit_point_geom.y)

    actual_exit_edge_idx = _edge_containing_point(edges, exit_point)
    if actual_exit_edge_idx is None:
        actual_exit_edge_idx = exit_edge_idx

    max_allowed_width = min(edge_length(entry_edge), edge_length(edges[actual_exit_edge_idx]))
    return entry_point, exit_point, actual_exit_edge_idx, max_allowed_width


def generate_road(
    plot: Plot,
    entry_edge_idx: int,
    exit_edge_idx: int,
    cross_section: CrossSection,
    angle_offset_deg: float = 0.0,
) -> RoadResult:
    """
    Build a straight road made of the cross-section's element strips, from
    the entry edge's midpoint toward a point found by ray-casting toward
    the exit edge (see _find_road_axis). If the cross-section is wider than
    the shorter of the two touched edges, every strip is scaled down to fit.
    """
    geometry: BaseGeometry = plot.geometry
    polygon = geometry if geometry.geom_type == "Polygon" else list(geometry.geoms)[0]

    edges = polygon_edges(polygon)
    if not (0 <= entry_edge_idx < len(edges)) or not (0 <= exit_edge_idx < len(edges)):
        raise RoadGenerationError("Entry/exit edge index out of range.")
    if entry_edge_idx == exit_edge_idx:
        raise RoadGenerationError("Entry and exit must be different edges.")
    if not cross_section.widths:
        raise RoadGenerationError("Select at least one street element before generating.")

    entry_point, exit_point, actual_exit_edge_idx, max_allowed_width = _find_road_axis(
        polygon, edges, entry_edge_idx, exit_edge_idx, angle_offset_deg
    )

    desired_total_width = cross_section.total_width
    if desired_total_width <= 0:
        raise RoadGenerationError("Cross-section has zero total width.")

    scale_factor = min(1.0, max_allowed_width / desired_total_width)
    scaled_widths = [(name, w * scale_factor) for name, w in cross_section.widths]
    total_width = sum(w for _, w in scaled_widths)
    if total_width <= 0:
        raise RoadGenerationError("Chosen edges are too short to fit any road width.")

    ex, ey = entry_point
    xx, xy = exit_point
    dx, dy = xx - ex, xy - ey
    length = math.hypot(dx, dy)
    if length == 0:
        raise RoadGenerationError("Entry and exit points coincide; can't build a road axis.")
    dir_x, dir_y = dx / length, dy / length
    perp_x, perp_y = -dir_y, dir_x  # unit vector perpendicular to the axis

    strips: List[Tuple[str, Polygon]] = []
    running_offset = -total_width / 2
    for name, width in scaled_widths:
        start_offset = running_offset
        end_offset = running_offset + width
        running_offset = end_offset

        p1 = (ex + perp_x * start_offset, ey + perp_y * start_offset)
        p2 = (ex + perp_x * end_offset, ey + perp_y * end_offset)
        p3 = (xx + perp_x * end_offset, xy + perp_y * end_offset)
        p4 = (xx + perp_x * start_offset, xy + perp_y * start_offset)

        strip_polygon = Polygon([p1, p2, p3, p4]).intersection(polygon)
        if not strip_polygon.is_empty:
            strips.append((name, strip_polygon))

    return RoadResult(
        entry_edge_idx=entry_edge_idx,
        exit_edge_idx=exit_edge_idx,
        actual_exit_edge_idx=actual_exit_edge_idx,
        entry_point=entry_point,
        exit_point=exit_point,
        centerline=LineString([entry_point, exit_point]),
        strips=strips,
        total_width=total_width,
        scale_factor=scale_factor,
    )