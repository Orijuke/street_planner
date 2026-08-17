"""
Left-side panel: choose a road type, then check off which street elements
to include. The checkbox list rebuilds every time the road type changes,
showing only that road type's allowed_elements (per the standards database)
plus each element's typical width for quick reference.
"""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.core.standards import get_allowed_elements, get_typical_width, list_road_types

ELEMENT_LABELS = {
    "car_lane": "Полоса движения / Car lane",
    "bus_lane": "Автобусная полоса / Bus lane",
    "bike_lane": "Велополоса / Bike lane",
    "parking_lane": "Парковка / Parking lane",
    "sidewalk": "Тротуар / Sidewalk",
    "grass_verge": "Газон / Grass verge",
}


class ParameterPanel(QWidget):
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._road_types = list_road_types()
        self._build_ui()
        self._rebuild_elements()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Road type</b>"))
        self.road_type_combo = QComboBox(self)
        for key, data in self._road_types.items():
            self.road_type_combo.addItem(data.get("label_ru", key), userData=key)
        self.road_type_combo.currentIndexChanged.connect(self._rebuild_elements)
        layout.addWidget(self.road_type_combo)

        self.elements_group = QGroupBox("Street elements", self)
        self.elements_form = QFormLayout(self.elements_group)
        layout.addWidget(self.elements_group)

        layout.addStretch(1)

    def _rebuild_elements(self) -> None:
        while self.elements_form.rowCount():
            self.elements_form.removeRow(0)
        self._checkboxes.clear()
        self.lanes_spinbox = None

        road_type = self.current_road_type()
        allowed = get_allowed_elements(road_type)

        for element in allowed:
            width = get_typical_width(
                element, road_type=road_type if element in ("car_lane", "sidewalk") else None
            )
            label = ELEMENT_LABELS.get(element, element)
            checkbox = QCheckBox(f"{label}  —  {width:.2f} m", self)
            checkbox.setChecked(element == "car_lane")
            checkbox.toggled.connect(self.selection_changed.emit)
            self._checkboxes[element] = checkbox

            if element == "car_lane":
                self.lanes_spinbox = QSpinBox(self)
                self.lanes_spinbox.setRange(1, 4)
                self.lanes_spinbox.setValue(2)
                self.lanes_spinbox.valueChanged.connect(self.selection_changed.emit)
                self.elements_form.addRow(checkbox, self.lanes_spinbox)
            else:
                self.elements_form.addRow(checkbox)

        self.selection_changed.emit()

    def current_road_type(self) -> str:
        return self.road_type_combo.currentData()

    def chosen_elements(self) -> List[str]:
        return [name for name, cb in self._checkboxes.items() if cb.isChecked()]

    def car_lane_count(self) -> int:
        return self.lanes_spinbox.value() if self.lanes_spinbox is not None else 2
