"""Turning numbers into short, speakable phrases."""
from .perception import spoken_name

FEET_PER_METER = 3.28084


def format_distance(meters, units="meters", step_length=0.7):
    if units == "steps":
        n = max(1, round(meters / step_length))
        return f"{n} step" if n == 1 else f"{n} steps"
    if units == "feet":
        n = max(1, round(meters * FEET_PER_METER))
        return f"{n} foot" if n == 1 else f"{n} feet"
    if meters < 1.0:
        return f"{max(0.1, round(meters, 1)):.1f} meters"
    rounded = round(meters * 2) / 2  # half-meter resolution is plenty and easier to hear
    if rounded == 1:
        return "1 meter"
    text = f"{rounded:.1f}".rstrip("0").rstrip(".")
    return f"{text} meters"


def direction_phrase(detection):
    if detection.clock == 12 and detection.in_path:
        return "ahead"
    return f"at {detection.clock} o'clock"


def object_phrase(detection, units, step_length, count=1, approaching=False):
    name = spoken_name(detection.label, count)
    if count > 1:
        name = f"{count} {name}"
    verb = " approaching" if approaching else ""
    dist = format_distance(detection.distance, units, step_length)
    if count > 1:
        dist = "nearest " + dist
    return f"{name}{verb} {direction_phrase(detection)}, {dist}"


def capitalize(text):
    return text[:1].upper() + text[1:]
