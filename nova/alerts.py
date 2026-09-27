"""Alert policy: decides *what* to say and *when*.

The detector produces many boxes per second; a blind user can absorb maybe one
short phrase every second or two. This module ranks hazards by urgency, keeps
per-object state so the same thing isn't repeated, and emits at most one
Announcement per detector cycle.

Urgency levels:
  CRITICAL  something in the walking path within critical_distance, or on a
            collision course (time-to-contact below critical_ttc). Interrupts speech.
  WARNING   in the path within warning_distance, very close off to the side, or
            an approaching vehicle.
  INFO      anything else within max_alert_distance (filtered by verbosity).
"""
import math
from dataclasses import dataclass

from .perception import PERSON, VEHICLE, ANIMAL, SIGNAL
from .phrasing import object_phrase, capitalize
from .tracker import iou

CRITICAL, WARNING, INFO = 0, 1, 2
URGENCY_NAMES = {CRITICAL: "critical", WARNING: "warning", INFO: "info"}

APPROACH_SPEED = 0.35       # m/s closing speed that counts as "approaching"
MIN_HITS = 2                # detector runs an object must survive before a non-critical alert
REMINDER_INTERVAL = 6.0     # seconds before the (single) critical repeat
MIN_GAP = {CRITICAL: 0.0, WARNING: 1.5, INFO: 3.0}  # min seconds since last speech
PATH_CLEAR_DEBOUNCE = 3.0
# The detector often loses an object for a moment or relabels it (TV -> laptop).
# A new track that overlaps something announced within REACQUIRE_SECONDS is
# treated as the same object, so it doesn't get announced all over again.
REACQUIRE_SECONDS = 3.0
REACQUIRE_IOU = 0.3


@dataclass
class Announcement:
    text: str
    urgency: int
    kind: str = "hazard"     # hazard | path_clear | status
    pan: float = 0.0         # -1 (left) .. 1 (right), for spatial earcons
    detection: object = None


def is_approaching(det):
    return det.closing_speed >= APPROACH_SPEED


def classify(det, s):
    """Return the urgency level of a detection, or None if it's not worth mentioning."""
    if det.category == SIGNAL:
        return INFO if det.distance <= s.max_alert_distance * 2 else None
    if det.in_path and det.distance < s.critical_distance:
        return CRITICAL
    if is_approaching(det) and det.ttc < s.critical_ttc and (det.in_path or abs(det.angle) < 15):
        return CRITICAL
    if det.in_path and det.distance < s.warning_distance:
        return WARNING
    if det.distance < s.critical_distance:
        return WARNING
    if det.category == VEHICLE and is_approaching(det) and det.distance <= s.max_alert_distance:
        return WARNING
    if det.distance <= s.max_alert_distance:
        return INFO
    return None


def passes_verbosity(det, urgency, verbosity):
    if urgency <= WARNING:
        return True
    if verbosity == "minimal":
        return False
    if verbosity == "normal":
        return det.in_path or det.category in (PERSON, VEHICLE, ANIMAL)
    return True


def pan_for(det, hfov_deg=60.0):
    return max(-1.0, min(1.0, det.angle / (hfov_deg / 2)))


