"""Geometry and object catalog: turns raw detector boxes into Detections with
direction, distance and "is it in my walking path" information.

All geometry uses a pinhole camera model parameterised by the horizontal field
of view, so clock positions reflect real angles (one hour = 30 degrees, the
convention taught in orientation & mobility training) rather than stretching
the camera's ~60 degree view across the whole 9-to-3 o'clock range.
"""
import math
from dataclasses import dataclass, field

# Category drives phrasing and urgency rules.
PERSON, VEHICLE, ANIMAL, FURNITURE, OBJECT, SIGNAL = (
    "person", "vehicle", "animal", "furniture", "object", "signal")

# COCO label -> (category, typical real width m, typical real height m)
OBJECT_CATALOG = {
    "person":        (PERSON,    0.45, 1.70),
    "bicycle":       (VEHICLE,   0.60, 1.05),
    "car":           (VEHICLE,   1.80, 1.50),
    "motorcycle":    (VEHICLE,   0.80, 1.10),
    "bus":           (VEHICLE,   2.50, 3.00),
    "truck":         (VEHICLE,   2.50, 3.00),
    "dog":           (ANIMAL,    0.30, 0.55),
    "cat":           (ANIMAL,    0.20, 0.30),
    "bench":         (FURNITURE, 1.20, 0.80),
    "chair":         (FURNITURE, 0.50, 0.90),
    "couch":         (FURNITURE, 1.80, 0.85),
    "bed":           (FURNITURE, 1.50, 0.60),
    "dining table":  (FURNITURE, 1.20, 0.75),
    "toilet":        (FURNITURE, 0.40, 0.75),
    "refrigerator":  (FURNITURE, 0.80, 1.80),
    "potted plant":  (OBJECT,    0.40, 0.60),
    "fire hydrant":  (OBJECT,    0.30, 0.70),
    "parking meter": (OBJECT,    0.30, 1.40),
    "suitcase":      (OBJECT,    0.40, 0.60),
    "backpack":      (OBJECT,    0.35, 0.45),
    "tv":            (OBJECT,    0.90, 0.55),
    "laptop":        (OBJECT,    0.35, 0.25),
    "bottle":        (OBJECT,    0.08, 0.25),
    "cup":           (OBJECT,    0.08, 0.10),
    "traffic light": (SIGNAL,    0.30, 0.90),
    "stop sign":     (SIGNAL,    0.75, 0.75),
}

# How the label is spoken; plural forms for grouped announcements.
PLURALS = {"person": "people", "bus": "buses", "couch": "couches", "bench": "benches",
           "dining table": "tables", "tv": "TVs"}
SPOKEN_NAMES = {"dining table": "table", "tv": "TV", "potted plant": "plant"}

EDGE_MARGIN_PX = 3


def spoken_name(label, count=1):
    if count > 1:
        return PLURALS.get(label, SPOKEN_NAMES.get(label, label) + "s")
    return SPOKEN_NAMES.get(label, label)


@dataclass
class Detection:
    label: str
    category: str
    bbox: tuple              # (x1, y1, x2, y2) pixels
    confidence: float
    distance: float          # meters
    angle: float             # degrees, negative = left
    clock: int               # 9..3
    in_path: bool            # overlaps the walking corridor
    track_id: int = None
    closing_speed: float = 0.0   # m/s, positive = getting closer
    first_seen: float = None     # timestamp the track was first detected
    extra: dict = field(default_factory=dict)

    @property
    def ttc(self):
        """Seconds until contact at the current closing speed (inf if not approaching)."""
        if self.closing_speed <= 0.05:
            return math.inf
        return self.distance / self.closing_speed

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2, (y1 + y2) / 2


class CameraGeometry:
    def __init__(self, frame_width, frame_height, hfov_deg):
        self.width = frame_width
        self.height = frame_height
        self.hfov_deg = hfov_deg
        self.focal_px = (frame_width / 2) / math.tan(math.radians(hfov_deg) / 2)

    def angle_of(self, x_px):
        return math.degrees(math.atan((x_px - self.width / 2) / self.focal_px))

    def x_of_angle(self, angle_deg):
        return self.width / 2 + math.tan(math.radians(angle_deg)) * self.focal_px

    def lateral_offset(self, x_px, distance):
        """Sideways offset in meters of pixel column x at the given distance."""
        return (x_px - self.width / 2) / self.focal_px * distance

    def estimate_distance(self, bbox, real_width, real_height):
        """Pinhole distance estimate, using only box sides that aren't cut off by
        the frame edge (a truncated box looks smaller, i.e. falsely far away).
        Takes the closer of the valid estimates: erring near is the safe error."""
        x1, y1, x2, y2 = bbox
        box_w = max(1.0, x2 - x1)
        box_h = max(1.0, y2 - y1)
        from_width = self.focal_px * real_width / box_w
        from_height = self.focal_px * real_height / box_h

        width_ok = x1 > EDGE_MARGIN_PX and x2 < self.width - EDGE_MARGIN_PX
        height_ok = y1 > EDGE_MARGIN_PX and y2 < self.height - EDGE_MARGIN_PX

        valid = [d for d, ok in ((from_width, width_ok), (from_height, height_ok)) if ok]
        if valid:
            return min(valid)
        # Both dimensions truncated: the object fills the view. Each estimate is
        # only an upper bound, so treat it as very near.
        return min(from_width, from_height, 0.8)


def clock_position(angle_deg):
    """Map a horizontal angle to a clock hour (30 degrees per hour), 9..3."""
    hours_offset = max(-3, min(3, round(angle_deg / 30.0)))
    hour = 12 + hours_offset
    return hour - 12 if hour > 12 else hour


def build_detection(label, bbox, confidence, geometry, corridor_half_width):
    category, real_w, real_h = OBJECT_CATALOG[label]
    x1, _, x2, _ = bbox
    distance = geometry.estimate_distance(bbox, real_w, real_h)
    angle = geometry.angle_of((x1 + x2) / 2)
    left_m = geometry.lateral_offset(x1, distance)
    right_m = geometry.lateral_offset(x2, distance)
    in_path = left_m < corridor_half_width and right_m > -corridor_half_width
    return Detection(
        label=label, category=category, bbox=tuple(int(v) for v in bbox),
        confidence=float(confidence), distance=distance, angle=angle,
        clock=clock_position(angle), in_path=in_path,
    )


class Detector:
    """Thin wrapper over an Ultralytics YOLO model restricted to OBJECT_CATALOG."""

    def __init__(self, model_path, confidence):
        from ultralytics import YOLO  # imported lazily so unit tests don't need it
        self.model = YOLO(model_path)
        self.confidence = confidence
        names = self.model.names
        self.class_ids = [i for i, n in names.items() if n in OBJECT_CATALOG]

    def warmup(self, shape=(480, 640, 3)):
        """Run one throwaway inference so the first real frame isn't delayed by
        model initialisation (several seconds on CPU)."""
        import numpy as np
        self.model.predict(np.zeros(shape, dtype=np.uint8), verbose=False)

    def detect(self, frame, geometry, corridor_half_width):
        results = self.model.predict(frame, conf=self.confidence, classes=self.class_ids,
                                     verbose=False)
        detections = []
        for result in results:
            for box in result.boxes:
                label = self.model.names[int(box.cls[0])]
                bbox = tuple(float(v) for v in box.xyxy[0])
                detections.append(build_detection(label, bbox, float(box.conf[0]),
                                                  geometry, corridor_half_width))
        return detections
