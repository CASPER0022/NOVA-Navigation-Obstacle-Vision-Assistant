import argparse
import cv2
from ultralytics import YOLO
import os
import pyttsx3
import time
import threading
import queue
from collections import deque
import sys
import atexit

from metrics_logger import MetricsLogger

# winsound is Windows-only (this project already assumes Windows via CAP_DSHOW);
# degrade gracefully to no earcons on other platforms instead of crashing.
try:
    import winsound
    EARCONS_AVAILABLE = True
except ImportError:
    EARCONS_AVAILABLE = False

# Initialize YOLO model
model = YOLO('yolov8n.pt')

metrics = MetricsLogger()

# Thread-safe queue for speech requests
speech_queue = queue.Queue()

# Reference to whichever pyttsx3 engine is currently mid-utterance, so a
# critical alert can interrupt it from another thread (see speak() below).
current_engine = None
current_engine_lock = threading.Lock()

# Speech worker running in a single dedicated background thread
def speech_worker():
    global current_engine
    while True:
        # Block until a speech request is available
        priority, text = speech_queue.get()
        try:
            metrics.log_tts_event("attempt", text)
            # Initialize fresh engine inside the loop to avoid Windows COM thread resource issues
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)  # slightly faster speech
            with current_engine_lock:
                current_engine = engine
            engine.say(text)
            engine.runAndWait()
            with current_engine_lock:
                current_engine = None
            # Clean up reference
            del engine
            metrics.log_tts_event("success", text)
        except Exception as e:
            print(f"Speech worker error: {e}")
            metrics.log_tts_event("error", str(e))
        finally:
            # Always mark the task done, even on failure, so anything waiting
            # on speech_queue.join() (e.g. the shutdown announcement) can't hang.
            speech_queue.task_done()

# Start the speech worker thread immediately
threading.Thread(target=speech_worker, daemon=True).start()


# Threaded speak function to prevent freezing and ensure message queuing.
# priority=0 (critical) interrupts whatever is currently being spoken so a
# "very close" hazard is never delayed behind a lower-priority message.
def speak(text, priority=1):
    # Clear any pending speech tasks so we only announce the most recent hazard
    while not speech_queue.empty():
        try:
            speech_queue.get_nowait()
            speech_queue.task_done()
        except queue.Empty:
            break

    if priority == 0:
        with current_engine_lock:
            if current_engine is not None:
                try:
                    current_engine.stop()
                except Exception:
                    pass

    speech_queue.put((priority, text))


# Short, distinct tones per proximity tier, played in a background thread so
# they never block the frame loop. TTS takes time to generate/speak, so an
# instant earcon lets the user react to urgency before the words finish.
def play_earcon(proximity):
    if not EARCONS_AVAILABLE:
        return

    def _beep():
        try:
            if proximity == "very close":
                winsound.Beep(1200, 100)
                winsound.Beep(1200, 100)
            elif proximity == "moderately close":
                winsound.Beep(800, 150)
            else:
                winsound.Beep(500, 150)
        except RuntimeError:
            pass

    threading.Thread(target=_beep, daemon=True).start()


# Track the last time a warning was spoken to avoid overlapping audio
last_speech_time = 0
speech_cooldown = 3.0  # Speak warnings at most every 3 seconds

# Global state tracking for active hazards and heartbeat alerts
active_hazards = {}        # (label, direction) -> (last_seen_time, proximity)
last_heartbeat_times = {}  # (label, direction) -> last_alert_time
first_seen_ts = {}         # (label, direction) -> time first detected, for alert-latency metrics

# Scan for all active camera indices (tests 0 to 4) using DirectShow (Windows optimized)
def get_best_camera_index():
    working_indices = []
    for i in range(5):
        # cv2.CAP_DSHOW prevents long timeouts on empty indices in Windows
        temp_cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if temp_cap.isOpened():
            ret, frame = temp_cap.read()
            if ret:
                working_indices.append(i)
            temp_cap.release()

    if not working_indices:
        print("No active cameras detected. Defaulting to index 0.")
        return 0

    print(f"Detected working camera indices: {working_indices}")
    # On laptops with built-in cameras, index 0 is typically the external USB webcam if plugged in,
    # or index 0 vs 1 depends on system order. If 0 is available, prefer 0 over 1, or let user override.
    selected_index = working_indices[0] if 0 in working_indices else working_indices[-1]
    print(f"Auto-selected Camera Index {selected_index} (preferring Index 0 for external USB webcam).")
    return selected_index


