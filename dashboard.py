from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QSplitter, QStatusBar, QGroupBox, QSizePolicy,
    QProgressBar, QScrollArea, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from constants import C, STYLESHEET, VEHICLE_CLASSES, VEHICLE_COLOURS, VEHICLE_ICONS
from config import load_config, save_config
from api import REQUESTS_AVAILABLE
from workers import DetectionWorker, CameraScanWorker
from widgets import (
    ImagePanel, CongestionBanner, VehicleCard,
    TrendGraph, Header, DetectionLegend, ModeIndicator,
)
from dialogs import ApiSettingsDialog


class TrafficGUI(QMainWindow):
    # Main application window - composes all panels and manages detection flow

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sydney Traffic Detection System")
        self.resize(1360, 880)
        self.setMinimumSize(1000, 650)

        self._cfg     = load_config()
        self._worker  = None
        self._scanner = None
        self._busy    = False
        self._cameras: list[dict] = self._cfg.get("cameras", [])

        self._build_ui()
        self.setStyleSheet(STYLESHEET)

        # Restore saved camera list on startup
        if self._cameras:
            self._populate_camera_combo(self._cameras)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(Header())

        content = QWidget()
        content.setStyleSheet(f"background: {C['page']};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 14, 16, 10)
        cl.setSpacing(12)
        cl.addWidget(self._make_toolbar())

        # Side-by-side camera feed and stats panel
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        splitter.addWidget(self._make_camera_panel())
        splitter.addWidget(self._make_stats_panel())
        splitter.setSizes([820, 480])
        cl.addWidget(splitter, stretch=1)

        root.addWidget(content, stretch=1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — Add your TfNSW API key via API Settings, then press Analyse")

    def _make_toolbar(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"QWidget {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px; }} QLabel {{ background: transparent; border: none; }}")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)

        cam_lbl = QLabel("📷  Camera:")
        cam_lbl.setStyleSheet(f"font-size: 13px; color: {C['text_mid']}; font-weight: 600;")

        self._combo = QComboBox()
        self._combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._combo.setMinimumWidth(280)
        self._combo.setMaximumWidth(420)
        self._populate_camera_combo()

        self._mode_ind = ModeIndicator()

        # Helper to create toolbar buttons consistently
        def btn(label, name, slot, checkable=False):
            b = QPushButton(label)
            b.setObjectName(name)
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            if checkable:
                b.setCheckable(True)
                b.toggled.connect(slot)
            else:
                b.clicked.connect(slot)
            return b

        self._analyse_btn  = btn("▶  Analyse",          "primary",   self._run)
        self._scan_btn     = btn("🔍  Find Live Camera", "secondary", self._scan_for_live_camera)
        self._auto_btn     = btn("⟳  Auto-refresh",     "secondary", self._toggle_auto, checkable=True)
        self._clear_btn    = btn("✕  Clear",             "secondary", self._clear)
        self._settings_btn = btn("⚙  API Settings",     "secondary", self._open_settings)

        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._run)

        lay.addWidget(cam_lbl)
        lay.addWidget(self._combo)
        lay.addWidget(self._analyse_btn)
        lay.addWidget(self._scan_btn)
        lay.addWidget(self._auto_btn)
        lay.addWidget(self._clear_btn)
        lay.addStretch()
        lay.addWidget(self._settings_btn)
        return w

    def _make_camera_panel(self) -> QWidget:
        # Left panel: original image and detection output side by side
        gb = QGroupBox("Camera Feed")
        lay = QVBoxLayout(gb)
        lay.setSpacing(10)

        col_row = QHBoxLayout()
        for txt in ("Original Camera Image", "Detection Output — Vehicles Highlighted"):
            lbl = QLabel(txt)
            lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            lbl.setStyleSheet(f"color: {C['text']}; background: transparent; border: none;")
            col_row.addWidget(lbl, stretch=1)
        lay.addLayout(col_row)

        img_row = QHBoxLayout()
        img_row.setSpacing(12)
        self._raw_panel = ImagePanel("No image loaded yet.\nPress Analyse to fetch the camera feed.")
        self._det_panel = ImagePanel("Detection output will appear here.\n\nColoured bounding boxes will highlight each detected vehicle.")
        img_row.addWidget(self._raw_panel)
        img_row.addWidget(self._det_panel)
        lay.addLayout(img_row, stretch=1)

        lay.addWidget(DetectionLegend())

        # Progress bar shown during detection
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(5)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"QProgressBar {{ background: {C['border']}; border-radius: 3px; border: none; }} QProgressBar::chunk {{ background: {C['blue']}; border-radius: 3px; }}")
        self._progress.setVisible(False)
        lay.addWidget(self._progress)
        return gb

    def _make_stats_panel(self) -> QWidget:
        # Right sidebar: total count, congestion level, vehicle cards, trend graph
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(14)

        # Total vehicle count
        total_gb = QGroupBox("Total Vehicles Detected")
        tl = QHBoxLayout(total_gb)
        self._total_lbl = QLabel("—")
        self._total_lbl.setFont(QFont("Segoe UI", 44, QFont.Bold))
        self._total_lbl.setStyleSheet(f"color: {C['text']}; border: none; background: transparent;")
        tl.addStretch()
        tl.addWidget(self._total_lbl)
        tl.addStretch()
        lay.addWidget(total_gb)

        # Congestion level with colour key
        cong_gb = QGroupBox("Traffic Congestion Level")
        cl2 = QVBoxLayout(cong_gb)
        cl2.setContentsMargins(0, 4, 0, 0)
        self._banner = CongestionBanner()
        cl2.addWidget(self._banner)

        key_row = QHBoxLayout()
        for level, colour, desc in [
            ("Low", C["low_border"], "< 20 vehicles"),
            ("Moderate", C["mod_border"], "20 – 49"),
            ("Heavy", C["heavy_border"], "50 +"),
        ]:
            pill = QWidget()
            pill.setFixedHeight(28)
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(8, 4, 8, 4)
            pl.setSpacing(6)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {colour}; font-size: 14px; background: transparent; border: none;")
            lbl = QLabel(f"{level}  {desc}")
            lbl.setStyleSheet(f"color: {C['text_mid']}; font-size: 11px; background: transparent; border: none;")
            pl.addWidget(dot)
            pl.addWidget(lbl)
            key_row.addWidget(pill)
        key_row.addStretch()
        cl2.addLayout(key_row)
        lay.addWidget(cong_gb)

        # Vehicle breakdown cards
        veh_gb = QGroupBox("Vehicle Breakdown")
        grid = QGridLayout(veh_gb)
        grid.setSpacing(10)
        self._cards = {}
        for i, (label, icon, colour) in enumerate(zip(VEHICLE_CLASSES, VEHICLE_ICONS, VEHICLE_COLOURS)):
            card = VehicleCard(label, icon, colour)
            self._cards[label] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addWidget(veh_gb)

        # Trend graph
        trend_gb = QGroupBox("Traffic Trend Over Time")
        trl = QVBoxLayout(trend_gb)
        trl.setContentsMargins(4, 4, 4, 4)
        help_lbl = QLabel("Each coloured line tracks one vehicle type across analysis runs.")
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(f"color: {C['text_soft']}; font-size: 11px; background: transparent; border: none;")
        trl.addWidget(help_lbl)
        self._trend = TrendGraph()
        trl.addWidget(self._trend, stretch=1)
        lay.addWidget(trend_gb, stretch=1)

        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _populate_camera_combo(self, cameras: list[dict] | None = None) -> None:
        # Fill dropdown with cameras from API or fallback demo list
        self._combo.blockSignals(True)
        self._combo.clear()
        if cameras:
            self._cameras = cameras
            for cam in cameras:
                region = cam.get("region", "")
                title  = cam.get("title", "Camera")
                self._combo.addItem(f"{region} — {title}" if region else title)
        else:
            self._cameras = []
            for name in [
                "Sydney CBD — George St", "Harbour Bridge — Northbound",
                "Harbour Bridge — Southbound", "M1 — Eastern Distributor",
                "M2 — Hills Motorway", "M4 — Western Motorway (Strathfield)",
                "M5 — South Western Motorway", "Lane Cove Tunnel (East Portal)",
                "Cross City Tunnel (William St)", "Parramatta Rd (Ashfield)",
            ]:
                self._combo.addItem(name)
        self._combo.blockSignals(False)

    def _current_camera_dict(self) -> dict:
        idx = self._combo.currentIndex()
        if 0 <= idx < len(self._cameras):
            return self._cameras[idx]
        return {"id": "", "title": self._combo.currentText(), "href": ""}

    def _refresh_mode_indicator(self) -> None:
        live = bool(self._cfg.get("api_key", "").strip() and REQUESTS_AVAILABLE)
        self._mode_ind.set_live() if live else self._mode_ind.set_demo()

    def _open_settings(self) -> None:
        dlg = ApiSettingsDialog(self._cfg, self)
        dlg.cameras_loaded.connect(self._on_cameras_loaded)
        dlg.exec_()
        self._cfg = load_config()
        self._refresh_mode_indicator()

    def _on_cameras_loaded(self, cameras: list[dict]) -> None:
        self._populate_camera_combo(cameras)
        self._status.showMessage(f"Loaded {len(cameras)} TfNSW cameras — press 'Find Live Camera' to auto-select one")

    def _scan_for_live_camera(self) -> None:
        # Start background scan to find first online camera
        if not self._cameras:
            self._status.showMessage("Load cameras from API Settings first, then scan.")
            return
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("🔍  Scanning…")
        self._status.showMessage(f"Scanning {len(self._cameras)} cameras for a live feed…")
        self._scanner = CameraScanWorker(self._cameras, self._cfg.get("api_key", "").strip())
        self._scanner.found.connect(self._on_scan_found)
        self._scanner.progress.connect(lambda msg: self._status.showMessage(msg))
        self._scanner.failed.connect(self._on_scan_failed)
        self._scanner.start()

    def _on_scan_found(self, idx: int, title: str) -> None:
        self._combo.setCurrentIndex(idx)
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("🔍  Find Live Camera")
        self._status.showMessage(f"Found live camera: {title} — running detection…")
        self._run()

    def _on_scan_failed(self) -> None:
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("🔍  Find Live Camera")
        self._status.showMessage("No live cameras found right now — try again later")

    def _run(self) -> None:
        # Start detection worker for selected camera
        if self._busy:
            return
        self._busy = True
        camera  = self._current_camera_dict()
        api_key = self._cfg.get("api_key", "").strip()
        conf    = float(self._cfg.get("conf_threshold", 0.15))

        self._analyse_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.showMessage(f"Analysing  {camera.get('title', '')} …  please wait")

        self._worker = DetectionWorker(camera, api_key, conf)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, r: dict) -> None:
        # Update all UI panels with detection results
        counts = r["counts"]
        total  = sum(counts.values())
        level  = "Low" if total < 20 else ("Moderate" if total < 50 else "Heavy")

        self._raw_panel.set_image(r["raw"])
        self._det_panel.set_image(r["det"])
        self._total_lbl.setText(str(total))
        self._banner.set_level(level)
        for k, card in self._cards.items():
            card.update_value(counts.get(k, 0))
        self._trend.push(counts)

        mode      = "LIVE"    if r.get("live")      else "DEMO"
        model_tag = "YOLOv8s" if r.get("has_model") else "demo boxes"
        ts = datetime.now().strftime("%H:%M:%S")
        self._status.showMessage(f"[{ts}]  {r['camera']}  ·  {total} vehicles  ·  Congestion: {level}  ·  {mode}  ·  {model_tag}")

        self._progress.setVisible(False)
        self._analyse_btn.setEnabled(True)
        self._busy = False

    def _on_error(self, msg: str) -> None:
        # Handle detection errors - skip offline cameras automatically
        self._progress.setVisible(False)
        self._analyse_btn.setEnabled(True)
        self._busy = False

        offline_hints = ["page not found", "temporarily unavailable", "404", "503", "no image url"]
        if any(h in msg.lower() for h in offline_hints):
            next_idx = self._combo.currentIndex() + 1
            if self._cameras and next_idx < len(self._cameras):
                self._combo.setCurrentIndex(next_idx)
                self._status.showMessage(f"Camera offline — skipping to: {self._cameras[next_idx].get('title', '')}…")
                self._run()
            else:
                self._status.showMessage("Camera offline — no more cameras to try. Use 'Find Live Camera' to scan.")
            return

        self._status.showMessage(f"Error — {msg[:120]}")
        QMessageBox.warning(self, "Detection Error",
                            f"An error occurred during detection:\n\n{msg}\n\nCheck your API key in API Settings.")

    def _toggle_auto(self, on: bool) -> None:
        # Toggle 30-second auto-refresh
        if on:
            self._auto_btn.setText("⟳  Auto-refresh ON  (30 s)")
            self._auto_timer.start(30_000)
            self._run()
        else:
            self._auto_btn.setText("⟳  Auto-refresh")
            self._auto_timer.stop()

    def _clear(self) -> None:
        # Reset all display panels
        self._raw_panel.clear_image()
        self._det_panel.clear_image()
        self._total_lbl.setText("—")
        self._banner.set_level("—")
        for card in self._cards.values():
            card.update_value(None)
        self._trend.reset()
        self._status.showMessage("Cleared — Select a camera and press Analyse")
