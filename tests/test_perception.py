import math

import pytest

from nova.perception import CameraGeometry, build_detection, clock_position, spoken_name


@pytest.fixture
def geo():
    return CameraGeometry(640, 480, 60.0)


@pytest.mark.parametrize("angle,hour", [
    (0, 12), (10, 12), (-14, 12), (16, 1), (-16, 11), (30, 1), (-60, 10), (89, 3), (-120, 9),
])
def test_clock_position_uses_30_degrees_per_hour(angle, hour):
    assert clock_position(angle) == hour


def test_frame_edge_of_60_degree_camera_is_not_3_oclock(geo):
    # Old code mapped the right frame edge to 3 o'clock (90 deg); it's really 30 deg.
    assert geo.angle_of(640) == pytest.approx(30.0)
    assert clock_position(geo.angle_of(639)) == 1


def test_angle_and_x_are_inverse(geo):
    for angle in (-25, -10, 0, 12, 29):
        assert geo.angle_of(geo.x_of_angle(angle)) == pytest.approx(angle)


def test_distance_from_height_for_person(geo):
    # A 1.7 m person 3 m away spans focal*1.7/3 pixels.
    box_h = geo.focal_px * 1.7 / 3.0
    bbox = (300, 240 - box_h / 2, 300 + box_h * 0.2, 240 + box_h / 2)
    assert geo.estimate_distance(bbox, 0.45, 1.7) == pytest.approx(3.0, rel=0.02)


def test_truncated_height_falls_back_to_width(geo):
    # Feet cut off by the bottom edge: height would suggest "far away", width is honest.
    box_w = geo.focal_px * 0.45 / 1.5
    bbox = (300, 100, 300 + box_w, 480)
    assert geo.estimate_distance(bbox, 0.45, 1.7) == pytest.approx(1.5, rel=0.02)


def test_fully_truncated_box_is_treated_as_very_close(geo):
    assert geo.estimate_distance((0, 0, 640, 480), 0.45, 1.7) <= 0.8


def test_in_path_uses_lateral_meters(geo):
    # Same pixel offset: near object is ~0.3 m to the side (in path),
    # far object is ~2 m to the side (not in path).
    x = geo.x_of_angle(10)
    def box_at(distance):
        h = geo.focal_px * 0.9 / distance
        w = geo.focal_px * 0.5 / distance
        return (x - w / 2, 240 - h / 2, x + w / 2, 240 + h / 2)
    near = build_detection("chair", box_at(1.5), 0.9, geo, 0.5)
    far = build_detection("chair", box_at(12.0), 0.9, geo, 0.5)
    assert near.in_path
    assert not far.in_path
    assert near.distance == pytest.approx(1.5, rel=0.05)


def test_spoken_names():
    assert spoken_name("person", 2) == "people"
    assert spoken_name("dining table") == "table"
    assert spoken_name("chair", 3) == "chairs"
