import json
from constants import CONFIG_PATH


def load_config() -> dict:
    # Load saved settings from disk, return defaults if missing
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"api_key": "", "conf_threshold": 0.15, "cameras": []}


def save_config(cfg: dict) -> None:
    # Write settings to disk as JSON
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
