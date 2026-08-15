"""
Loading and validating land-plot border files.

Supported formats:
    * GeoJSON (.geojson, .json)     -- always available
    * Shapefile (.shp)              -- requires geopandas + fiona (optional)
    * simple point list (.csv/.txt) -- "x,y" per line
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Union

from shapely.geometry import Polygon, shape
from shapely.geometry.base import BaseGeometry

from app.core.models import Plot


class BorderLoadError(Exception):
    """Raised when a border file can't be read or doesn't contain a valid polygon."""


SUPPORTED_EXTENSIONS = {".geojson", ".json", ".shp", ".csv", ".txt"}


def load_border(path: Union[str, Path]) -> Plot:
    path = Path(path)
    if not path.exists():
        raise BorderLoadError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise BorderLoadError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext in {".geojson", ".json"}:
        geometry = _load_geojson(path)
    elif ext == ".shp":
        geometry = _load_shapefile(path)
    else:
        geometry = _load_point_list(path)

    _validate_geometry(geometry)
    return Plot(geometry=geometry, source_path=str(path), name=path.stem)


def _load_geojson(path: Path) -> BaseGeometry:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise BorderLoadError("GeoJSON FeatureCollection has no features.")
        geom_dict = features[0]["geometry"]
    elif data.get("type") == "Feature":
        geom_dict = data["geometry"]
    else:
        geom_dict = data

    try:
        return shape(geom_dict)
    except Exception as exc:
        raise BorderLoadError(f"Could not parse GeoJSON geometry: {exc}") from exc


def _load_shapefile(path: Path) -> BaseGeometry:
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise BorderLoadError(
            "Reading .shp files requires the optional 'geopandas' package "
            "(pip install geopandas)."
        ) from exc

    gdf = gpd.read_file(path)
    if gdf.empty:
        raise BorderLoadError("Shapefile contains no geometries.")
    return gdf.geometry.iloc[0]


def _load_point_list(path: Path) -> BaseGeometry:
    points = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].strip().startswith("#"):
                continue
            if len(row) < 2:
                continue
            try:
                x, y = float(row[0]), float(row[1])
            except ValueError:
                continue
            points.append((x, y))

    if len(points) < 3:
        raise BorderLoadError("Need at least 3 valid 'x,y' points to form a border.")

    return Polygon(points)


def _validate_geometry(geometry: BaseGeometry) -> None:
    if geometry is None or geometry.is_empty:
        raise BorderLoadError("Loaded geometry is empty.")
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise BorderLoadError(
            f"Border must be a Polygon or MultiPolygon, got '{geometry.geom_type}'."
        )
    if not geometry.is_valid:
        raise BorderLoadError("Border geometry is invalid (self-intersecting or malformed).")