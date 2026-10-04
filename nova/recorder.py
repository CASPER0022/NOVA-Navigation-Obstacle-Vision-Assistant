"""Saves the annotated HUD (camera view, radar, captions) to a video file, so a
demo can be shown without relying on a live camera."""
import os

import cv2

LIVE_FPS = 15.0


class Recorder:
    """Writes composed frames to `path`.

    With `realtime` (live camera) frames arrive irregularly, so they're placed on a
    fixed LIVE_FPS timeline by wall-clock time: a frame is repeated to fill a slow
    gap and skipped when frames arrive faster than the output rate. That keeps the
    video's playback speed equal to what actually happened. Recorded input is
    written one frame per input frame at the source's own rate.
    """

    def __init__(self, path, fps=None, realtime=True):
        self.path = path
        self.realtime = realtime
        self.fps = LIVE_FPS if realtime or not fps else fps
        self.writer = None
        self.size = None
        self.frames_written = 0
        self._start = None

    def _open(self, size):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        codec = "XVID" if self.path.lower().endswith(".avi") else "mp4v"
        self.writer = cv2.VideoWriter(self.path, cv2.VideoWriter_fourcc(*codec), self.fps, size)
        if not self.writer.isOpened():
            raise RuntimeError(f"Could not open video writer for {self.path}")
        self.size = size

    def write(self, image, now=None):
        h, w = image.shape[:2]
        if self.writer is None:
            self._open((w, h))
            self._start = now
        if (w, h) != self.size:
            image = cv2.resize(image, self.size)
        if not self.realtime or now is None:
            copies = 1
        else:
            due = int((now - self._start) * self.fps) + 1
            copies = due - self.frames_written
        for _ in range(max(0, copies)):
            self.writer.write(image)
            self.frames_written += 1

    def close(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            print(f"Saved recording to {self.path} "
                  f"({self.frames_written} frames, {self.frames_written / self.fps:.1f} s)")
