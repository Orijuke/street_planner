"""Main application window: choose a border file, see it rendered on the canvas."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox,
    QStatusBar, QToolBar, QVBoxLayout, QWidget,
)

from app.core.border_loader import BorderLoadError, load_border
from app.ui.map_canvas import MapCanvas


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Street Planner")
        self.resize(1100, 750)
        self.plot = None
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = MapCanvas(central)
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open border file...", self)
        open_action.triggered.connect(self.open_border_file)
        toolbar.addAction(open_action)

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.plot_info_label = QLabel("No border loaded.")
        status.addWidget(self.plot_info_label)

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
        self.canvas.show_plot(plot)
        minx, miny, maxx, maxy = plot.bounds
        self.plot_info_label.setText(
            f"Loaded: {plot.name}  |  bounds: "
            f"({minx:.2f}, {miny:.2f}) -> ({maxx:.2f}, {maxy:.2f})  |  "
            f"area (raw units): {plot.area:.2f}"
        )