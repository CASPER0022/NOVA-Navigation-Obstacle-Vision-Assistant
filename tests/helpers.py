from nova.perception import Detection, OBJECT_CATALOG, clock_position

_next_id = [1000]


def make_det(label="person", distance=3.0, angle=0.0, in_path=True, hits=3,
             closing_speed=0.0, track_id=None, bbox=(100, 100, 200, 300)):
    if track_id is None:
        _next_id[0] += 1
        track_id = _next_id[0]
    det = Detection(label=label, category=OBJECT_CATALOG[label][0], bbox=bbox,
                    confidence=0.9, distance=distance, angle=angle,
                    clock=clock_position(angle), in_path=in_path, track_id=track_id,
                    closing_speed=closing_speed, first_seen=0.0)
    det.extra["hits"] = hits
    return det
