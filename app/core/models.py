"""Core data models shared across the application."""
from dataclasses import dataclass
from typing import Optional

from shapely.geometry.base import BaseGeometry


@dataclass
class Plot:
    """Represents a loaded land-plot border."""

    geometry: BaseGeometry          # shapely Polygon / MultiPolygon
    source_path: str                # original file path
    crs: Optional[str] = None       # e.g. "EPSG:4326", None if unknown/local
    name: str = "Untitled plot"

    @property
    def bounds(self):
        """(minx, miny, maxx, maxy) of the border."""
        return self.geometry.bounds

    @property
    def area(self) -> float:
        """Raw area in the units of the source geometry (not necessarily m^2)."""
        return self.geometry.area