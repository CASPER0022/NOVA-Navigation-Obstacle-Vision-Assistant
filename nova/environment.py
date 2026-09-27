"""Camera-health checks. A detector that silently sees nothing is dangerous: in
the dark, with a covered or smeared lens, or on a frozen feed, "no alerts" would
otherwise sound exactly like "path clear". These checks make that failure audible.
"""
import cv2
import numpy as np

DARK_MEAN = 35          # mean grey level (0-255) below which the scene is too dark
BLOCKED_STD = 12        # near-uniform image: lens covered or pointing at a wall
BLUR_LAPLACIAN = 15.0   # variance of Laplacian below which the image is badly blurred
FROZEN_DIFF = 0.5       # mean abs diff between frames below which the feed looks frozen
FROZEN_SECONDS = 4.0
REPEAT_SECONDS = 30.0   # how often a persisting problem is re-announced

MESSAGES = {
    "dark": "It's very dark. I may miss obstacles.",
    "blocked": "Camera view looks blocked. Check the lens.",
    "blurry": "Camera image is blurry. I may miss obstacles.",
    "frozen": "Camera image is frozen. I may miss obstacles.",
    "ok": "Camera view is clear again.",
}


def assess_frame(frame):
    """Return 'dark', 'blocked', 'blurry' or None for a single BGR frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (160, 120), interpolation=cv2.INTER_AREA)
    mean, std = float(small.mean()), float(small.std())
    if mean < DARK_MEAN:
        return "dark"
    if std < BLOCKED_STD:
        return "blocked"
    if cv2.Laplacian(small, cv2.CV_64F).var() < BLUR_LAPLACIAN:
        return "blurry"
    return None


class EnvironmentMonitor:
    """Debounces per-frame assessments and reports state changes as speech."""

    def __init__(self, confirm_checks=3, check_frozen=True):
        self.confirm_checks = confirm_checks
        self.check_frozen = check_frozen
        self.state = None
        self._candidate = None
        self._candidate_count = 0
        self._last_announced = -REPEAT_SECONDS
        self._prev_small = None
        self._static_since = None

    def _frozen(self, frame, now):
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (80, 60)).astype(np.int16)
        prev, self._prev_small = self._prev_small, small
        if prev is None or float(np.abs(small - prev).mean()) > FROZEN_DIFF:
            self._static_since = None
            return False
        if self._static_since is None:
            self._static_since = now
        return now - self._static_since >= FROZEN_SECONDS

    def update(self, frame, now):
        """Call on each detector cycle. Returns a message to speak, or None."""
        problem = assess_frame(frame)
        if problem is None and self.check_frozen and self._frozen(frame, now):
            problem = "frozen"

        if problem == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate, self._candidate_count = problem, 1

        if self._candidate_count < self.confirm_checks:
            return None

        if problem != self.state:
            self.state = problem
            self._last_announced = now
            return MESSAGES[problem or "ok"]
        if problem is not None and now - self._last_announced >= REPEAT_SECONDS:
            self._last_announced = now
            return MESSAGES[problem]
        return None
