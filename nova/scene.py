"""On-demand spoken summaries ("what's around me?", "is the path ahead clear?")."""
from collections import defaultdict

from .perception import SIGNAL, spoken_name
from .phrasing import format_distance, capitalize


def describe_scene(detections, settings, max_groups=5):
    """A compact left-to-right summary of everything currently detected."""
    objects = [d for d in detections if d.distance <= settings.max_alert_distance * 2]
    if not objects:
        return "I don't see any objects right now."

    groups = defaultdict(list)
    for d in objects:
        position = "ahead" if (d.clock == 12 and d.in_path) else f"{d.clock} o'clock"
        groups[(d.label, position)].append(d)

    # Nearest groups first, then keep the spoken order left to right so it maps
    # onto the user's mental picture of the space.
    ranked = sorted(groups.items(), key=lambda kv: min(d.distance for d in kv[1]))[:max_groups]
    ranked.sort(key=lambda kv: min(d.angle for d in kv[1]))

    parts = []
    for (label, position), dets in ranked:
        nearest = min(d.distance for d in dets)
        name = spoken_name(label, len(dets))
        count = f"{len(dets)} " if len(dets) > 1 else ""
        light = ""
        if label == "traffic light":
            state = dets[0].extra.get("light_state")
            light = f" showing {state}" if state else ""
        parts.append(f"{count}{name}{light} {position}, "
                     f"{format_distance(nearest, settings.units, settings.step_length)}")

    total = len(objects)
    header = "1 object" if total == 1 else f"{total} objects"
    extra = len(groups) - len(ranked)
    tail = f". And {extra} more." if extra > 0 else "."
    return f"{header}. " + ". ".join(capitalize(p) for p in parts) + tail


def describe_path(detections, settings):
    """Answer "is the way ahead clear?" using only objects in the walking corridor."""
    in_path = sorted((d for d in detections if d.in_path and d.category != SIGNAL),
                     key=lambda d: d.distance)
    if not in_path:
        return "Path ahead looks clear."
    nearest = in_path[0]
    dist = format_distance(nearest.distance, settings.units, settings.step_length)
    text = f"{capitalize(spoken_name(nearest.label))} in your path, {dist}"
    # Suggest the side with more room: whichever half of the view has fewer
    # nearby obstacles. Only a hint - the user's cane/dog has the final say.
    left = sum(1 for d in detections if d.angle < -5 and d.distance < settings.warning_distance)
    right = sum(1 for d in detections if d.angle > 5 and d.distance < settings.warning_distance)
    if nearest.distance < settings.warning_distance and left != right:
        text += ". More room on your " + ("right" if left > right else "left")
    return text + "."
