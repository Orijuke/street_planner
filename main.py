import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("Street Planner - Test Window")
window.resize(600, 400)

label = QLabel("Test Window Text")
window.setCentralWidget(label)

window.show()
sys.exit(app.exec())