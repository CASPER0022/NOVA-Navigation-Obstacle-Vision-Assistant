"""NOVA: Navigation & Obstacle Vision Assistant - command-line entry point.

    python assistive_system.py                     # auto-select camera
    python assistive_system.py --camera 1          # (or legacy: python assistive_system.py 1)
    python assistive_system.py --input clip.mp4 --headless
    python assistive_system.py --units steps --verbosity minimal --save-config

Run with --help for every option. Preferences can also live in nova_config.json.
"""
import argparse
import json
import sys

from nova.config import load_settings, DEFAULT_CONFIG_PATH, UNITS, VERBOSITY_LEVELS


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="NOVA assistive navigation system")
    p.add_argument("camera_index", nargs="?", type=int, default=None,
                   help="(legacy positional form) camera index, same as --camera")
    p.add_argument("--config", default=None,
                   help=f"JSON settings file (default: {DEFAULT_CONFIG_PATH} if present)")
    p.add_argument("--save-config", action="store_true",
                   help="write the effective settings to the config file and exit")

    src = p.add_argument_group("input")
    src.add_argument("--camera", type=int, help="webcam index (skips auto-scan)")
    src.add_argument("--input", help="video file or image directory instead of a camera")
    src.add_argument("--headless", action="store_true", default=None,
                     help="no preview window")
    src.add_argument("--list-cameras", action="store_true", help="list working cameras and exit")
    src.add_argument("--log-dir", help="where metrics CSVs are written (default logs)")

    det = p.add_argument_group("detection")
    det.add_argument("--model", help="YOLO weights (default yolov8n.pt)")
    det.add_argument("--confidence", type=float, help="detector confidence threshold")
    det.add_argument("--hfov", dest="camera_hfov_deg", type=float,
                     help="camera horizontal field of view in degrees (default 60)")
    det.add_argument("--inference-interval", type=float,
                     help="seconds between detector runs (default 0.25; 0 = every frame)")

    out = p.add_argument_group("speech & audio")
    out.add_argument("--units", choices=UNITS)
    out.add_argument("--verbosity", choices=VERBOSITY_LEVELS)
    out.add_argument("--rate", dest="speech_rate", type=int, help="speech rate, words per minute")
    out.add_argument("--voice", help="part of a system voice name, e.g. Zira or David")
    out.add_argument("--list-voices", action="store_true", help="list installed voices and exit")
    out.add_argument("--no-earcons", dest="earcons", action="store_false", default=None)
    out.add_argument("--no-traffic-lights", dest="traffic_lights", action="store_false",
                     default=None)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.list_cameras:
        from nova.capture import list_cameras
        print("Working camera indices:", list_cameras() or "none")
        return 0
    if args.list_voices:
        from nova.audio import Pyttsx3Backend
        for name, voice_id in Pyttsx3Backend.list_voices():
            print(f"{name}  ({voice_id})")
        return 0

    overrides = {k: v for k, v in vars(args).items()
                 if k not in ("camera_index", "config", "save_config", "list_cameras",
                              "list_voices")}
    if overrides.get("camera") is None:
        overrides["camera"] = args.camera_index
    try:
        settings = load_settings(args.config, overrides, allow_missing=args.save_config)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"Configuration error: {e}")
        return 2

    config_path = args.config or DEFAULT_CONFIG_PATH
    if args.save_config:
        data = settings.to_dict()
        for transient in ("camera", "input", "headless"):
            data.pop(transient)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved settings to {config_path}")
        return 0

    from nova.app import NovaApp  # heavy imports (torch, cv2) only when actually running
    return NovaApp(settings, config_path=config_path).run()


if __name__ == "__main__":
    sys.exit(main())
