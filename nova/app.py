"""NOVA main loop: capture -> detect -> track -> decide -> speak."""
import json
import os
import time
from collections import deque

import cv2

from metrics_logger import MetricsLogger

from . import hud
from .alerts import AlertPolicy, CRITICAL, WARNING, INFO, URGENCY_NAMES
from .audio import (Speech, Pyttsx3Backend, Earcons,
                    CRITICAL_PRIORITY, NORMAL_PRIORITY, LOW_PRIORITY)
from .capture import FrameSource
from .config import UNITS, VERBOSITY_LEVELS
from .controls import KeyboardControls, HELP_TEXT
from .environment import EnvironmentMonitor
from .perception import CameraGeometry, Detector
from .scene import describe_scene, describe_path
from .tracker import Tracker
from .traffic_light import TrafficLightMonitor

SPEECH_PRIORITY = {CRITICAL: CRITICAL_PRIORITY, WARNING: NORMAL_PRIORITY, INFO: LOW_PRIORITY}
PAUSE_REMINDER_SECONDS = 60.0
PERSISTED_PREFERENCES = ("verbosity", "units", "speech_rate")


class NovaApp:
    def __init__(self, settings, config_path=None):
        self.s = settings
        self.config_path = config_path
        self.metrics = MetricsLogger(settings.log_dir)
        self.speech = Speech(Pyttsx3Backend(settings.speech_rate, settings.volume, settings.voice),
                             metrics=self.metrics)
        self.earcons = Earcons(settings.earcons)
        self.controls = KeyboardControls()
        self.policy = AlertPolicy(settings)
        self.tracker = Tracker()
        self.lights = TrafficLightMonitor() if settings.traffic_lights else None
        self.detector = None
        self.env = None
        self.detections = []
        self.paused = False
        self.running = True
        self.preferences_changed = False
        self._geometry = None
        self._last_inference = 0.0
        self._last_pause_reminder = 0.0

    # ------------------------------------------------------------------ speech
    def announce(self, text, priority=NORMAL_PRIORITY, force=True, earcon=None):
        print(f"NOVA: {text}")
        if earcon:
            self.earcons.play(earcon)
        self.speech.say(text, priority, force=force)
        self.policy.note_spoken(time.time())

    def _deliver(self, ann, inference_duration):
        kind = "path_clear" if ann.kind == "path_clear" else URGENCY_NAMES[ann.urgency]
        print(f"[{kind}] {ann.text}")
        self.earcons.play(kind, ann.pan)
        self.speech.say(ann.text, SPEECH_PRIORITY[ann.urgency])
        if ann.detection is not None:
            self.metrics.log_alert_latency(ann.detection.label, ann.detection.first_seen,
                                           time.time(), inference_duration)

    # ---------------------------------------------------------------- commands
    def handle(self, command):
        s = self.s
        if command == "describe":
            prefix = "Paused. Last seen: " if self.paused else ""
            self.announce(prefix + describe_scene(self.detections, s))
        elif command == "ahead":
            self.announce(describe_path(self.detections, s))
        elif command == "repeat":
            self.speech.repeat_last()
        elif command == "quiet":
            self.speech.quiet = not self.speech.quiet
            self.announce("Quiet mode on. Only urgent warnings." if self.speech.quiet
                          else "Quiet mode off.")
        elif command == "pause":
            self.paused = not self.paused
            self.policy.reset()
            self.tracker = Tracker()
            self._last_pause_reminder = time.time()
            self.announce("Paused. Obstacle warnings are off. Press P to resume." if self.paused
                          else "Resumed. Monitoring the path ahead.", CRITICAL_PRIORITY)
        elif command == "verbosity":
            s.verbosity = _cycle(VERBOSITY_LEVELS, s.verbosity)
            self.preferences_changed = True
            self.announce(f"Detail level {s.verbosity}.")
        elif command == "units":
            s.units = _cycle(UNITS, s.units)
            self.preferences_changed = True
            self.announce(f"Distances in {s.units}.")
        elif command in ("faster", "slower"):
            rate = self.speech.change_rate(25 if command == "faster" else -25)
            s.speech_rate = rate
            self.preferences_changed = True
            self.announce("Faster." if command == "faster" else "Slower.")
        elif command == "help":
            self.announce(HELP_TEXT)
        elif command == "quit":
            self.running = False

    # -------------------------------------------------------------------- loop
    def run(self):
        s = self.s
        self.announce("Starting NOVA.", CRITICAL_PRIORITY)
        self.detector = Detector(s.model, s.confidence)
        self.detector.warmup()
        try:
            source = FrameSource(s, on_status=lambda t: self.announce(t, CRITICAL_PRIORITY))
        except RuntimeError as e:
            self.announce(f"{e}. Cannot start.", CRITICAL_PRIORITY)
            self.shutdown(None)
            return 1
        if s.environment_checks:
            self.env = EnvironmentMonitor(check_frozen=not source.is_image_dir)
        self.controls.start()
        self.announce("NOVA ready. Monitoring the path ahead. Press H for help, Q to quit.")

        # Recorded input is read far faster than real time; analyse every frame so
        # offline runs are deterministic instead of skipping most of the clip.
        interval = s.inference_interval if source.is_live else 0.0
        frame_times = deque(maxlen=60)
        last_fps_log = 0.0
        fps = 0.0
        try:
            while self.running:
                frame = source.read()
                if frame is None:
                    if not source.is_live:
                        self.announce("End of recording.")
                    break
                now = time.time()

                frame_times.append(now)
                if len(frame_times) >= 2 and frame_times[-1] > frame_times[0]:
                    fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])
                    if now - last_fps_log >= 1.0:
                        self.metrics.log_fps_sample(fps)
                        last_fps_log = now

                for command in self.controls.drain():
                    self.handle(command)
                if not self.running:
                    break

                if self.paused:
                    if now - self._last_pause_reminder >= PAUSE_REMINDER_SECONDS:
                        self._last_pause_reminder = now
                        self.announce("NOVA is paused. Press P to resume.", LOW_PRIORITY)
                elif now - self._last_inference >= interval:
                    self._last_inference = now
                    self._process(frame, now)

                if not s.headless:
                    self._show(frame, fps)
        except KeyboardInterrupt:
            print("\nStop requested.")
        finally:
            self.shutdown(source)
        return 0

    def _process(self, frame, now):
        h, w = frame.shape[:2]
        if self._geometry is None or (self._geometry.width, self._geometry.height) != (w, h):
            self._geometry = CameraGeometry(w, h, self.s.camera_hfov_deg)

        started = time.time()
        detections = self.detector.detect(frame, self._geometry, self.s.corridor_half_width)
        inference_duration = time.time() - started
        self.tracker.update(detections, now)
        self.detections = detections

        if self.env:
            message = self.env.update(frame, now)
            if message:
                self.announce(message, NORMAL_PRIORITY, earcon="warning")
        if self.lights:
            message = self.lights.update(frame, detections)
            if message:
                self.announce(message, NORMAL_PRIORITY, force=False, earcon="info")

        announcement = self.policy.update(detections, now)
        if announcement:
            self._deliver(announcement, inference_duration)

    def _show(self, frame, fps):
        flags = []
        if self.paused:
            flags.append("PAUSED")
        if self.speech.quiet:
            flags.append("QUIET")
        if self.env and self.env.state:
            flags.append(self.env.state.upper())
        status = (f"FPS {fps:4.1f} | {self.s.verbosity} | {self.s.units} | "
                  f"rate {self.speech.backend.rate} " + " ".join(flags))
        if self._geometry is not None:
            hud.draw(frame, [] if self.paused else self.detections, self._geometry, self.s, status)
        cv2.imshow("NOVA", frame)
        key = cv2.waitKey(1) & 0xFF
        if key != 255:
            self.controls.feed_key(chr(key))

    def shutdown(self, source):
        self.controls.stop()
        print("NOVA: Shutting down.")
        self.speech.say("Shutting down.", CRITICAL_PRIORITY, force=True)
        self.speech.wait_idle(timeout=5.0)
        if source is not None:
            source.release()
        cv2.destroyAllWindows()
        self.metrics.close()
        if self.preferences_changed and self.config_path:
            save_preferences(self.s, self.config_path)


def _cycle(options, current):
    return options[(options.index(current) + 1) % len(options)]


def save_preferences(settings, path):
    """Persist keyboard-adjusted preferences so they survive a restart."""
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    for key in PERSISTED_PREFERENCES:
        data[key] = getattr(settings, key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved preferences to {path}")
