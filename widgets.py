from collections import deque
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from PyQt5.QtWidgets import (
    QLabel, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont

from constants import C, VEHICLE_CLASSES, VEHICLE_COLOURS, VEHICLE_ICONS


class ImagePanel(QLabel):
    # Displays a camera image scaled to fit, with placeholder text when empty
    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._pix = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(280, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._show_placeholder()

    def set_image(self, arr: np.ndarray) -> None:
        arr = np.ascontiguousarray(arr)
        h, w, ch = arr.shape
        qimg = QImage(arr.tobytes(), w, h, ch * w, QImage.Format_RGB888)
        self._pix = QPixmap.fromImage(qimg)
        self._rescale()
        self.setStyleSheet(f"QLabel {{ background: {C['surface_alt']}; border: 2px solid {C['border']}; border-radius: 8px; }}")

    def clear_image(self) -> None:
        self._pix = None
        self.clear()
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.setText(self._placeholder)
        self.setStyleSheet(f"QLabel {{ background: {C['surface_alt']}; border: 2px dashed {C['border_dark']}; border-radius: 8px; color: {C['text_soft']}; font-size: 13px; }}")

    def _rescale(self) -> None:
        if self._pix:
            self.setPixmap(self._pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()


class CongestionBanner(QWidget):
    # Colour-coded banner showing Low / Moderate / Heavy traffic level
    _STYLES = {
        "—":        {"bg": C["surface_alt"], "border": C["border"],       "text": C["text_soft"],  "label": "No data yet",       "desc": "Press Analyse to run detection"},
        "Low":      {"bg": C["low_bg"],      "border": C["low_border"],   "text": C["low_text"],   "label": "Low Traffic",       "desc": "Roads are clear — fewer than 20 vehicles detected"},
        "Moderate": {"bg": C["mod_bg"],      "border": C["mod_border"],   "text": C["mod_text"],   "label": "Moderate Traffic",  "desc": "Some congestion — 20 to 49 vehicles detected"},
        "Heavy":    {"bg": C["heavy_bg"],    "border": C["heavy_border"], "text": C["heavy_text"], "label": "Heavy Traffic",     "desc": "High congestion — 50 or more vehicles detected"},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)
        self._level_lbl = QLabel("—")
        self._level_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self._desc_lbl = QLabel("Press Analyse to run detection")
        self._desc_lbl.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self._level_lbl)
        layout.addWidget(self._desc_lbl)
        self._apply("—")

    def set_level(self, level: str) -> None:
        s = self._STYLES.get(level, self._STYLES["—"])
        self._level_lbl.setText(s["label"])
        self._desc_lbl.setText(s["desc"])
        self._apply(level)

    def _apply(self, level: str) -> None:
        s = self._STYLES.get(level, self._STYLES["—"])
        self.setStyleSheet(f"QWidget {{ background: {s['bg']}; border: 2px solid {s['border']}; border-radius: 10px; }} QLabel {{ background: transparent; border: none; color: {s['text']}; }}")


class VehicleCard(QFrame):
    # Card showing icon, vehicle type, and count for one class
    def __init__(self, label: str, icon: str, colour: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"QFrame {{ background: {C['surface']}; border: 1.5px solid {C['border']}; border-radius: 10px; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(5)
        bar.setStyleSheet(f"background: {colour}; border-radius: 10px 10px 0 0;")
        root.addWidget(bar)

        body = QWidget()
        body.setStyleSheet("background: transparent; border: none;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(14, 10, 14, 12)
        bl.setSpacing(4)

        top = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        icon_lbl.setStyleSheet("border: none; background: transparent;")

        self._count = QLabel("—")
        self._count.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self._count.setStyleSheet(f"color: {colour}; border: none; background: transparent;")
        self._count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top.addWidget(icon_lbl)
        top.addStretch()
        top.addWidget(self._count)
        bl.addLayout(top)

        name_lbl = QLabel(label)
        name_lbl.setFont(QFont("Segoe UI", 11))
        name_lbl.setStyleSheet(f"color: {C['text_mid']}; border: none; background: transparent;")
        bl.addWidget(name_lbl)
        root.addWidget(body)

    def update_value(self, v) -> None:
        self._count.setText("—" if v is None else str(v))


class TrendGraph(FigureCanvas):
    # Matplotlib line chart tracking vehicle counts over time
    MAX = 20

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(4, 2.6), dpi=96, facecolor=C["surface"])
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._ax      = self._fig.add_subplot(111)
        self._history = {k: deque(maxlen=self.MAX) for k in VEHICLE_CLASSES}
        self._xlabels = []
        self._colors  = dict(zip(VEHICLE_CLASSES, VEHICLE_COLOURS))
        self._empty()

    def _style_ax(self) -> None:
        self._ax.set_facecolor(C["surface_alt"])
        self._ax.tick_params(colors=C["text_mid"], labelsize=8)
        for spine in self._ax.spines.values():
            spine.set_edgecolor(C["border"])
        self._ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        self._ax.set_ylabel("Vehicles", fontsize=9, color=C["text_mid"])

    def _empty(self) -> None:
        self._ax.clear()
        self._style_ax()
        self._ax.set_title("Detections over time — run Analyse to populate", fontsize=9, color=C["text_soft"], pad=6)
        self._fig.tight_layout(pad=0.8)
        self.draw()

    def push(self, counts: dict) -> None:
        self._xlabels.append(datetime.now().strftime("%H:%M:%S"))
        if len(self._xlabels) > self.MAX:
            self._xlabels = self._xlabels[-self.MAX:]
        for k in VEHICLE_CLASSES:
            self._history[k].append(counts.get(k, 0))

        self._ax.clear()
        self._style_ax()
        self._ax.set_title("Vehicle count over time", fontsize=10, color=C["text"], pad=6, fontweight="600")

        x = list(range(len(self._xlabels)))
        for k in VEHICLE_CLASSES:
            y = list(self._history[k])
            self._ax.plot(x, y, marker="o", markersize=3.5, linewidth=2, label=k, color=self._colors[k])
            self._ax.fill_between(x, y, alpha=0.08, color=self._colors[k])

        if x:
            step = max(1, len(x) // 5)
            self._ax.set_xticks(x[::step])
            self._ax.set_xticklabels(self._xlabels[::step], rotation=30, ha="right", fontsize=7)

        self._ax.legend(fontsize=8, loc="upper left", framealpha=0.8, edgecolor=C["border"], labelcolor=C["text"])
        self._fig.tight_layout(pad=0.8)
        self.draw()

    def reset(self) -> None:
        self._history = {k: deque(maxlen=self.MAX) for k in VEHICLE_CLASSES}
        self._xlabels = []
        self._empty()


class Header(QWidget):
    # Dark title bar with app name and live clock
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setStyleSheet(f"QWidget {{ background: {C['header_bg']}; border-radius: 0px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)

        dot = QLabel("◉")
        dot.setStyleSheet("color: #3B82F6; font-size: 18px; background: transparent;")

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Sydney Traffic Detection System")
        title.setStyleSheet(f"color: {C['text_inv']}; font-size: 16px; font-weight: 700; background: transparent;")
        sub = QLabel("YOLOv8s · SAHI · Real-time detection · TfNSW Live Traffic API")
        sub.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
        title_col.addWidget(title)
        title_col.addWidget(sub)

        self._clock = QLabel()
        self._clock.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
        self._clock.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(1000)
        self._tick()

        lay.addWidget(dot)
        lay.addSpacing(10)
        lay.addLayout(title_col)
        lay.addStretch()
        lay.addWidget(self._clock)

    def _tick(self) -> None:
        self._clock.setText(datetime.now().strftime("%A %d %b %Y   %H:%M:%S"))


class DetectionLegend(QWidget):
    # Horizontal colour swatch legend for bounding box colours
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 8px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        title = QLabel("Bounding box colours:")
        title.setStyleSheet(f"color: {C['text_mid']}; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        lay.addWidget(title)
        lay.addSpacing(8)

        for label, colour in zip(VEHICLE_CLASSES, VEHICLE_COLOURS):
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background: {colour}; border-radius: 3px; border: none;")
            txt = QLabel(label)
            txt.setStyleSheet(f"color: {C['text_mid']}; font-size: 11px; border: none; background: transparent;")
            lay.addWidget(swatch)
            lay.addWidget(txt)
            lay.addSpacing(10)

        lay.addStretch()
        note = QLabel("Boxes show where each vehicle was detected in the image")
        note.setStyleSheet(f"color: {C['text_soft']}; font-size: 10px; font-style: italic; border: none; background: transparent;")
        lay.addWidget(note)


class ModeIndicator(QLabel):
    # LIVE / DEMO pill badge shown in the toolbar
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setAlignment(Qt.AlignCenter)
        self.set_demo()

    def set_live(self) -> None:
        self.setText("  LIVE  ")
        self.setStyleSheet(f"background: {C['low_bg']}; color: {C['low_text']}; border: 1.5px solid {C['low_border']}; border-radius: 6px; font-size: 11px; font-weight: 700; padding: 0 6px;")

    def set_demo(self) -> None:
        self.setText("  DEMO  ")
        self.setStyleSheet(f"background: {C['mod_bg']}; color: {C['mod_text']}; border: 1.5px solid {C['mod_border']}; border-radius: 6px; font-size: 11px; font-weight: 700; padding: 0 6px;")
