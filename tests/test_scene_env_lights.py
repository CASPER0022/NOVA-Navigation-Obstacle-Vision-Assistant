import numpy as np
import cv2

from nova.config import Settings
from nova.environment import assess_frame, EnvironmentMonitor
from nova.scene import describe_scene, describe_path
from nova.traffic_light import classify_light, TrafficLightMonitor

from helpers import make_det


def textured(seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)


def test_describe_empty_and_grouped():
    s = Settings()
    assert describe_scene([], s) == "I don't see any objects right now."
    dets = [make_det("chair", 2.0, angle=0, in_path=True),
            make_det("person", 4.0, angle=25, in_path=False),
            make_det("person", 5.0, angle=28, in_path=False)]
    text = describe_scene(dets, s)
    assert text == "3 objects. Chair ahead, 2 meters. 2 people 1 o'clock, 4 meters."


def test_describe_path_suggests_side():
    s = Settings()
    assert describe_path([], s) == "Path ahead looks clear."
    dets = [make_det("chair", 1.5, angle=-8, in_path=True),
            make_det("person", 2.0, angle=-20, in_path=False)]
    assert describe_path(dets, s) == "Chair in your path, 1.5 meters. More room on your right."


def test_environment_assessment():
    assert assess_frame(np.full((240, 320, 3), 10, np.uint8)) == "dark"
    assert assess_frame(np.full((240, 320, 3), 128, np.uint8)) == "blocked"
    # Large high-contrast shapes (a checkerboard) seen through a smeared lens.
    board = np.kron((np.indices((6, 8)).sum(0) % 2) * 200 + 30, np.ones((40, 40)))
    board = cv2.cvtColor(board.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    assert assess_frame(board) is None
    assert assess_frame(cv2.GaussianBlur(board, (0, 0), 12)) == "blurry"
    assert assess_frame(textured()) is None


def test_environment_monitor_debounces_and_recovers():
    m = EnvironmentMonitor(confirm_checks=3, check_frozen=False)
    dark = np.full((240, 320, 3), 5, np.uint8)
    assert m.update(dark, 0) is None
    assert m.update(dark, 1) is None
    assert m.update(dark, 2).startswith("It's very dark")
    assert m.update(dark, 3) is None
    ok = textured()
    m.update(ok, 4), m.update(ok, 5)
    assert m.update(ok, 6) == "Camera view is clear again."


def test_frozen_feed_detected():
    m = EnvironmentMonitor(confirm_checks=1)
    frame = textured()
    msgs = [m.update(frame, t) for t in range(0, 7)]
    assert "Camera image is frozen. I may miss obstacles." in msgs


def light_frame(color_bgr, lit_row):
    frame = np.zeros((120, 60, 3), np.uint8)
    frame[:] = (40, 40, 40)
    cy = [20, 60, 100][lit_row]
    cv2.circle(frame, (30, cy), 15, color_bgr, -1)
    return frame


def test_classify_light():
    box = (0, 0, 60, 120)
    assert classify_light(light_frame((0, 0, 255), 0), box) == "red"
    assert classify_light(light_frame((0, 255, 0), 2), box) == "green"
    assert classify_light(light_frame((0, 220, 255), 1), box) == "yellow"
    assert classify_light(np.full((120, 60, 3), 40, np.uint8), box) is None


def test_light_monitor_reports_changes():
    mon = TrafficLightMonitor(confirm_checks=2)
    light = make_det("traffic light", 8.0, bbox=(0, 0, 60, 120))
    red, green = light_frame((0, 0, 255), 0), light_frame((0, 255, 0), 2)
    assert mon.update(red, [light]) is None
    assert mon.update(red, [light]) == "Traffic light at 12 o'clock appears red."
    assert mon.update(red, [light]) is None
    mon.update(green, [light])
    assert mon.update(green, [light]) == "Traffic light at 12 o'clock changed to green."
