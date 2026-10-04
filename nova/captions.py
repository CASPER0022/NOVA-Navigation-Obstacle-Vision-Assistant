"""On-screen subtitles of everything NOVA says, so a recorded or projected demo
shows what the user hears (and a sighted helper can follow along)."""
from collections import deque
from dataclasses import dataclass

import cv2

from .hud import FONT

KIND_COLORS = {"critical": (0, 0, 255), "warning": (0, 140, 255), "info": (0, 160, 0),
               "path_clear": (160, 130, 0), "status": (90, 90, 90)}
MIN_SECONDS = 2.5
SECONDS_PER_CHAR = 0.06
MAX_SECONDS = 8.0
MAX_VISIBLE = 2
SCALE = 0.55
LINE_GAP = 6
PAD = 6


@dataclass
class Caption:
    text: str
    kind: str
    start: float

    @property
    def duration(self):
        return min(MAX_SECONDS, max(MIN_SECONDS, SECONDS_PER_CHAR * len(self.text)))


class Captions:
    def __init__(self):
        self.items = deque(maxlen=8)

    def add(self, text, kind, now):
        self.items.append(Caption(text, kind if kind in KIND_COLORS else "status", now))

    def clear(self):
        self.items.clear()

    def active(self, now):
        live = [c for c in self.items if 0 <= now - c.start <= c.duration]
        return live[-MAX_VISIBLE:]


def wrap(text, max_width, scale=SCALE):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and cv2.getTextSize(candidate, FONT, scale, 1)[0][0] > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def draw(frame, captions, bottom_margin=30):
    """Draw captions as boxes stacked upwards from the bottom, newest lowest."""
    h, w = frame.shape[:2]
    line_h = cv2.getTextSize("Ag", FONT, SCALE, 1)[0][1] + LINE_GAP
    y_bottom = h - bottom_margin
    for caption in reversed(captions):
        lines = wrap(caption.text, w - 4 * PAD)
        widths = [cv2.getTextSize(line, FONT, SCALE, 1)[0][0] for line in lines]
        box_w = max(widths) + 2 * PAD
        box_h = len(lines) * line_h + PAD
        x1 = (w - box_w) // 2
        y1 = y_bottom - box_h
        if y1 < 28:  # never cover the status bar
            break
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x1 + box_w, y_bottom), KIND_COLORS[caption.kind], -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        for i, (line, lw) in enumerate(zip(lines, widths)):
            y = y1 + PAD + (i + 1) * line_h - LINE_GAP
            cv2.putText(frame, line, ((w - lw) // 2, y), FONT, SCALE, (255, 255, 255), 1,
                        cv2.LINE_AA)
        y_bottom = y1 - 4
    return frame
