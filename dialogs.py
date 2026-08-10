import json

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox,
)
from PyQt5.QtCore import pyqtSignal

from constants import C, CAMERAS_ENDPOINT
from config import save_config
from api import fetch_cameras, test_api_key, REQUESTS_AVAILABLE, _auth_headers
from detection import YOLO_AVAILABLE, YOLO_IMPORT_ERROR, SAHI_AVAILABLE

try:
    import requests as _requests
except ImportError:
    _requests = None


class ApiSettingsDialog(QDialog):
    # Settings dialog for API key, confidence threshold and camera loading
    cameras_loaded = pyqtSignal(list)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("API Settings — TfNSW Open Data")
        self.setMinimumWidth(560)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)

        # Instructions panel
        info = QLabel(
            "Enter your TfNSW Open Data API key below.\n"
            "Register free at: opendata.transport.nsw.gov.au\n"
            "  1. Sign in → top-right avatar → Applications\n"
            "  2. Click 'Add new application', give it any name\n"
            "  3. Copy the generated API key and paste it here."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {C['text_mid']}; font-size: 12px; background: {C['blue_light']}; border: 1px solid {C['blue']}; border-radius: 8px; padding: 10px;")
        lay.addWidget(info)

        # API key input
        lay.addWidget(QLabel("API Key:"))
        key_row = QHBoxLayout()
        self._key_edit = QLineEdit(cfg.get("api_key", ""))
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_edit.setPlaceholderText("Paste your TfNSW API key here…")
        self._show_cb = QCheckBox("Show")
        self._show_cb.toggled.connect(
            lambda on: self._key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        key_row.addWidget(self._key_edit)
        key_row.addWidget(self._show_cb)
        lay.addLayout(key_row)

        # Confidence threshold input
        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Detection confidence threshold (0.0 – 1.0):"))
        self._conf_edit = QLineEdit(str(cfg.get("conf_threshold", 0.15)))
        self._conf_edit.setFixedWidth(70)
        thresh_row.addWidget(self._conf_edit)
        thresh_row.addStretch()
        lay.addLayout(thresh_row)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color: {C['text_mid']}; font-size: 12px; min-height: 28px;")
        lay.addWidget(self._status_lbl)

        # Action buttons
        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setObjectName("secondary")
        self._test_btn.clicked.connect(self._test)

        self._load_btn = QPushButton("Load Cameras from API")
        self._load_btn.setObjectName("secondary")
        self._load_btn.clicked.connect(self._load_cameras)

        self._debug_btn = QPushButton("Show Raw API Response")
        self._debug_btn.setObjectName("secondary")
        self._debug_btn.clicked.connect(self._show_raw)

        save_btn = QPushButton("Save & Close")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(self._test_btn)
        btn_row.addWidget(self._load_btn)
        btn_row.addWidget(self._debug_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        # Model and SAHI status
        model_lbl = QLabel(self._model_status_text())
        model_lbl.setWordWrap(True)
        model_lbl.setStyleSheet(f"color: {C['text_mid']}; font-size: 11px; background: {C['surface_alt']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 8px;")
        lay.addWidget(model_lbl)

    def _model_status_text(self) -> str:
        if not YOLO_AVAILABLE:
            return f"⚠ YOLOv8 failed to load.\n  {YOLO_IMPORT_ERROR or 'unknown error'}\n\n  App will run in demo mode."
        sahi_str = "✓ SAHI sliced inference active" if SAHI_AVAILABLE else "⚠ SAHI not installed — pip install sahi"
        return f"✓ Running on YOLOv8s — pretrained on COCO dataset.\n  Detects: Cars · Trucks · Buses · Motorcycles\n  {sahi_str}"

    def _current_key(self) -> str:
        return self._key_edit.text().strip()

    def _test(self) -> None:
        key = self._current_key()
        if not key:
            self._set_status("Enter an API key first.", error=True)
            return
        if not REQUESTS_AVAILABLE:
            self._set_status("'requests' not installed — pip install requests", error=True)
            return
        self._test_btn.setEnabled(False)
        self._set_status("Testing connection…")
        QApplication.processEvents()
        ok, msg = test_api_key(key)
        self._set_status(("✓ " if ok else "✗ ") + msg, error=not ok)
        self._test_btn.setEnabled(True)

    def _load_cameras(self) -> None:
        key = self._current_key()
        if not key:
            self._set_status("Enter an API key first.", error=True)
            return
        self._load_btn.setEnabled(False)
        self._set_status("Fetching camera list…")
        QApplication.processEvents()
        try:
            cameras = fetch_cameras(key)
            self._set_status(f"✓ Loaded {len(cameras)} cameras from TfNSW API.")
            self._cfg["cameras"] = cameras
            save_config(self._cfg)
            self.cameras_loaded.emit(cameras)
        except Exception as exc:
            self._set_status(f"✗ {exc}", error=True)
        self._load_btn.setEnabled(True)

    def _save(self) -> None:
        key = self._current_key()
        try:
            conf = float(self._conf_edit.text().strip())
            conf = max(0.01, min(0.99, conf))
        except ValueError:
            conf = 0.15
        self._cfg["api_key"] = key
        self._cfg["conf_threshold"] = conf
        save_config(self._cfg)
        self.accept()

    def _show_raw(self) -> None:
        # Debug helper - shows raw JSON from first camera entry
        key = self._current_key()
        if not key:
            self._set_status("Enter an API key first.", error=True)
            return
        if not REQUESTS_AVAILABLE or _requests is None:
            self._set_status("'requests' not installed.", error=True)
            return
        try:
            resp = _requests.get(CAMERAS_ENDPOINT, headers=_auth_headers(key), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "features" in data:
                first = data["features"][0] if data["features"] else data
            elif isinstance(data, list):
                first = data[0] if data else {}
            else:
                first = data
            QMessageBox.information(self, "Raw API Response (first camera)",
                                    f"Use this to identify which field holds the image URL:\n\n{json.dumps(first, indent=2)[:2000]}")
        except Exception as exc:
            self._set_status(f"✗ {exc}", error=True)

    def _set_status(self, msg: str, error: bool = False) -> None:
        colour = C["heavy_text"] if error else C["low_text"]
        self._status_lbl.setStyleSheet(f"color: {colour}; font-size: 12px;")
        self._status_lbl.setText(msg)