class ImageDirectoryCapture:
    """Mimics cv2.VideoCapture's read()/release()/isOpened() interface over a
    directory of still images, so --input can point at a folder of frames as
    well as a video file without touching the main loop below."""

    _EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp')

    def __init__(self, dir_path):
        self._paths = sorted(
            os.path.join(dir_path, f) for f in os.listdir(dir_path)
            if f.lower().endswith(self._EXTENSIONS)
        )
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


def parse_args():
    parser = argparse.ArgumentParser(description="NOVA assistive navigation system")
    parser.add_argument('camera_index', nargs='?', type=int, default=None,
                         help='(legacy positional form) camera index, equivalent to --camera')
    parser.add_argument('--camera', type=int, default=None,
                         help='Manually specify the webcam index to use (skips auto-scan)')
    parser.add_argument('--input', type=str, default=None,
                         help='Path to a video file or a directory of images to run on '
                              'instead of a live camera (e.g. for demos or regression tests)')
    parser.add_argument('--headless', action='store_true',
                         help='Do not open a GUI window (skips cv2.imshow/waitKey); '
                              'use with --input for automated/offline runs')
    return parser.parse_args()


args = parse_args()

if args.input:
    if os.path.isdir(args.input):
        print(f"Using image directory as input: {args.input}")
        cap = ImageDirectoryCapture(args.input)
    else:
        print(f"Using video file as input: {args.input}")
        cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        print(f"Could not open input: {args.input}")
        raise SystemExit(1)
else:
    # Allow manual override via command line parameter: python .\assistive_system.py <index>
    manual_index = args.camera if args.camera is not None else args.camera_index
    if manual_index is not None:
        camera_index = manual_index
        print(f"Using manually specified Camera Index: {camera_index}")
    else:
        print("----------------------------------------------------------------")
        print("Tip: If the system uses the wrong camera, override it by running:")
        print("     python .\\assistive_system.py <index>   (or --camera <index>)")
        print("     Example: python .\\assistive_system.py 0   (to use index 0)")
        print("     To run on a recorded video/image folder instead: --input <path>")
        print("----------------------------------------------------------------")
        camera_index = get_best_camera_index()
    cap = cv2.VideoCapture(camera_index)

# Attempt to recover from a lost/disconnected camera instead of dying silently.
# Retries for up to max_wait seconds, announcing status changes so a blind user
# isn't left with a frozen, unexplained silence.
def reconnect_camera(index, max_wait=30.0, retry_delay=1.0):
    speak("Camera lost. Reconnecting.", priority=0)
    print("Camera read failed. Attempting to reconnect...")
    start_time = time.time()
    while time.time() - start_time < max_wait:
        temp_cap = cv2.VideoCapture(index)
        if temp_cap.isOpened():
            ret, _ = temp_cap.read()
            if ret:
                speak("Camera reconnected.", priority=0)
                print("Camera reconnected successfully.")
                return temp_cap
        temp_cap.release()
        time.sleep(retry_delay)
    speak("Camera unavailable. Shutting down.", priority=0)
    print("Camera reconnection timed out. Giving up.")
    return None

if not cap.isOpened():
    cap = reconnect_camera(camera_index)
    if cap is None:
        sys.exit(1)

