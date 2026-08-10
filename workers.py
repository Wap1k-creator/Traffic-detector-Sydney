import random
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from constants import VEHICLE_CLASSES
from detection import load_model, run_detection
from api import fetch_camera_image_rgb, REQUESTS_AVAILABLE

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BaseWorker(QThread):
    # Base class for background workers - provides shared stop logic
    def __init__(self):
        super().__init__()

    def safe_stop(self) -> None:
        # Gracefully stop the thread
        self.quit()
        self.wait(3000)


class CameraScanWorker(BaseWorker):
    # Scans cameras one by one and finds the first live one
    found    = pyqtSignal(int, str)
    progress = pyqtSignal(str)
    failed   = pyqtSignal()

    def __init__(self, cameras: list[dict], api_key: str):
        super().__init__()
        self.cameras = cameras
        self.api_key = api_key

    def run(self) -> None:
        if not _REQUESTS_OK:
            self.failed.emit()
            return

        for i, cam in enumerate(self.cameras):
            href  = cam.get("href", "")
            title = cam.get("title", f"Camera {i}")
            if not href:
                continue

            self.progress.emit(f"Checking {i + 1}/{len(self.cameras)}: {title}…")
            try:
                resp = _requests.get(href, headers={"User-Agent": _BROWSER_UA},
                                     timeout=6, allow_redirects=True)
                if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
                    self.found.emit(i, title)
                    return
            except Exception:
                continue

        self.failed.emit()


class DetectionWorker(BaseWorker):
    # Fetches camera image and runs YOLOv8s detection in background thread
    result_ready = pyqtSignal(dict)
    error        = pyqtSignal(str)

    def __init__(self, camera: dict, api_key: str, conf: float = 0.15):
        super().__init__()
        self.camera  = camera
        self.api_key = api_key
        self.conf    = conf

    def run(self) -> None:
        try:
            title = self.camera.get("title", "Unknown camera")
            href  = self.camera.get("href", "")
            live  = bool(self.api_key and href and REQUESTS_AVAILABLE)

            # Fetch image from TfNSW camera or use blank demo image
            if live:
                raw_rgb = fetch_camera_image_rgb(self.api_key, href)
            else:
                raw_rgb = np.full((480, 640, 3), 210, dtype=np.uint8)
                raw_rgb[230:250, :] = [180, 180, 180]

            # Run detection
            model, is_custom = load_model()

            if model is not None:
                det_rgb, counts = run_detection(model, raw_rgb, is_custom, self.conf)
            else:
                det_rgb, counts = self._demo_boxes(raw_rgb)

            self.result_ready.emit({
                "counts":    counts,
                "raw":       raw_rgb,
                "det":       det_rgb,
                "camera":    title,
                "live":      live,
                "has_model": model is not None,
            })

        except Exception as exc:
            self.error.emit(str(exc))

    @staticmethod
    def _demo_boxes(raw_rgb: np.ndarray) -> tuple[np.ndarray, dict]:
        # Fallback demo boxes when model is unavailable
        counts = {
            "Cars":        random.randint(5, 25),
            "Trucks":      random.randint(0,  8),
            "Buses":       random.randint(0,  4),
            "Motorcycles": random.randint(0,  6),
        }
        box_cols = [(37, 99, 235), (124, 58, 237), (217, 119, 6), (5, 150, 105)]
        det = raw_rgb.copy()
        h, w = det.shape[:2]
        for i in range(sum(counts.values())):
            cx, cy = random.randint(60, w - 60), random.randint(40, h - 40)
            bw, bh = random.randint(40, 90), random.randint(22, 48)
            col = box_cols[i % len(box_cols)]
            det[cy - bh:cy + bh, cx - bw:cx + bw] = [c // 2 + 110 for c in col]
            det[cy - bh:cy - bh + 3, cx - bw:cx + bw] = col
            det[cy + bh - 3:cy + bh, cx - bw:cx + bw] = col
            det[cy - bh:cy + bh, cx - bw:cx - bw + 3] = col
            det[cy - bh:cy + bh, cx + bw - 3:cx + bw] = col
        return det, counts
