"""
Simple street generation between two chosen border edges.

Current capability (first version): a single straight 2-lane road connecting
the midpoint of a chosen "entry" edge to a point on the border found by
casting a ray from the entry point. By default that ray points straight
into the plot (perpendicular to the entry edge); angle_offset_deg rotates
it, which lets the road land on a different point/edge than a pure
perpendicular shot would reach.

Not handled yet (future work): curved/multi-segment alignments, intersections,
multiple roads, or fitting road width against more elaborate cross-sections.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.models import Plot
from app.core.standards import get_typical_width

Edge = Tuple[Tuple[float, float], Tuple[float, float]]


class RoadGenerationError(Exception):
    """Raised when a road can't be generated from the given entry/exit selection."""


@dataclass
class RoadSegment:
    entry_edge_idx: int
    exit_edge_idx: int          # edge the user selected as "exit"
    actual_exit_edge_idx: int   # edge the generated road actually reaches (may differ)
    entry_point: Tuple[float, float]
    exit_point: Tuple[float, float]
    width: float
    centerline: LineString
    polygon: Polygon


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

    # Fallback (shouldn't normally happen for a simple polygon): pick the first.
    nx, ny = candidates[0]
    return math.atan2(ny, nx)


def _edge_containing_point(edges: List[Edge], point: Tuple[float, float], tol: float = 1e-6) -> Optional[int]:
    px, py = point
    for i, ((x1, y1), (x2, y2)) in enumerate(edges):
        seg = LineString([(x1, y1), (x2, y2)])
        if seg.distance(Point(px, py)) <= tol:
            return i
    return None


def generate_straight_road(
    plot: Plot,
    entry_edge_idx: int,
    exit_edge_idx: int,
    angle_offset_deg: float = 0.0,
    lanes: int = 2,
    road_type: str = "local_street",
) -> RoadSegment:
    """
    Build a straight, flat-ended road band from the entry edge's midpoint toward
    the exit edge, by casting a ray (perpendicular to the entry edge, rotated by
    angle_offset_deg) until it hits the plot boundary again.
    """
    geometry: BaseGeometry = plot.geometry
    polygon = geometry if geometry.geom_type == "Polygon" else list(geometry.geoms)[0]

    edges = polygon_edges(polygon)
    if not (0 <= entry_edge_idx < len(edges)) or not (0 <= exit_edge_idx < len(edges)):
        raise RoadGenerationError("Entry/exit edge index out of range.")
    if entry_edge_idx == exit_edge_idx:
        raise RoadGenerationError("Entry and exit must be different edges.")

    entry_edge = edges[entry_edge_idx]
    entry_point = edge_midpoint(entry_edge)

    base_angle = _inward_normal_angle(entry_edge, polygon)
    angle = base_angle + math.radians(angle_offset_deg)
    direction = (math.cos(angle), math.sin(angle))

    # Cast a long ray from the entry point and see where it re-crosses the boundary.
    far_point = (
        entry_point[0] + direction[0] * 1e6,
        entry_point[1] + direction[1] * 1e6,
    )
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

    min_travel = max(edge_length(entry_edge) * 0.05, 0.1)  # ignore hits right at the start
    far_hits = [p for p in candidate_points if Point(entry_point).distance(p) > min_travel]

    if not far_hits:
        raise RoadGenerationError(
            "Couldn't find where the road re-crosses the border. Try a smaller angle offset."
        )

    exit_point_geom = min(far_hits, key=lambda p: Point(entry_point).distance(p))
    exit_point = (exit_point_geom.x, exit_point_geom.y)

    actual_exit_edge_idx = _edge_containing_point(edges, exit_point)
    if actual_exit_edge_idx is None:
        actual_exit_edge_idx = exit_edge_idx  # fall back to the requested edge

    car_lane_width = get_typical_width("car_lane", road_type=road_type)
    desired_width = car_lane_width * lanes

    crossing_edges = [entry_edge, edges[actual_exit_edge_idx]]
    max_allowed_width = min(edge_length(e) for e in crossing_edges)
    width = min(desired_width, max_allowed_width)
    if width <= 0:
        raise RoadGenerationError("Chosen edges are too short to fit any road width.")

    centerline = LineString([entry_point, exit_point])
    road_polygon = centerline.buffer(width / 2, cap_style="flat")
    road_polygon = road_polygon.intersection(polygon)

    return RoadSegment(
        entry_edge_idx=entry_edge_idx,
        exit_edge_idx=exit_edge_idx,
        actual_exit_edge_idx=actual_exit_edge_idx,
        entry_point=entry_point,
        exit_point=exit_point,
        width=width,
        centerline=centerline,
        polygon=road_polygon,
    )