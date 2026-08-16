import cv2
from ultralytics import YOLO
import pyttsx3
import time
import threading
from collections import deque

from metrics_logger import MetricsLogger

# Initialize YOLO model
model = YOLO('yolov8n.pt')

metrics = MetricsLogger()

# Threaded speak function to prevent freezing
def speak(text):
    metrics.log_tts_event("attempt", text)

    def _run_speech():
        try:
            # Initialize engine inside the thread to avoid Windows COM thread issues
            th_engine = pyttsx3.init()
            th_engine.setProperty('rate', 170)  # slightly faster speech
            th_engine.say(text)
            th_engine.runAndWait()
            metrics.log_tts_event("success", text)
        except Exception as e:
            print(f"Speech error: {e}")
            metrics.log_tts_event("error", str(e))

    # Start speech in a daemon background thread
    threading.Thread(target=_run_speech, daemon=True).start()


# Track the last time a warning was spoken to avoid overlapping audio
last_speech_time = 0 
speech_cooldown = 3.0  # Speak warnings at most every 3 seconds

cap = cv2.VideoCapture(0)

# Track inference rate (1 detection run per second)
last_inference_time = 0
inference_interval = 1.0  # seconds
# Store the latest bounding boxes to draw between runs
latest_detections = []

# Track when each obstacle label was first seen, to measure alert latency
first_seen_ts = {}
# Labels already logged (so repeat cooldown-throttled warnings for a still-present
# object don't re-log ever-growing "latency" against the original first-seen time)
latency_logged_labels = set()
last_inference_duration = 0.0

# Rolling frame-time window for FPS measurement
frame_times = deque(maxlen=60)
last_fps_log_time = 0.0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width, _ = frame.shape
    current_time = time.time()

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
        seen_labels_this_cycle = set()

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

                    # Distance mapping
                    obj_width = x2 - x1
                    width_ratio = obj_width / width
                    if width_ratio > 0.4:
                        proximity = "very close"
                    elif width_ratio > 0.2:
                        proximity = "moderately close"
                    else:
                        proximity = "far"

                    # Save detection for drawing and speaking
                    latest_detections.append((x1, y1, x2, y2, label, proximity, direction, width_ratio))
                    obstacles_detected.append({
                        'text': f"{label} {direction}, {proximity}",
                        'width_ratio': width_ratio,
                        'label': label
                    })

                    seen_labels_this_cycle.add(label)
                    if label not in first_seen_ts:
                        first_seen_ts[label] = current_time

        # Drop labels that are no longer in frame so a future re-appearance
        # is timed as a fresh detection, not stale latency.
        for stale_label in list(first_seen_ts.keys()):
            if stale_label not in seen_labels_this_cycle:
                del first_seen_ts[stale_label]
                latency_logged_labels.discard(stale_label)

        last_inference_time = current_time

        # Sort obstacles by proximity (width_ratio descending = closest first)
        obstacles_detected.sort(key=lambda x: x['width_ratio'], reverse=True)

        # 2. Speak warnings if any are detected (already handled by cooldown)
        if obstacles_detected and (current_time - last_speech_time > speech_cooldown):
            top_obstacle = obstacles_detected[0]
            warning_msg = top_obstacle['text']
            print(f"Alert: {warning_msg}")
            speak(warning_msg)
            speak_ts = time.time()
            label = top_obstacle['label']
            if label not in latency_logged_labels:
                detect_ts = first_seen_ts.get(label, current_time)
                metrics.log_alert_latency(label, detect_ts, speak_ts, last_inference_duration)
                latency_logged_labels.add(label)
            last_speech_time = current_time

    # 3. Draw the LATEST detections on the live frame (keeps visuals smooth)
    for x1, y1, x2, y2, label, proximity, direction, w_ratio in latest_detections:
        color = (0, 0, 255) if proximity == "very close" else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{label} ({direction}, {proximity})", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # 4. Draw direction arrow pointing to the nearest hazard
    if latest_detections:
        # Find closest detection based on width_ratio
        closest = max(latest_detections, key=lambda x: x[7])
        x1, y1, x2, y2, label, proximity, direction, w_ratio = closest
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

    cv2.imshow("Assistive System Feed", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
metrics.close()
