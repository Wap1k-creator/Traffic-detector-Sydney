from pathlib import Path
import numpy as np

from constants import (
    VEHICLE_CLASSES, COCO_VEHICLE_MAP, CUSTOM_CLASS_MAP,
    COCO_NAME_MAP, COLOUR_MAP_RGB,
)

# Import torch and YOLO before PyQt5 to avoid DLL conflicts on Windows
try:
    import torch
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    YOLO_IMPORT_ERROR = ""
except Exception as _yolo_exc:
    YOLO_AVAILABLE = False
    YOLO_IMPORT_ERROR = str(_yolo_exc)

# SAHI import for sliced inference
try:
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction
    SAHI_AVAILABLE = True
except ImportError:
    SAHI_AVAILABLE = False

# PIL for image drawing
try:
    from PIL import Image as PILImage, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Model caches to avoid reloading on every detection
_model_cache      = {"model": None, "is_custom": False}
_sahi_model_cache = {"model": None, "path": None}


CUSTOM_MODEL_PATH = str(Path(__file__).parent / "best (2).pt")


def _get_model_path(is_custom: bool = False) -> str:
    if is_custom or Path(CUSTOM_MODEL_PATH).exists():
        return CUSTOM_MODEL_PATH
    return "yolov8s.pt"


def load_model():
    # Return cached model if already loaded
    if _model_cache["model"] is not None:
        return _model_cache["model"], _model_cache["is_custom"]

    if not YOLO_AVAILABLE:
        return None, False

    # Prefer custom best.pt if present, fall back to yolov8s pretrained
    use_custom = Path(CUSTOM_MODEL_PATH).exists()
    model_path = CUSTOM_MODEL_PATH if use_custom else "yolov8s.pt"
    try:
        model = YOLO(model_path)
        _model_cache["model"] = model
        _model_cache["is_custom"] = use_custom
        return model, use_custom
    except Exception:
        return None, False


def load_sahi_model(model_path: str):
    # Return cached SAHI model if already loaded for this path
    if not SAHI_AVAILABLE:
        return None
    if _sahi_model_cache["model"] is not None and _sahi_model_cache["path"] == model_path:
        return _sahi_model_cache["model"]
    try:
        # Load with very low confidence - we filter manually later
        sahi_model = AutoDetectionModel.from_pretrained(
            model_type="ultralytics",
            model_path=model_path,
            confidence_threshold=0.01,
            device="cpu",
        )
        _sahi_model_cache["model"] = sahi_model
        _sahi_model_cache["path"] = model_path
        return sahi_model
    except Exception as exc:
        print(f"SAHI model load failed: {exc}")
        return None


def run_detection(model, rgb_array: np.ndarray, is_custom: bool, conf: float = 0.15):
    # Custom model uses standard inference (SAHI causes duplicate boxes with fine-tuned weights)
    if is_custom:
        return _run_standard(model, rgb_array, is_custom, conf)
    if SAHI_AVAILABLE and PIL_AVAILABLE:
        try:
            return _run_sahi(is_custom, rgb_array, conf)
        except Exception as exc:
            print(f"SAHI failed, using standard: {exc}")
    return _run_standard(model, rgb_array, is_custom, conf)


def _run_standard(model, rgb_array: np.ndarray, is_custom: bool, conf: float):
    # Convert RGB to BGR for YOLO, run prediction, convert back
    bgr = rgb_array[:, :, ::-1].copy()
    classes = list(CUSTOM_CLASS_MAP.keys() if is_custom else COCO_VEHICLE_MAP.keys())
    results = model.predict(source=bgr, conf=conf, imgsz=1280, classes=classes, verbose=False)
    result  = results[0]
    annotated_rgb = result.plot()[:, :, ::-1]

    # Count detections per vehicle class
    class_map = CUSTOM_CLASS_MAP if is_custom else COCO_VEHICLE_MAP
    counts = {k: 0 for k in VEHICLE_CLASSES}
    cls_ids = result.boxes.cls.cpu().numpy().astype(int) if result.boxes else []
    for cls_id in cls_ids:
        label = class_map.get(cls_id)
        if label:
            counts[label] += 1

    return annotated_rgb, counts


def _run_sahi(is_custom: bool, rgb_array: np.ndarray, conf: float):
    # SAHI sliced inference - splits image into tiles for better small object detection
    model_path = _get_model_path(is_custom)
    sahi_model = load_sahi_model(model_path)
    if sahi_model is None:
        raise RuntimeError("SAHI model could not be loaded")

    pil_image = PILImage.fromarray(rgb_array)
    h, w = rgb_array.shape[:2]

    # Calculate tile size based on image dimensions
    slice_w = max(320, w // 2)
    slice_h = max(320, h // 2)

    result = get_sliced_prediction(
        pil_image,
        sahi_model,
        slice_height=slice_h,
        slice_width=slice_w,
        overlap_height_ratio=0.2,
        overlap_width_ratio=0.2,
        perform_standard_pred=True,
        postprocess_type="GREEDYNMM",
        postprocess_match_threshold=0.5,
        verbose=0,
    )

    # Class name map for filtering predictions
    name_map = (
        {"cars": "Cars", "car": "Cars", "trucks": "Trucks", "truck": "Trucks",
         "buses": "Buses", "bus": "Buses", "motorcycles": "Motorcycles", "motorcycle": "Motorcycles"}
        if is_custom else COCO_NAME_MAP
    )

    # Filter by confidence threshold and vehicle classes only
    counts = {k: 0 for k in VEHICLE_CLASSES}
    kept = []
    for pred in result.object_prediction_list:
        if pred.score.value < conf:
            continue
        label = name_map.get(pred.category.name.lower())
        if label:
            counts[label] += 1
            kept.append((pred, label))

    # Draw bounding boxes and labels onto image
    annotated = PILImage.fromarray(rgb_array.copy())
    draw = ImageDraw.Draw(annotated)

    for pred, label in kept:
        colour = COLOUR_MAP_RGB[label]
        x1, y1 = int(pred.bbox.minx), int(pred.bbox.miny)
        x2, y2 = int(pred.bbox.maxx), int(pred.bbox.maxy)

        draw.rectangle([x1, y1, x2, y2], outline=colour, width=2)

        tag = f"{pred.category.name} {pred.score.value:.2f}"
        try:
            tb = draw.textbbox((x1, y1), tag)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
        except AttributeError:
            tw, th = draw.textsize(tag)
        ty = max(0, y1 - th - 4)
        draw.rectangle([x1, ty, x1 + tw + 4, ty + th + 4], fill=colour)
        draw.text((x1 + 2, ty + 2), tag, fill=(255, 255, 255))

    return np.array(annotated), counts
