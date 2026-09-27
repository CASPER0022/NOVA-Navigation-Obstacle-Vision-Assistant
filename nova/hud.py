"""Preview-window overlay for sighted helpers, low-vision users and demos."""
import cv2

from .alerts import classify, CRITICAL, WARNING, INFO, is_approaching

COLORS = {CRITICAL: (0, 0, 255), WARNING: (0, 165, 255), INFO: (0, 200, 0), None: (160, 160, 160)}
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _text(frame, text, org, color, scale=0.5, thickness=1):
    # Dark outline keeps text legible on any background.
    cv2.putText(frame, text, org, FONT, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, org, FONT, scale, color, thickness, cv2.LINE_AA)


def draw(frame, detections, geometry, settings, status):
    h, w = frame.shape[:2]

    # Clock sector boundaries at +-15 and +-45 degrees (hour = 30 degrees).
    for boundary in (-75, -45, -15, 15, 45, 75):
        if abs(boundary) < settings.camera_hfov_deg / 2:
            x = int(geometry.x_of_angle(boundary))
            cv2.line(frame, (x, 0), (x, h), (120, 120, 120), 1)
    for hour_offset in range(-3, 4):
        angle = hour_offset * 30
        if abs(angle) <= settings.camera_hfov_deg / 2:
            hour = 12 + hour_offset
            hour = hour - 12 if hour > 12 else hour
            x = min(max(2, int(geometry.x_of_angle(angle)) - 8), w - 24)
            _text(frame, str(hour), (x, h - 10), (0, 255, 255))

    # Walking corridor as it appears at the warning distance.
    half = geometry.focal_px * settings.corridor_half_width / settings.warning_distance
    for x in (int(w / 2 - half), int(w / 2 + half)):
        for y in range(0, h, 16):
            cv2.line(frame, (x, y), (x, min(h, y + 8)), (255, 200, 0), 1)

    nearest = None
    for d in detections:
        urgency = classify(d, settings)
        color = COLORS[urgency]
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3 if urgency == CRITICAL else 2)
        tag = f"{d.label} {d.distance:.1f}m {d.clock}h"
        if is_approaching(d):
            tag += " >>"
        if d.extra.get("light_state"):
            tag += f" [{d.extra['light_state']}]"
        _text(frame, tag, (x1, max(15, y1 - 6)), color)
        if urgency in (CRITICAL, WARNING) and (nearest is None or d.distance < nearest[0].distance):
            nearest = (d, color)

    if nearest:
        d, color = nearest
        cx, cy = (int(v) for v in d.center)
        cv2.arrowedLine(frame, (w // 2, h - 30), (cx, cy), color, 3, tipLength=0.12)

    # Status bar.
    cv2.rectangle(frame, (0, 0), (w, 24), (0, 0, 0), -1)
    _text(frame, status, (6, 17), (255, 255, 255), 0.5)
    return frame
