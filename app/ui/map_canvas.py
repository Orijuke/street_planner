"""
QGraphicsView-based canvas that draws a land-plot border, its edges (for
entry/exit selection), and any generated road.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsScene, QGraphicsView

from app.core.models import Plot
from app.core.road_network import polygon_edges

BORDER_PEN = QPen(QColor("#2b6cb0"))
BORDER_BRUSH = QBrush(QColor(43, 108, 176, 40))

EDGE_DEFAULT_PEN = QPen(QColor("#94a3b8"))
EDGE_ENTRY_PEN = QPen(QColor("#16a34a"))   # green
EDGE_EXIT_PEN = QPen(QColor("#dc2626"))    # red

ROAD_BRUSH = QBrush(QColor("#4b5563"))     # asphalt gray
ROAD_PEN = QPen(QColor("#374151"))

for _pen in (BORDER_PEN, EDGE_DEFAULT_PEN, EDGE_ENTRY_PEN, EDGE_EXIT_PEN, ROAD_PEN):
    _pen.setWidthF(0)  # cosmetic: constant on-screen width regardless of zoom

EDGE_HIT_WIDTH = 6  # visual + click width for edge lines (pixels, cosmetic)


class MapCanvas(QGraphicsView):
    edge_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#eef1f4")))
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        self._edge_items: List[QGraphicsLineItem] = []
        self._road_items: List[QGraphicsPolygonItem] = []
        self._entry_edge_idx: Optional[int] = None
        self._exit_edge_idx: Optional[int] = None

    def clear(self) -> None:
        self._scene.clear()
        self._edge_items = []
        self._road_items = []
        self._entry_edge_idx = None
        self._exit_edge_idx = None

    def show_plot(self, plot: Plot) -> None:
        self.clear()

        geometry = plot.geometry
        polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)

        for poly in polygons:
            qpoly = QPolygonF([QPointF(x, -y) for x, y in poly.exterior.coords])
            self._scene.addPolygon(qpoly, BORDER_PEN, BORDER_BRUSH)

        # Only the first polygon's edges are selectable for entry/exit (matches
        # the road-generation logic, which also only looks at polygons[0]).
        main_polygon = polygons[0]
        edges = polygon_edges(main_polygon)
        for idx, ((x1, y1), (x2, y2)) in enumerate(edges):
            item = QGraphicsLineItem(x1, -y1, x2, -y2)
            pen = QPen(EDGE_DEFAULT_PEN)
            pen.setWidth(EDGE_HIT_WIDTH)
            pen.setCosmetic(True)
            item.setPen(pen)
            item.setData(0, idx)
            item.setZValue(1)
            self._scene.addItem(item)
            self._edge_items.append(item)

        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_entry_edge(self, idx: int) -> None:
        self._restyle_edge(self._entry_edge_idx, EDGE_DEFAULT_PEN)
        self._entry_edge_idx = idx
        self._restyle_edge(idx, EDGE_ENTRY_PEN)

    def set_exit_edge(self, idx: int) -> None:
        self._restyle_edge(self._exit_edge_idx, EDGE_DEFAULT_PEN)
        self._exit_edge_idx = idx
        self._restyle_edge(idx, EDGE_EXIT_PEN)

    def _restyle_edge(self, idx: Optional[int], base_pen: QPen) -> None:
        if idx is None or idx >= len(self._edge_items):
            return
        pen = QPen(base_pen)
        pen.setWidth(EDGE_HIT_WIDTH)
        pen.setCosmetic(True)
        self._edge_items[idx].setPen(pen)

    def draw_road(self, road_geometry) -> None:
        """road_geometry: a shapely Polygon or MultiPolygon."""
        for item in self._road_items:
            self._scene.removeItem(item)
        self._road_items = []

        polys = [road_geometry] if road_geometry.geom_type == "Polygon" else list(road_geometry.geoms)
        for poly in polys:
            if poly.is_empty:
                continue
            qpoly = QPolygonF([QPointF(x, -y) for x, y in poly.exterior.coords])
            item = self._scene.addPolygon(qpoly, ROAD_PEN, ROAD_BRUSH)
            item.setZValue(2)
            self._road_items.append(item)

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsLineItem):
            edge_idx = item.data(0)
            if edge_idx is not None:
                self.edge_clicked.emit(int(edge_idx))
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._scene.sceneRect().isEmpty():
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)