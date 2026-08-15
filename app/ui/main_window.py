"""
Main application window: choose a border file, pick entry/exit edges, and
generate a simple straight road between them.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QStatusBar, QToolBar, QVBoxLayout, QWidget,
)

from app.core.border_loader import BorderLoadError, load_border
from app.core.road_network import RoadGenerationError, edge_length, generate_straight_road, polygon_edges
from app.ui.map_canvas import MapCanvas


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Street Planner")
        self.resize(1100, 750)

        self.plot = None
        self.selection_mode: Optional[str] = None  # None | "entry" | "exit"
        self.entry_edge_idx: Optional[int] = None
        self.exit_edge_idx: Optional[int] = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = MapCanvas(central)
        self.canvas.edge_clicked.connect(self.on_edge_clicked)
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open border file...", self)
        open_action.triggered.connect(self.open_border_file)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        self.entry_action = QAction("Select entry edge", self)
        self.entry_action.setCheckable(True)
        self.entry_action.triggered.connect(lambda: self._set_selection_mode("entry"))
        toolbar.addAction(self.entry_action)

        self.exit_action = QAction("Select exit edge", self)
        self.exit_action.setCheckable(True)
        self.exit_action.triggered.connect(lambda: self._set_selection_mode("exit"))
        toolbar.addAction(self.exit_action)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Angle offset (deg): "))
        self.angle_spinbox = QDoubleSpinBox(self)
        self.angle_spinbox.setRange(-89.0, 89.0)
        self.angle_spinbox.setValue(0.0)
        self.angle_spinbox.setSingleStep(5.0)
        toolbar.addWidget(self.angle_spinbox)

        toolbar.addSeparator()
        self.generate_action = QAction("Generate road", self)
        self.generate_action.setEnabled(False)
        self.generate_action.triggered.connect(self.generate_road)
        toolbar.addAction(self.generate_action)

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.plot_info_label = QLabel("No border loaded.")
        status.addWidget(self.plot_info_label)

    def _set_selection_mode(self, mode: str) -> None:
        # Only one of entry/exit selection can be "armed" at a time.
        if mode == "entry":
            self.selection_mode = "entry" if self.entry_action.isChecked() else None
            self.exit_action.setChecked(False)
        else:
            self.selection_mode = "exit" if self.exit_action.isChecked() else None
            self.entry_action.setChecked(False)

    def open_border_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a land-plot border file", "",
            "Border files (*.geojson *.json *.shp *.csv *.txt);;All files (*)",
        )
        if not path:
            return

        try:
            plot = load_border(path)
        except BorderLoadError as exc:
            QMessageBox.critical(self, "Could not load border", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Unexpected error", str(exc))
            return

        self.plot = plot
        self.entry_edge_idx = None
        self.exit_edge_idx = None
        self.selection_mode = None
        self.entry_action.setChecked(False)
        self.exit_action.setChecked(False)
        self.generate_action.setEnabled(False)

        self.canvas.show_plot(plot)
        minx, miny, maxx, maxy = plot.bounds
        self.plot_info_label.setText(
            f"Loaded: {plot.name}  |  bounds: "
            f"({minx:.2f}, {miny:.2f}) -> ({maxx:.2f}, {maxy:.2f})  |  "
            f"area (raw units): {plot.area:.2f}  |  "
            f"Click 'Select entry edge', then click a border edge on the map."
        )

    def on_edge_clicked(self, edge_idx: int) -> None:
        if self.plot is None or self.selection_mode is None:
            return

        if self.selection_mode == "entry":
            self.entry_edge_idx = edge_idx
            self.canvas.set_entry_edge(edge_idx)
            self.entry_action.setChecked(False)
        elif self.selection_mode == "exit":
            self.exit_edge_idx = edge_idx
            self.canvas.set_exit_edge(edge_idx)
            self.exit_action.setChecked(False)

        self.selection_mode = None
        self.generate_action.setEnabled(
            self.entry_edge_idx is not None
            and self.exit_edge_idx is not None
            and self.entry_edge_idx != self.exit_edge_idx
        )
        self._update_status_for_selection()

    def _update_status_for_selection(self) -> None:
        if self.plot is None:
            return
        geometry = self.plot.geometry
        polygon = geometry if geometry.geom_type == "Polygon" else list(geometry.geoms)[0]
        edges = polygon_edges(polygon)

        parts = []
        if self.entry_edge_idx is not None:
            parts.append(f"entry edge #{self.entry_edge_idx} ({edge_length(edges[self.entry_edge_idx]):.2f} m)")
        if self.exit_edge_idx is not None:
            parts.append(f"exit edge #{self.exit_edge_idx} ({edge_length(edges[self.exit_edge_idx]):.2f} m)")
        if parts:
            self.plot_info_label.setText("Selected: " + "  |  ".join(parts))

    def generate_road(self) -> None:
        if self.plot is None or self.entry_edge_idx is None or self.exit_edge_idx is None:
            return

        try:
            road = generate_straight_road(
                self.plot,
                entry_edge_idx=self.entry_edge_idx,
                exit_edge_idx=self.exit_edge_idx,
                angle_offset_deg=self.angle_spinbox.value(),
            )
        except RoadGenerationError as exc:
            QMessageBox.warning(self, "Could not generate road", str(exc))
            return

        self.canvas.draw_road(road.polygon)

        note = ""
        if road.actual_exit_edge_idx != self.exit_edge_idx:
            note = (
                f"  (note: at this angle the road actually reaches edge "
                f"#{road.actual_exit_edge_idx}, not the selected exit edge #{self.exit_edge_idx})"
            )
        self.plot_info_label.setText(
            f"Road generated: width {road.width:.2f} m, "
            f"length {road.centerline.length:.2f} m{note}"
        )
