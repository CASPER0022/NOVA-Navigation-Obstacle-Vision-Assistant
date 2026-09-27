"""Traffic-light colour reading via HSV thresholds inside YOLO's box.

This is an *aid*, not a crossing signal: lighting, angle and pedestrian vs.
vehicle lights all confuse it. Phrasing says "appears" deliberately, and the
README tells users never to cross on this alone.
"""
import cv2
import numpy as np

# OpenCV hue is 0-179. Red wraps around 0.
HUE_RANGES = {
    "red": [(0, 10), (165, 179)],
    "yellow": [(15, 35)],
    "green": [(40, 95)],
}
MIN_SATURATION = 90
MIN_VALUE = 130
MIN_LIT_FRACTION = 0.03


def classify_light(frame, bbox):
    """Return 'red', 'yellow', 'green' or None for the light inside bbox."""
    x1, y1, x2, y2 = (int(v) for v in bbox)
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 4 or y2 - y1 < 6:
        return None
    hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lit = (sat >= MIN_SATURATION) & (val >= MIN_VALUE)
    total = lit.size

    scores = {}
    for color, ranges in HUE_RANGES.items():
        mask = np.zeros_like(lit)
        for lo, hi in ranges:
            mask |= (hue >= lo) & (hue <= hi)
        scores[color] = int(np.count_nonzero(mask & lit))

    best = max(scores, key=scores.get)
    if scores[best] / total < MIN_LIT_FRACTION:
        return None
    return best


class TrafficLightMonitor:
    """Annotates traffic-light detections with their colour and reports
    confirmed changes of the nearest light."""

    def __init__(self, confirm_checks=2):
        self.confirm_checks = confirm_checks
        self.state = None
        self._candidate = None
        self._count = 0

    def update(self, frame, detections):
        lights = [d for d in detections if d.label == "traffic light"]
        for d in lights:
            d.extra["light_state"] = classify_light(frame, d.bbox)
        if not lights:
            self.state = self._candidate = None
            self._count = 0
            return None

        nearest = min(lights, key=lambda d: d.distance)
        observed = nearest.extra["light_state"]
        if observed is None:
            return None
        if observed == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = observed, 1
        if self._count >= self.confirm_checks and observed != self.state:
            changed = self.state is not None
            self.state = observed
            verb = "changed to" if changed else "appears"
            return f"Traffic light at {nearest.clock} o'clock {verb} {observed}."
        return None
