"""User-tunable settings.

Defaults live on the Settings dataclass. A JSON file (``nova_config.json`` by
default, see ``nova_config.example.json``) can override any of them, and CLI
flags override the file. Keeping preferences in a file matters for blind users:
they shouldn't have to re-type long command lines every time they start NOVA.
"""
import json
import os
from dataclasses import dataclass, asdict, fields

DEFAULT_CONFIG_PATH = "nova_config.json"

UNITS = ("meters", "steps", "feet")
VERBOSITY_LEVELS = ("minimal", "normal", "detailed")


@dataclass
class Settings:
    # --- Input -----------------------------------------------------------
    camera: int = None          # None = auto-scan
    input: str = None           # video file or image directory instead of a camera
    headless: bool = False      # no preview window

    # --- Detection -------------------------------------------------------
    model: str = "yolov8n.pt"
    confidence: float = 0.40
    inference_interval: float = 0.25   # seconds between detector runs
    camera_hfov_deg: float = 60.0      # horizontal field of view; drives clock + distance geometry

    # --- Safety thresholds (meters / seconds) ------------------------------
    critical_distance: float = 1.2
    warning_distance: float = 2.5
    max_alert_distance: float = 6.0
    corridor_half_width: float = 0.5   # half the width of the walking path in front of the user
    critical_ttc: float = 2.0          # time-to-contact below which an approaching object is critical

    # --- Speech & audio --------------------------------------------------
    speech_rate: int = 175
    voice: str = None                  # substring of a system voice name, e.g. "Zira"
    volume: float = 1.0
    earcons: bool = True
    units: str = "meters"
    step_length: float = 0.7           # meters per step, used when units == "steps"
    verbosity: str = "normal"
    path_clear_interval: float = 20.0

    # --- Extras ----------------------------------------------------------
    traffic_lights: bool = True
    environment_checks: bool = True
    log_dir: str = "logs"

    def validate(self):
        if self.units not in UNITS:
            raise ValueError(f"units must be one of {UNITS}, got {self.units!r}")
        if self.verbosity not in VERBOSITY_LEVELS:
            raise ValueError(f"verbosity must be one of {VERBOSITY_LEVELS}, got {self.verbosity!r}")
        if not 10 <= self.camera_hfov_deg <= 170:
            raise ValueError("camera_hfov_deg must be between 10 and 170")
        if not 0 < self.critical_distance < self.warning_distance <= self.max_alert_distance:
            raise ValueError("need 0 < critical_distance < warning_distance <= max_alert_distance")
        if self.inference_interval < 0:
            raise ValueError("inference_interval must be >= 0")
        return self

    def to_dict(self):
        return asdict(self)


def load_settings(path=None, overrides=None, allow_missing=False):
    """Build Settings from defaults <- JSON file <- overrides (None values ignored).

    An explicitly given path must exist unless allow_missing (used when about to
    create it); the default path is always optional.
    """
    settings = Settings()
    known = {f.name for f in fields(Settings)}

    config_path = path or DEFAULT_CONFIG_PATH
    must_exist = path is not None and not allow_missing
    if must_exist or os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown setting(s) in {config_path}: {sorted(unknown)}")
        for key, value in data.items():
            setattr(settings, key, value)

    for key, value in (overrides or {}).items():
        if key in known and value is not None:
            setattr(settings, key, value)

    return settings.validate()