# Accessible shutdown: Ctrl+C works from the terminal without needing to see
# or focus the (sighted-only) preview window, unlike the 'q' key below. Suppress
# the raw traceback so it doesn't look like a crash, and always announce the
# shutdown out loud before the process actually exits.
def _friendly_keyboard_interrupt(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        print("\nStop requested. Shutting down.")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _friendly_keyboard_interrupt

def _announce_shutdown():
    # Runs on every exit path (normal quit, sys.exit, or Ctrl+C) since atexit
    # fires on interpreter shutdown regardless of how it was triggered.
    speak("Shutting down.", priority=0)
    speech_queue.join()
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()

atexit.register(_announce_shutdown)

# Announce readiness out loud: a blind user can't see console output or the
# preview window, so this is the only confirmation the system actually started
# and what it's about to do.
speak("System ready. Monitoring the path ahead. Press control C in this window to stop.")
print("System ready. Listening for obstacles.")

# Track inference rate (1 detection run per second)
last_inference_time = 0
inference_interval = 1.0  # seconds
last_inference_duration = 0.0
# Store the latest bounding boxes to draw between runs
latest_detections = []

<<<<<<< Updated upstream
# Rolling frame-time window for FPS measurement
frame_times = deque(maxlen=60)
last_fps_log_time = 0.0
=======
# Heartbeat: periodically confirm "path clear" so silence can't be mistaken
# for a frozen/crashed system when no hazards are present.
last_hazard_free_announcement = 0
path_clear_interval = 15.0  # seconds between "path clear" reminders
>>>>>>> Stashed changes

while True:
    ret, frame = cap.read()
    if not ret:
        cap.release()
        cap = reconnect_camera(camera_index)
        if cap is None:
            break
        continue

    height, width, _ = frame.shape
    current_time = time.time()

    # Track effective display FPS, independent of the once-per-second inference cadence
    frame_times.append(current_time)
    if len(frame_times) >= 2:
        fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])
        cv2.putText(frame, f"FPS: {fps:.1f}", (width - 120, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        if current_time - last_fps_log_time >= 1.0:
            metrics.log_fps_sample(fps)
            last_fps_log_time = current_time

    # 1. Run inference ONLY if 1 second has passed
    if current_time - last_inference_time >= inference_interval:
        inference_start = time.time()
        results = model(frame, stream=False, verbose=False) # verbose=False cleans up console output
        last_inference_duration = time.time() - inference_start
        latest_detections = []
        obstacles_detected = []
        current_seen_keys = set()

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]

                if class_id in [0, 1, 2, 39, 56, 62, 63]:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    obj_center_x = (x1 + x2) // 2

                    # Clock-Position mapping (9 o'clock to 3 o'clock)
                    x_norm = obj_center_x / width
                    hour_val = round(9 + x_norm * 6)
                    if hour_val > 12:
                        hour_val -= 12
                    direction = f"at {hour_val} o'clock"

                    # Distance mapping using estimated physical width (meters)
                    ESTIMATED_REAL_WIDTHS = {
                        'person': 0.45,
                        'chair': 0.50,
                        'bottle': 0.08,
                        'cup': 0.08,
                        'backpack': 0.35,
                        'handbag': 0.30,
                        'suitcase': 0.40,
                        'laptop': 0.35,
                        'cell phone': 0.08
                    }
                    real_width = ESTIMATED_REAL_WIDTHS.get(label, 0.30)

                    obj_width = x2 - x1
                    width_ratio = max(0.001, obj_width / width)
                    estimated_distance = real_width / width_ratio

                    # Determine proximity category based on estimated distance
                    if estimated_distance < 1.0:
                        proximity = "very close"
                    elif estimated_distance < 2.0:
                        proximity = "moderately close"
                    else:
                        proximity = "far"

                    # Save detection for drawing
                    latest_detections.append((x1, y1, x2, y2, label, proximity, direction, estimated_distance))

                    # State machine tracking logic
                    hazard_key = (label, direction)
                    current_seen_keys.add(hazard_key)

                    is_new = hazard_key not in active_hazards
                    proximity_got_closer = False
                    is_heartbeat = False

                    if is_new:
                        first_seen_ts[hazard_key] = current_time

                    if not is_new:
                        _, old_proximity = active_hazards[hazard_key]
                        proximity_levels = {"very close": 0, "moderately close": 1, "far": 2}
                        if proximity_levels[proximity] < proximity_levels[old_proximity]:
                            proximity_got_closer = True

                        # Trigger alert for very close items if heartbeat interval has passed
                        if proximity == "very close":
                            last_hb = last_heartbeat_times.get(hazard_key, 0)
                            if current_time - last_hb > 6.0:  # 6 seconds reminder heartbeat
                                is_heartbeat = True

                    # Update the state of the active hazard
                    active_hazards[hazard_key] = (current_time, proximity)

                    # Only queue speech warning if it's a new threat, got closer, or hit the heartbeat reminder
                    if is_new or proximity_got_closer or is_heartbeat:
                        obstacles_detected.append({
                            'text': f"{label} {direction}, {proximity}",
                            'estimated_distance': estimated_distance,
                            'proximity': proximity,
                            'hazard_key': hazard_key
                        })
                        last_heartbeat_times[hazard_key] = current_time

        last_inference_time = current_time

        # Stale hazard cleanup: remove objects that haven't been seen in the last 2 seconds
        stale_keys = []
        for key in list(active_hazards.keys()):
            if key not in current_seen_keys:
                last_seen_time, _ = active_hazards[key]
                if current_time - last_seen_time > 2.0:
                    stale_keys.append(key)

        for key in stale_keys:
            del active_hazards[key]
            if key in last_heartbeat_times:
                del last_heartbeat_times[key]
            if key in first_seen_ts:
                del first_seen_ts[key]

        # Sort obstacles by estimated_distance ascending (closest first)
        obstacles_detected.sort(key=lambda x: x['estimated_distance'])

        # 2. Speak warnings if any are detected (already filtered by state machine)
        if obstacles_detected:
            closest_obstacle = obstacles_detected[0]
            proximity = closest_obstacle['proximity']

            # Dynamic cooldown: faster pulses for closer threats
            if proximity == "very close":
                dynamic_cooldown = 1.0
            elif proximity == "moderately close":
                dynamic_cooldown = 2.5
            else:
                dynamic_cooldown = 4.0

            if current_time - last_speech_time > dynamic_cooldown:
                warning_msg = closest_obstacle['text']
                print(f"Alert: {warning_msg} (Cooldown: {dynamic_cooldown}s)")
                # Play an instant earcon before the (slower) TTS phrase, so the
                # user gets an urgency cue immediately rather than waiting for
                # speech synthesis to catch up.
                play_earcon(proximity)
                # "Very close" hazards are safety-critical: let them interrupt
                # whatever lower-priority phrase is currently being spoken.
                speak(warning_msg, priority=0 if proximity == "very close" else 1)
                speak_ts = time.time()
                detect_ts = first_seen_ts.get(closest_obstacle['hazard_key'], current_time)
                metrics.log_alert_latency(closest_obstacle['hazard_key'][0], detect_ts, speak_ts, last_inference_duration)
                last_speech_time = current_time

            # Reset the clear-path timer so "Path clear" doesn't fire right
            # after a hazard stops being announced.
            last_hazard_free_announcement = current_time
        elif not active_hazards:
            # Nothing detected at all: periodically confirm the system is alive
            # and the path is clear, so silence isn't mistaken for a crash/freeze.
            if current_time - last_hazard_free_announcement > path_clear_interval:
                print("Heartbeat: Path clear")
                speak("Path clear")
                last_hazard_free_announcement = current_time

    # 3. Draw the LATEST detections on the live frame (keeps visuals smooth)
    for x1, y1, x2, y2, label, proximity, direction, est_dist in latest_detections:
        color = (0, 0, 255) if proximity == "very close" else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{label} ({direction}, {proximity})", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # 4. Draw direction arrow pointing to the nearest hazard
    if latest_detections:
        # Find closest detection based on estimated_distance (index 7)
        closest = min(latest_detections, key=lambda x: x[7])
        x1, y1, x2, y2, label, proximity, direction, est_dist = closest
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        start_pt = (width // 2, height - 40)
        end_pt = (cx, cy)

        # Color based on proximity
        arrow_color = (0, 0, 255) if proximity == "very close" else (0, 165, 255)
        cv2.arrowedLine(frame, start_pt, end_pt, arrow_color, 3, tipLength=0.15)
        cv2.circle(frame, start_pt, 6, (255, 0, 0), -1)

        # Overlay warning text at the bottom
        cv2.putText(frame, f"HAZARD: {label.upper()} ({direction})", (20, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, arrow_color, 2)

    # Draw clock sector boundaries and labels on the frame for visual debugging
    # Boundaries: 1/12, 3/12, 5/12, 7/12, 9/12, 11/12 of width
    boundaries = [1/12, 3/12, 5/12, 7/12, 9/12, 11/12]
    for b in boundaries:
        bx = int(width * b)
        cv2.line(frame, (bx, 0), (bx, height), (150, 150, 150), 1)

    # Sector labels at the top
    sectors = [
        (0.5/12, "9"),
        (2/12, "10"),
        (4/12, "11"),
        (6/12, "12"),
        (8/12, "1"),
        (10/12, "2"),
        (11.5/12, "3")
    ]
    for pct, label_str in sectors:
        lx = int(width * pct)
        cv2.putText(frame, f"{label_str}H", (lx - 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    if not args.headless:
        cv2.imshow("Assistive System Feed", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Cleanup and the spoken shutdown confirmation happen in _announce_shutdown(),
# registered via atexit, so they run on every exit path (including Ctrl+C).
def _announce_shutdown_metrics():
    metrics.close()

atexit.register(_announce_shutdown_metrics)