class AlertPolicy:
    def __init__(self, settings):
        self.s = settings
        # track id -> {"urgency", "time", "count", "bbox", "last_seen"} for
        # everything already announced (kept briefly after the track is lost).
        self._announced = {}
        self.last_speech_time = -math.inf
        self.last_urgency = INFO
        self._path_blocked = False
        self._clear_since = None
        self._last_path_clear = -math.inf

    def reset(self):
        self.__init__(self.s)

    def note_spoken(self, now, urgency=INFO):
        """Record externally-triggered speech (e.g. a scene description) so the
        heartbeat and gaps account for it."""
        self.last_speech_time = now
        self.last_urgency = urgency

    def update(self, detections, now):
        """Return an Announcement or None for this detector cycle."""
        s = self.s
        self._refresh_memory(detections, now)

        candidates = []
        for det in detections:
            urgency = classify(det, s)
            if urgency is None or not passes_verbosity(det, urgency, s.verbosity):
                continue
            hits = det.extra.get("hits", MIN_HITS)
            if urgency != CRITICAL and hits < MIN_HITS:
                continue
            if self._due(det.track_id, urgency, now):
                candidates.append((urgency, det.distance, det))

        announcement = None

        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]))
            urgency, _, det = candidates[0]
            gap = now - self.last_speech_time
            if gap >= MIN_GAP[urgency] or urgency < self.last_urgency:
                announcement = self._hazard_announcement(det, urgency, candidates, now)

        in_path = [d for d in detections
                   if d.in_path and classify(d, s) in (CRITICAL, WARNING)]
        # Only obstacles the user was actually warned about can later be "cleared".
        blocking = [d for d in in_path if d.track_id in self._announced]

        # Path-clear feedback: once when a blocking obstacle leaves the path, and
        # periodically as a heartbeat so silence isn't mistaken for a frozen system.
        if blocking:
            self._path_blocked = True
            self._clear_since = None
        elif announcement is None:
            if self._path_blocked:
                if self._clear_since is None:
                    self._clear_since = now
                elif now - self._clear_since >= PATH_CLEAR_DEBOUNCE:
                    self._path_blocked = False
                    announcement = Announcement("Path clear ahead", INFO, kind="path_clear")
            elif (not in_path and now - self.last_speech_time >= s.path_clear_interval
                  and now - self._last_path_clear >= s.path_clear_interval):
                announcement = Announcement("Path clear", INFO, kind="path_clear")

        if announcement is not None:
            self.last_speech_time = now
            self.last_urgency = announcement.urgency
            if announcement.kind == "path_clear":
                self._last_path_clear = now
        return announcement

    def _refresh_memory(self, detections, now):
        live = {d.track_id: d for d in detections}
        for tid, state in self._announced.items():
            if tid in live:
                state["bbox"] = live[tid].bbox
                state["last_seen"] = now
        for tid in [t for t, st in self._announced.items()
                    if now - st["last_seen"] > REACQUIRE_SECONDS]:
            del self._announced[tid]
        # Hand the memory of a lost/relabelled object over to its new track.
        for tid, det in live.items():
            if tid in self._announced:
                continue
            best, best_iou = None, REACQUIRE_IOU
            for old_tid, state in self._announced.items():
                if old_tid in live:
                    continue
                overlap = iou(det.bbox, state["bbox"])
                if overlap >= best_iou:
                    best, best_iou = old_tid, overlap
            if best is not None:
                self._announced[tid] = self._announced.pop(best)

    def _due(self, track_id, urgency, now):
        """New objects are announced; an announced object speaks again only if it
        becomes more urgent, or once more (critical only) after REMINDER_INTERVAL.
        After that it stays silent - Space describes it on demand."""
        state = self._announced.get(track_id)
        if state is None or urgency < state["urgency"]:
            return True
        if urgency > state["urgency"]:
            return False
        limit = self.s.critical_repeats if urgency == CRITICAL else 1
        return state["count"] < limit and now - state["time"] >= REMINDER_INTERVAL

    def _hazard_announcement(self, det, urgency, candidates, now):
        s = self.s
        approaching = is_approaching(det) and det.category in (PERSON, VEHICLE, ANIMAL)
        group = [det]
        if urgency == INFO:
            # Collapse same-label objects at the same clock position into one phrase.
            group = [c[2] for c in candidates
                     if c[0] == INFO and c[2].label == det.label and c[2].clock == det.clock]
        phrase = object_phrase(det, s.units, s.step_length, count=len(group),
                               approaching=approaching)
        text = f"Stop. {capitalize(phrase)}" if urgency == CRITICAL else capitalize(phrase)
        for d in group:
            state = self._announced.get(d.track_id)
            count = state["count"] + 1 if state and state["urgency"] == urgency else 1
            self._announced[d.track_id] = {"urgency": urgency, "time": now, "count": count,
                                           "bbox": d.bbox, "last_seen": now}
        return Announcement(text, urgency, pan=pan_for(det, s.camera_hfov_deg), detection=det)
