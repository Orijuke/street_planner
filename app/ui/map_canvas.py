"""QGraphicsView-based canvas that draws a land-plot border."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from app.core.models import Plot


class MapCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#eef1f4")))
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def clear(self) -> None:
        self._scene.clear()

    def show_plot(self, plot: Plot) -> None:
        self.clear()
        geometry = plot.geometry
        polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)

        pen = QPen(QColor("#2b6cb0"))
        pen.setWidthF(0)
        brush = QBrush(QColor(43, 108, 176, 40))

        for poly in polygons:
            qpoly = QPolygonF([QPointF(x, -y) for x, y in poly.exterior.coords])
            self._scene.addPolygon(qpoly, pen, brush)

        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._scene.sceneRect().isEmpty():
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)