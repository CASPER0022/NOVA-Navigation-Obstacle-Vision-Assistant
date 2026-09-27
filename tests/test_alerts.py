from nova.alerts import AlertPolicy, classify, CRITICAL, WARNING, INFO
from nova.config import Settings
from nova.phrasing import format_distance

from helpers import make_det


def policy(**kw):
    return AlertPolicy(Settings(**kw).validate())


def test_classification():
    s = Settings()
    assert classify(make_det(distance=0.9, in_path=True), s) == CRITICAL
    assert classify(make_det(distance=2.0, in_path=True), s) == WARNING
    assert classify(make_det(distance=0.9, in_path=False, angle=25), s) == WARNING
    assert classify(make_det(distance=4.0, in_path=False, angle=25), s) == INFO
    assert classify(make_det(distance=20.0, in_path=False), s) is None
    # Collision course: 4 m away closing at 3 m/s -> ttc 1.3 s
    assert classify(make_det(distance=4.0, closing_speed=3.0), s) == CRITICAL
    assert classify(make_det("car", distance=5.0, in_path=False, angle=25,
                             closing_speed=1.0), s) == WARNING


def test_critical_phrase_and_ahead():
    p = policy()
    ann = p.update([make_det("chair", distance=0.9)], now=10)
    assert ann.urgency == CRITICAL
    assert ann.text == "Stop. Chair ahead, 0.9 meters"


def test_warning_is_said_once():
    p = policy()
    d = make_det(distance=2.0, track_id=1)
    assert p.update([d], now=0).urgency == WARNING
    for t in range(1, 60):
        assert p.update([d], now=t) is None


def test_critical_is_said_twice_then_quiet():
    p = policy()
    d = make_det("laptop", distance=0.4, track_id=1)
    spoken = [t for t in range(0, 60) if p.update([d], now=t) is not None]
    assert spoken == [0, 6]


def test_critical_repeats_is_configurable():
    p = policy(critical_repeats=1)
    d = make_det("laptop", distance=0.4, track_id=1)
    assert [t for t in range(0, 60) if p.update([d], now=t)] == [0]


def test_relabelled_or_reacquired_object_is_not_reannounced():
    # YOLO flips the same desk object between labels and loses it briefly.
    p = policy()
    box = (100, 100, 300, 300)
    assert p.update([make_det("tv", 0.8, track_id=1, bbox=box)], now=0) is not None
    assert p.update([], now=0.5) is None
    assert p.update([make_det("laptop", 0.8, track_id=2, bbox=(110, 105, 305, 300))],
                    now=1.0) is None
    assert p.update([make_det("refrigerator", 0.8, track_id=3, bbox=box)], now=1.5) is None


def test_object_gone_for_a_while_is_announced_again():
    p = policy()
    box = (100, 100, 300, 300)
    p.update([make_det("chair", 0.8, track_id=1, bbox=box)], now=0)
    p.update([], now=1)
    assert p.update([make_det("chair", 0.8, track_id=2, bbox=box)], now=10) is not None


def test_escalation_is_announced_immediately():
    p = policy()
    p.update([make_det(distance=2.0, track_id=1)], now=0)
    ann = p.update([make_det(distance=1.0, track_id=1)], now=0.3)
    assert ann is not None and ann.urgency == CRITICAL


def test_unconfirmed_detection_is_debounced_but_critical_is_not():
    p = policy()
    assert p.update([make_det(distance=2.0, hits=1)], now=0) is None
    assert p.update([make_det(distance=0.8, hits=1)], now=1).urgency == CRITICAL


def test_closest_most_urgent_first():
    p = policy()
    far = make_det("person", distance=2.4)
    near = make_det("chair", distance=1.6)
    ann = p.update([far, near], now=0)
    assert ann.detection is near


def test_unspoken_hazards_are_not_lost():
    p = policy()
    a = make_det("person", distance=1.8, track_id=1)
    b = make_det("chair", distance=2.2, track_id=2)
    first = p.update([a, b], now=0)
    second = p.update([a, b], now=2.0)
    assert {first.detection.track_id, second.detection.track_id} == {1, 2}


def test_verbosity_filters_info():
    side_chair = make_det("chair", distance=4.0, in_path=False, angle=25)
    for verbosity, expect_spoken in (("minimal", False), ("normal", False), ("detailed", True)):
        p = policy(verbosity=verbosity)
        p.note_spoken(0)  # the app announces "ready" at startup
        ann = p.update([side_chair], now=5)
        assert (ann is not None and ann.urgency == INFO) == expect_spoken


def test_info_grouping():
    p = policy(verbosity="detailed")
    people = [make_det("person", distance=d, in_path=False, angle=25) for d in (4.0, 4.5, 5.0)]
    ann = p.update(people, now=0)
    assert ann.text == "3 people at 1 o'clock, nearest 4 meters"


def test_path_clear_after_obstacle_leaves():
    p = policy()
    p.update([make_det(distance=2.0)], now=0)
    assert p.update([], now=0.5) is None       # debounce
    assert p.update([], now=2.0) is None
    ann = p.update([], now=3.6)
    assert ann.kind == "path_clear" and ann.text == "Path clear ahead"


def test_path_clear_heartbeat():
    p = policy(path_clear_interval=10)
    p.note_spoken(0)
    assert p.update([], now=5) is None
    assert p.update([], now=10.5).text == "Path clear"
    assert p.update([], now=15) is None


def test_distance_units():
    assert format_distance(0.84) == "0.8 meters"
    assert format_distance(1.1) == "1 meter"
    assert format_distance(2.3) == "2.5 meters"
    assert format_distance(2.1, "steps", 0.7) == "3 steps"
    assert format_distance(0.3, "steps", 0.7) == "1 step"
    assert format_distance(1.0, "feet") == "3 feet"


def test_steps_in_announcement():
    ann = policy(units="steps").update([make_det("chair", distance=0.7)], now=0)
    assert ann.text == "Stop. Chair ahead, 1 step"
