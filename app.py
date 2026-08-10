"""
app.py — Entry point for the Sydney Traffic Detection System.

Run with:
    python app.py

Make sure other files are part of the same directory before running (API/Workers/CONFIG/Detection/dashboard/Dialogs/Constants/Widgets) before running
"""

import sys


import detection  

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from dashboard import TrafficGUI


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    win = TrafficGUI()
    win.show()
    sys.exit(app.exec_())
