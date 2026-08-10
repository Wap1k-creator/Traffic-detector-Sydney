import io
import numpy as np
from constants import CAMERAS_ENDPOINT

# Optional dependencies
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Browser user-agent required by TfNSW webcam CDN
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"apikey {api_key}", "Accept": "application/json"}


def fetch_cameras(api_key: str) -> list[dict]:
    # Fetch camera list from TfNSW Open Data API
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests not installed — pip install requests")

    resp = requests.get(CAMERAS_ENDPOINT, headers=_auth_headers(api_key), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Parse GeoJSON FeatureCollection response
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        raw_list = data.get("features", [])
    elif isinstance(data, dict):
        raw_list = data.get("cameras", data.get("features", [data]))
    else:
        raw_list = data

    cameras = []
    for item in raw_list:
        props = item.get("properties", {}) if item.get("type") == "Feature" else item
        href = (
            props.get("href") or props.get("image_url") or props.get("imageUrl")
            or props.get("image") or props.get("url") or ""
        )
        cameras.append({
            "id":     props.get("id", ""),
            "title":  props.get("title") or props.get("name") or props.get("description") or "Camera",
            "region": props.get("region") or props.get("suburb") or "",
            "href":   href,
        })

    return cameras


def test_api_key(api_key: str) -> tuple[bool, str]:
    # Quick connectivity check
    try:
        cameras = fetch_cameras(api_key)
        return True, f"Connected — {len(cameras)} cameras available"
    except Exception as exc:
        return False, str(exc)


def fetch_camera_image_rgb(api_key: str, href: str) -> np.ndarray:
    # Download camera image and return as RGB numpy array
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests not installed — pip install requests")
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow not installed — pip install pillow")
    if not href:
        raise ValueError("No image URL for this camera. Load cameras via API Settings.")

    # Try multiple auth strategies — CDN needs browser UA, not API key header
    attempts = [
        {"headers": {"User-Agent": _BROWSER_UA}, "params": {}},
        {"headers": {"Authorization": f"apikey {api_key}", "User-Agent": _BROWSER_UA}, "params": {}},
        {"headers": {"User-Agent": _BROWSER_UA}, "params": {"apikey": api_key}},
    ]

    last_error = ""
    for attempt in attempts:
        try:
            resp = requests.get(href, headers=attempt["headers"], params=attempt["params"],
                                timeout=15, allow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and len(resp.content) < 500:
                try:
                    last_error = str(resp.json().get("message", resp.json()))
                except Exception:
                    last_error = resp.text[:200]
                continue

            img = PILImage.open(io.BytesIO(resp.content)).convert("RGB")
            return np.array(img)

        except PILImage.UnidentifiedImageError:
            last_error = f"Non-image response ({len(resp.content)} bytes)"
            continue
        except requests.HTTPError as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(
        f"Could not fetch image.\nURL: {href}\nError: {last_error}\n\n"
        "Check your API key and ensure the camera is online."
    )
