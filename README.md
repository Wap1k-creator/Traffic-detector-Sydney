# 🚦 Sydney Real-Time Traffic Detection System

A desktop application that connects to **live Transport for NSW traffic cameras** and detects vehicles in real time using a **custom-trained YOLOv8 model**. It counts cars, trucks, buses, and motorcycles per frame, classifies congestion levels, and tracks trends over time — all in a responsive PyQt5 dashboard.

<img width="977" height="575" alt="image" src="https://github.com/user-attachments/assets/972f30d4-4743-485d-b8a0-2ebd44e2cd3a" />


## Features

- **Live camera feeds** — pulls real-time imagery from 190+ TfNSW traffic cameras across Sydney via the [Transport for NSW Open Data API](https://opendata.transport.nsw.gov.au/)
- **Custom YOLOv8 detection** — uses a fine-tuned model (`best.pt`) trained for traffic scenes, with automatic fallback to pretrained `yolov8s`
- **SAHI sliced inference** — tiles each frame into overlapping slices so small, distant vehicles are still detected (a known weakness of standard full-frame detection)
- **Per-class vehicle counting** — cars, trucks, buses, motorcycles with colour-coded bounding boxes
- **Congestion analysis** — low / moderate / heavy classification with live trend graphs
- **Responsive UI** — detection runs on background worker threads so the interface never freezes during inference
- **Persistent settings** — API key, confidence threshold, and camera list saved between sessions

## Architecture

| Module | Responsibility |
|---|---|
| `app.py` | Entry point — bootstraps the Qt application |
| `dashboard.py` | Main window: toolbar, camera panel, stats panel |
| `detection.py` | Model loading, standard + SAHI sliced inference, per-class counting |
| `api.py` | TfNSW Open Data API client (camera list + image fetching) |
| `workers.py` | Background QThread workers for non-blocking detection |
| `widgets.py` | Custom widgets: image panel, congestion banner, trend graph |
| `dialogs.py` | API settings dialog |
| `config.py` | Load/save local settings (`config.json`) |
| `constants.py` | Colour palette, class maps, stylesheet, endpoints |

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> Python 3.13+ recommended. The first run downloads pretrained YOLO weights if the custom model is missing.

### 2. Get a free TfNSW API key

1. Create an account at [opendata.transport.nsw.gov.au](https://opendata.transport.nsw.gov.au/)
2. Create an application and subscribe to the **Live Traffic Cameras** API
3. Copy your API key

### 3. Run

```bash
python app.py
```

Click **API Settings**, paste your key, load the camera list, pick a camera, and press **Analyse**.

> Your API key is stored locally in `config.json`, which is gitignored and never committed.

## How detection works

1. The selected camera frame is fetched as an RGB image from the TfNSW CDN
2. If the custom model is present, standard YOLOv8 inference runs at 1280px
3. Otherwise, **SAHI** slices the frame into overlapping tiles (~half the image size, 20% overlap), runs detection on each tile plus the full frame, and merges results with greedy NMM post-processing — dramatically improving recall on small/distant vehicles
4. Detections are filtered by confidence, counted per class, and drawn with colour-coded boxes

## Tech Stack

Python · PyQt5 · Ultralytics YOLOv8 · SAHI · PyTorch · Pillow · NumPy · TfNSW Open Data API

## Collaborators

This was a collaborative project with [ReubenDiasAlberto](https://github.com/ReubenDiasAlberto).
