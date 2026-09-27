"""Lightweight multi-object tracker.

Gives each physical object a stable id across detector runs so that:
  * an object isn't re-announced as "new" every time it drifts across a sector,
  * two people side by side are two hazards, not one,
  * single-frame false positives can be ignored (``hits`` debounce),
  * we can measure closing speed and time-to-contact from the distance history.
"""
from collections import deque


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)


class Track:
    def __init__(self, track_id, detection, now):
        self.id = track_id
        self.label = detection.label
        self.bbox = detection.bbox
        self.first_seen = now
        self.last_seen = now
        self.hits = 1
        self.smoothed_distance = detection.distance
        self.history = deque(maxlen=12)  # (timestamp, distance)
        self.history.append((now, detection.distance))
        self.detection = detection

    def update(self, detection, now, alpha=0.5):
        self.bbox = detection.bbox
        self.last_seen = now
        self.hits += 1
        self.smoothed_distance = alpha * detection.distance + (1 - alpha) * self.smoothed_distance
        self.history.append((now, detection.distance))
        self.detection = detection

    def closing_speed(self, window=1.5, min_samples=4, min_span=0.75):
        """Least-squares slope of distance over the recent window, negated so that
        positive means approaching. 0 when there isn't enough history."""
        latest = self.history[-1][0]
        pts = [(t, d) for t, d in self.history if latest - t <= window]
        if len(pts) < min_samples or pts[-1][0] - pts[0][0] < min_span:
            return 0.0
        n = len(pts)
        mean_t = sum(t for t, _ in pts) / n
        mean_d = sum(d for _, d in pts) / n
        var_t = sum((t - mean_t) ** 2 for t, _ in pts)
        if var_t == 0:
            return 0.0
        slope = sum((t - mean_t) * (d - mean_d) for t, d in pts) / var_t
        return -slope


class Tracker:
    def __init__(self, iou_threshold=0.25, max_age=1.5):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.tracks = {}
        self._next_id = 1

    def update(self, detections, now):
        """Associate detections with tracks (greedy by IoU, same label only),
        annotate each detection in place, and drop tracks unseen for max_age."""
        candidates = []
        for di, det in enumerate(detections):
            for tid, track in self.tracks.items():
                if track.label != det.label:
                    continue
                score = iou(det.bbox, track.bbox)
                if score >= self.iou_threshold:
                    candidates.append((score, di, tid))
        candidates.sort(reverse=True)

        assignment = {}  # detection index -> track id
        for _, di, tid in candidates:
            if di in assignment or tid in assignment.values():
                continue
            assignment[di] = tid
            self.tracks[tid].update(detections[di], now)

        for di, det in enumerate(detections):
            if di not in assignment:
                track = Track(self._next_id, det, now)
                self.tracks[track.id] = track
                self._next_id += 1
                assignment[di] = track.id
            det.track_id = assignment[di]

        for det in detections:
            track = self.tracks[det.track_id]
            det.distance = track.smoothed_distance
            det.closing_speed = track.closing_speed()
            det.first_seen = track.first_seen
            det.extra["hits"] = track.hits

        for tid in [tid for tid, t in self.tracks.items() if now - t.last_seen > self.max_age]:
            del self.tracks[tid]

        return detections

    def recent(self, now, window=1.0):
        """Latest detection of every object seen within `window` seconds. Used for
        on-demand descriptions, so one missed frame doesn't mean "nothing here"."""
        return [t.detection for t in self.tracks.values() if now - t.last_seen <= window]
