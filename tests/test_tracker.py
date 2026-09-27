import pytest

from nova.perception import Detection
from nova.tracker import Tracker, iou


def det(bbox, distance, label="person"):
    return Detection(label=label, category="person", bbox=bbox, confidence=0.9,
                     distance=distance, angle=0.0, clock=12, in_path=True)


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)


def test_ids_persist_while_object_moves():
    t = Tracker()
    ids = []
    for i in range(5):
        d = det((100 + i * 10, 100, 200 + i * 10, 300), 3.0)
        t.update([d], now=i * 0.25)
        ids.append(d.track_id)
    assert len(set(ids)) == 1
    assert d.extra["hits"] == 5


def test_two_side_by_side_people_get_two_ids():
    t = Tracker()
    a, b = det((0, 0, 100, 200), 3), det((300, 0, 400, 200), 3)
    t.update([a, b], now=0)
    assert a.track_id != b.track_id


def test_labels_never_match_each_other():
    t = Tracker()
    a = det((0, 0, 100, 200), 3)
    t.update([a], now=0)
    b = det((0, 0, 100, 200), 3, label="chair")
    t.update([b], now=0.25)
    assert a.track_id != b.track_id


def test_closing_speed_of_approaching_object():
    t = Tracker()
    for i in range(6):
        now = i * 0.25
        d = det((100, 100, 200, 300), 4.0 - 1.0 * now)  # approaching at 1 m/s
        t.update([d], now=now)
    assert d.closing_speed == pytest.approx(1.0, abs=0.15)
    assert d.ttc < 4.0


def test_stale_tracks_expire():
    t = Tracker(max_age=1.0)
    t.update([det((0, 0, 10, 10), 3)], now=0)
    t.update([], now=2.0)
    assert t.tracks == {}


def test_jittery_static_object_is_not_approaching_on_short_history():
    t = Tracker()
    for i, dist in enumerate([5.0, 4.4, 5.3]):  # noisy estimates, only 0.5 s of history
        d = det((100, 100, 200, 300), dist)
        t.update([d], now=i * 0.25)
    assert d.closing_speed == 0.0
