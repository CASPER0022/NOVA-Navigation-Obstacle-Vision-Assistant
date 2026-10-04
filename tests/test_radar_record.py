import cv2
import numpy as np

from nova import captions as captions_overlay, radar
from nova.captions import Captions
from nova.config import Settings
from nova.perception import CameraGeometry
from nova.recorder import Recorder

from helpers import make_det


def test_radar_places_objects_by_distance_and_side():
    s = Settings().validate()
    view = radar.RadarView(480, s)
    ux, uy = view.origin
    near_x, near_y = view.to_px(0, 1.0)
    far_x, far_y = view.to_px(0, 4.0)
    assert near_x == far_x == ux
    assert uy > near_y > far_y            # farther = higher up the panel
    assert view.to_px(-1.0, 2.0)[0] < ux < view.to_px(1.0, 2.0)[0]


def test_radar_renders_panel_with_objects():
    s = Settings().validate()
    geometry = CameraGeometry(640, 480, s.camera_hfov_deg)
    dets = [make_det("chair", 1.0, bbox=(280, 200, 360, 420)),
            make_det("car", 5.0, angle=20, in_path=False, closing_speed=1.5,
                     bbox=(500, 200, 600, 260)),
            make_det("person", 30.0)]  # beyond range: skipped, not drawn off-panel
    empty = radar.render(480, [], geometry, s)
    panel = radar.render(480, dets, geometry, s)
    assert panel.shape[0] == 480 and panel.shape[2] == 3
    assert (panel != empty).any()


def test_captions_expire_and_keep_newest():
    c = Captions()
    c.add("Stop. Chair ahead, 1 step.", "critical", 0.0)
    c.add("Path clear ahead.", "path_clear", 1.0)
    c.add("Person at 2 o'clock, 3 meters.", "info", 2.0)
    assert [x.text for x in c.active(2.1)] == ["Path clear ahead.",
                                               "Person at 2 o'clock, 3 meters."]
    assert c.active(100.0) == []
    assert c.active(-1.0) == []


def test_caption_wrapping_and_drawing():
    long = "3 objects. Chair ahead, 2 meters. 2 people at 1 o'clock, 4 meters. " * 2
    lines = captions_overlay.wrap(long, 300)
    assert len(lines) > 1
    assert " ".join(lines) == long.strip()
    frame = np.zeros((480, 640, 3), np.uint8)
    c = Captions()
    c.add(long, "warning", 0.0)
    captions_overlay.draw(frame, c.active(0.5))
    assert frame.any()


def test_recorder_realtime_fills_gaps(tmp_path):
    path = str(tmp_path / "out.avi")
    rec = Recorder(path, realtime=True)
    frame = np.zeros((120, 160, 3), np.uint8)
    rec.write(frame, 10.0)
    rec.write(frame, 10.01)      # faster than the output rate: dropped
    rec.write(frame, 11.0)       # 1 s later: padded to keep real-time speed
    rec.close()
    assert rec.frames_written == int(1.0 * rec.fps) + 1
    cap = cv2.VideoCapture(path)
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == rec.frames_written
    cap.release()


def test_recorder_offline_writes_every_frame(tmp_path):
    rec = Recorder(str(tmp_path / "out.avi"), fps=25, realtime=False)
    frame = np.zeros((120, 160, 3), np.uint8)
    for _ in range(5):
        rec.write(frame)
    rec.close()
    assert rec.fps == 25 and rec.frames_written == 5
