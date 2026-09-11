# Metrics Instrumentation Plan (branch: `metrics`)

Scope: instrument [assistive_system.py](assistive_system.py) to measure and log the three metrics
that don't require a physical ground-truth course (tape-measured distances/angles). Distance
accuracy (#3) and false-negative-rate-by-position (#4) are deferred — they need a taped test
course and are tracked separately in `next_steps.md` under the real-world distance item.

## Metrics in scope

1. **End-to-end alert latency** — time from an obstacle first appearing in a detection cycle to
   the moment it is actually spoken (may be delayed by the 3s speech cooldown). Also log raw
   YOLO inference duration per cycle, since that's a separate contributor to latency.
2. **TTS failure / overlap rate** — every `speak()` call attempt and every exception raised
   inside the speech thread, so `failures / attempts` can be computed over a run.
3. **Effective display FPS** — rolling average of the main loop's frame interval, independent of
   the once-per-second inference cadence, to confirm the decoupled-inference design is actually
   keeping the display smooth.

## Approach

- New module `metrics_logger.py`: a small `MetricsLogger` class, no external dependencies beyond
  stdlib (`csv`, `time`, `collections.deque`), so it doesn't add new pip requirements.
  - `log_alert_latency(label, detect_ts, speak_ts, inference_duration)` → appends a row to
    `logs/alert_latency.csv`.
  - `log_tts_event(event_type, message="")` → appends a row to `logs/tts_events.csv`
    (`event_type` is `attempt`, `success`, or `error`).
  - `log_fps_sample(fps)` → appends a row to `logs/fps.csv`, sampled roughly once/sec (not every
    frame, to keep the file small and avoid I/O overhead on the hot loop).
  - CSV files are opened in append mode once at startup and flushed per-row (buffer loss on crash
    is unacceptable for a "measure the crash rate" metric).
- `logs/` is added to `.gitignore` — logged data is a run artifact, not source.
- Changes to `assistive_system.py`:
  - Track `first_seen_ts` per obstacle label in a dict, cleared when that label is no longer
    detected in a cycle. When a warning is actually spoken, compute latency vs. that label's
    first-seen timestamp and log it.
  - Time the `model(frame, ...)` call and log inference duration alongside the latency row.
  - Wrap the existing `speak()` attempt/exception paths with `log_tts_event` calls.
  - Track a rolling frame-time deque in the main loop, compute FPS once per ~1s, log it, and
    also draw it on-screen (`FPS: NN`) since it's useful for the live demo too.
- No behavioral change to detection/speech logic itself — purely additive logging, so existing
  functionality (and the known TTS race bug, until it's fixed separately) is unaffected.

## Testing plan

- Sandbox environment likely has no webcam, so full end-to-end camera testing isn't possible
  here. Verify instead by:
  - Static syntax/import check (`python -m py_compile`).
  - A short synthetic-frame test (`cv2.VideoCapture` replaced with a dummy source generating
    blank/random frames, or mocking `model()`'s return) to confirm the logger writes valid CSV
    rows without crashing the loop, then inspect the CSV output.
- Real webcam verification (actual latency numbers, actual TTS behavior) is left for the user to
  run locally, per the "how to run" instructions already given.

## Out of scope for this branch

- Distance MAE / false-negative-by-position metrics (need taped course).
- The TTS concurrency fix itself (next_steps.md #5) — this branch only adds the instrumentation
  to measure it, not the fix.
