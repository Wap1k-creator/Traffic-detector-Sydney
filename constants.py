from pathlib import Path

# Colour palette used across the UI
C = {
    "page":        "#F0F2F5",
    "surface":     "#FFFFFF",
    "surface_alt": "#F8F9FB",
    "header_bg":   "#1A2332",
    "border":      "#D1D9E0",
    "border_dark": "#B0BBC7",
    "text":        "#111827",
    "text_mid":    "#4B5563",
    "text_soft":   "#9CA3AF",
    "text_inv":    "#FFFFFF",
    "blue":        "#2563EB",
    "blue_light":  "#DBEAFE",
    "blue_dark":   "#1D4ED8",
    "low_bg":      "#D1FAE5",
    "low_text":    "#065F46",
    "low_border":  "#10B981",
    "mod_bg":      "#FEF3C7",
    "mod_text":    "#92400E",
    "mod_border":  "#F59E0B",
    "heavy_bg":    "#FEE2E2",
    "heavy_text":  "#991B1B",
    "heavy_border":"#EF4444",
    "car":         "#2563EB",
    "truck":       "#7C3AED",
    "bus":         "#D97706",
    "moto":        "#059669",
}

# Vehicle class labels, colours and icons
VEHICLE_CLASSES = ["Cars", "Trucks", "Buses", "Motorcycles"]
VEHICLE_COLOURS = [C["car"], C["truck"], C["bus"], C["moto"]]
VEHICLE_ICONS   = ["🚗", "🚛", "🚌", "🏍"]

# COCO class ID to vehicle label mapping
COCO_VEHICLE_MAP = {2: "Cars", 3: "Motorcycles", 5: "Buses", 7: "Trucks"}
CUSTOM_CLASS_MAP = {0: "Cars", 1: "Trucks", 2: "Buses", 3: "Motorcycles"}

# COCO class name strings used by SAHI
COCO_NAME_MAP = {
    "car": "Cars", "truck": "Trucks",
    "bus": "Buses", "motorcycle": "Motorcycles",
}

# RGB colours for drawing bounding boxes
COLOUR_MAP_RGB = {
    "Cars":        ( 37,  99, 235),
    "Trucks":      (124,  58, 237),
    "Buses":       (217, 119,   6),
    "Motorcycles": (  5, 150, 105),
}

# TfNSW API endpoint
TFNSW_BASE       = "https://api.transport.nsw.gov.au"
CAMERAS_ENDPOINT = f"{TFNSW_BASE}/v1/live/cameras"

# Config file location
CONFIG_PATH = Path(__file__).parent / "config.json"

# Global Qt stylesheet
STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {C['page']};
    font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: {C['text']};
}}
QGroupBox {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    margin-top: 18px;
    padding: 12px 14px 14px 14px;
    font-size: 12px;
    font-weight: 600;
    color: {C['text_mid']};
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background: {C['surface']};
}}
QComboBox {{
    background: {C['surface']};
    border: 1.5px solid {C['border_dark']};
    border-radius: 7px;
    padding: 7px 32px 7px 12px;
    font-size: 13px;
    color: {C['text']};
    min-width: 220px;
}}
QComboBox:hover {{ border-color: {C['blue']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    selection-background-color: {C['blue_light']};
    selection-color: {C['blue_dark']};
    padding: 4px;
}}
QPushButton {{
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    border: none;
}}
QPushButton#primary {{
    background: {C['blue']};
    color: white;
}}
QPushButton#primary:hover  {{ background: {C['blue_dark']}; }}
QPushButton#primary:disabled {{ background: #93C5FD; color: #EFF6FF; }}
QPushButton#secondary {{
    background: {C['surface']};
    color: {C['text']};
    border: 1.5px solid {C['border_dark']};
}}
QPushButton#secondary:hover {{
    background: {C['blue_light']};
    border-color: {C['blue']};
    color: {C['blue_dark']};
}}
QPushButton#secondary:checked {{
    background: {C['blue_light']};
    border-color: {C['blue']};
    color: {C['blue_dark']};
}}
QLineEdit {{
    background: {C['surface']};
    border: 1.5px solid {C['border_dark']};
    border-radius: 7px;
    padding: 7px 12px;
    font-size: 13px;
    color: {C['text']};
}}
QLineEdit:focus {{ border-color: {C['blue']}; }}
QStatusBar {{
    background: {C['surface']};
    color: {C['text_mid']};
    border-top: 1px solid {C['border']};
    padding: 4px 12px;
    font-size: 12px;
}}
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C['border_dark']}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
