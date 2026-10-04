"""Bird's-eye "radar" panel: a top-down map of what NOVA believes is around the user.

The user stands at the bottom centre looking up the page. Every tracked object is
placed at its estimated forward distance and sideways offset in meters (the same
pinhole geometry the alert policy uses), drawn as a bar spanning its width, so
you can see at a glance why something is or isn't "in your path".
"""
import math

import cv2
import numpy as np

from .alerts import classify, is_approaching, CRITICAL
from .hud import COLORS, FONT, _text
from .perception import spoken_name

BACKGROUND = (28, 24, 22)
FOV_FILL = (48, 42, 38)
RING = (80, 80, 80)
CORRIDOR = (255, 200, 0)
PREDICTION_SECONDS = 1.0     # approach arrows show where the object will be in this long
TOP_MARGIN = 30
BOTTOM_MARGIN = 44


class RadarView:
    """Maps meters (lateral x, forward z) to panel pixels."""

    def __init__(self, height, settings, width=None):
        self.h = height
        self.w = width or max(260, int(height * 0.8))
        self.s = settings
        self.range_m = settings.max_alert_distance + 0.5
        self.scale = (height - TOP_MARGIN - BOTTOM_MARGIN) / self.range_m  # px per meter
        self.origin = (self.w // 2, height - BOTTOM_MARGIN)

    def to_px(self, lateral_m, forward_m):
        return (int(round(self.origin[0] + lateral_m * self.scale)),
                int(round(self.origin[1] - forward_m * self.scale)))

    def render(self, detections, geometry):
        panel = np.full((self.h, self.w, 3), BACKGROUND, np.uint8)
        self._draw_field_of_view(panel)
        self._draw_zones(panel)
        self._draw_rings(panel)
        for det in sorted(detections, key=lambda d: -d.distance):  # nearest drawn on top
            self._draw_object(panel, det, geometry)
        self._draw_user(panel)
        _text(panel, "BIRD'S-EYE VIEW", (8, 20), (255, 255, 255), 0.5)
        cv2.line(panel, (0, 0), (0, self.h), (90, 90, 90), 2)
        return panel

    # ----------------------------------------------------------------- layers
    def _draw_field_of_view(self, panel):
        half = math.radians(self.s.camera_hfov_deg / 2)
        reach = self.range_m * 1.5
        pts = np.array([self.origin,
                        self.to_px(-reach * math.sin(half), reach * math.cos(half)),
                        self.to_px(reach * math.sin(half), reach * math.cos(half))], np.int32)
        cv2.fillPoly(panel, [pts], FOV_FILL)
        for p in pts[1:]:
            cv2.line(panel, self.origin, tuple(int(v) for v in p), (90, 90, 90), 1, cv2.LINE_AA)

    def _draw_zones(self, panel):
        """Walking corridor, shaded by the distance bands that make an object in it
        critical (red) or a warning (orange)."""
        c = self.s.corridor_half_width
        overlay = panel.copy()
        bands = ((0.0, self.s.critical_distance, COLORS[CRITICAL]),
                 (self.s.critical_distance, self.s.warning_distance, COLORS[1]),
                 (self.s.warning_distance, self.range_m, CORRIDOR))
        for near, far, color in bands:
            cv2.rectangle(overlay, self.to_px(-c, far), self.to_px(c, near), color, -1)
        cv2.addWeighted(overlay, 0.18, panel, 0.82, 0, panel)
        top = self.to_px(0, self.range_m)[1]
        for x in (self.to_px(-c, 0)[0], self.to_px(c, 0)[0]):
            for y in range(top, self.origin[1], 12):
                cv2.line(panel, (x, y), (x, min(self.origin[1], y + 6)), CORRIDOR, 1)

    def _draw_rings(self, panel):
        for m in range(1, int(self.s.max_alert_distance) + 1):
            r = int(m * self.scale)
            cv2.ellipse(panel, self.origin, (r, r), 0, 180, 360, RING, 1, cv2.LINE_AA)
            x, y = self.to_px(0, m)
            cv2.putText(panel, f"{m}m", (x + 4, y - 3), FONT, 0.35, (150, 150, 150), 1,
                        cv2.LINE_AA)

    def _draw_user(self, panel):
        x, y = self.origin
        cv2.fillPoly(panel, [np.array([(x, y - 12), (x - 9, y + 6), (x + 9, y + 6)], np.int32)],
                     (255, 255, 255))
        _text(panel, "YOU", (x - 15, y + 24), (255, 255, 255), 0.45)

    def _draw_object(self, panel, det, geometry):
        if det.distance > self.range_m:
            return
        urgency = classify(det, self.s)
        color = COLORS[urgency]
        x1, _, x2, _ = det.bbox
        left = geometry.lateral_offset(x1, det.distance)
        right = geometry.lateral_offset(x2, det.distance)
        centre = (left + right) / 2
        p_left, p_right = self.to_px(left, det.distance), self.to_px(right, det.distance)
        p_centre = self.to_px(centre, det.distance)

        if is_approaching(det):
            # Where the object will be after PREDICTION_SECONDS, moving towards the user.
            travel = min(det.closing_speed * PREDICTION_SECONDS, det.distance)
            k = (det.distance - travel) / det.distance
            target = self.to_px(centre * k, det.distance * k)
            cv2.arrowedLine(panel, p_centre, target, color, 2, cv2.LINE_AA, tipLength=0.25)

        cv2.line(panel, p_left, p_right, color, 6 if urgency == CRITICAL else 4, cv2.LINE_AA)
        cv2.circle(panel, p_centre, 4, (255, 255, 255), -1, cv2.LINE_AA)
        tag = spoken_name(det.label)
        if det.track_id is not None:
            tag = f"#{det.track_id} {tag}"
        tw = cv2.getTextSize(tag, FONT, 0.4, 1)[0][0]
        tx = min(max(4, p_centre[0] - tw // 2), self.w - tw - 4)
        _text(panel, tag, (tx, p_centre[1] - 10), color, 0.4)


def render(height, detections, geometry, settings):
    return RadarView(height, settings).render(detections, geometry)
