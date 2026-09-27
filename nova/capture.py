"""Frame sources: live camera (with auto-selection and reconnect), video file,
or a directory of images."""
import os
import sys
import time

import cv2

IS_WINDOWS = sys.platform.startswith("win")


def _open_camera(index):
    # DirectShow avoids multi-second timeouts on empty indices on Windows.
    if IS_WINDOWS:
        return cv2.VideoCapture(index, cv2.CAP_DSHOW)
    return cv2.VideoCapture(index)


def list_cameras(max_index=5):
    working = []
    for i in range(max_index):
        cap = _open_camera(i)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                working.append(i)
        cap.release()
    return working


def best_camera_index():
    working = list_cameras()
    if not working:
        print("No working cameras detected. Defaulting to index 0.")
        return 0
    print(f"Detected working camera indices: {working}")
    # Index 0 is usually the external USB webcam when one is plugged in.
    selected = 0 if 0 in working else working[-1]
    print(f"Auto-selected camera index {selected}.")
    return selected


class ImageDirectoryCapture:
    """cv2.VideoCapture-like reader over a folder of still images."""

    EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")

    def __init__(self, dir_path):
        self._paths = sorted(os.path.join(dir_path, f) for f in os.listdir(dir_path)
                             if f.lower().endswith(self.EXTENSIONS))
        self._index = 0

    def isOpened(self):
        return len(self._paths) > 0

    def read(self):
        if self._index >= len(self._paths):
            return False, None
        frame = cv2.imread(self._paths[self._index])
        self._index += 1
        return frame is not None, frame

    def release(self):
        pass


class FrameSource:
    """Uniform interface over camera / file input. read() returns a frame or None;
    for a live camera it transparently tries to reconnect, calling `on_status`
    with spoken status messages so a blind user isn't left in silence."""

    def __init__(self, settings, on_status=print):
        self.on_status = on_status
        self.is_live = settings.input is None
        self.is_image_dir = False
        if not self.is_live:
            if os.path.isdir(settings.input):
                self.is_image_dir = True
                self.cap = ImageDirectoryCapture(settings.input)
            else:
                self.cap = cv2.VideoCapture(settings.input)
            if not self.cap.isOpened():
                raise RuntimeError(f"Could not open input: {settings.input}")
            self.camera_index = None
        else:
            self.camera_index = (settings.camera if settings.camera is not None
                                 else best_camera_index())
            self.cap = _open_camera(self.camera_index)
            if not self.cap.isOpened() and not self._reconnect():
                raise RuntimeError("Camera unavailable")

    def read(self):
        ok, frame = self.cap.read()
        if ok:
            return frame
        if not self.is_live:
            return None  # end of recording
        return self.read() if self._reconnect() else None

    def _reconnect(self, max_wait=30.0, retry_delay=1.0):
        self.on_status("Camera lost. Reconnecting.")
        self.cap.release()
        start = time.time()
        while time.time() - start < max_wait:
            cap = _open_camera(self.camera_index)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    self.cap = cap
                    self.on_status("Camera reconnected.")
                    return True
            cap.release()
            time.sleep(retry_delay)
        self.on_status("Camera unavailable.")
        return False

    def release(self):
        self.cap.release()
