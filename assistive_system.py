import cv2
from ultralytics import YOLO
import pyttsx3
import time
import threading
import queue
import sys

# Initialize YOLO model
model = YOLO('yolov8n.pt')

# Thread-safe queue for speech requests
speech_queue = queue.Queue()

# Speech worker running in a single dedicated background thread
def speech_worker():
    while True:
        try:
            # Block until a speech request is available
            text = speech_queue.get()
            # Initialize fresh engine inside the loop to avoid Windows COM thread resource issues
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)  # slightly faster speech
            engine.say(text)
            engine.runAndWait()
            # Clean up reference
            del engine
            speech_queue.task_done()
        except Exception as e:
            print(f"Speech worker error: {e}")

# Start the speech worker thread immediately
threading.Thread(target=speech_worker, daemon=True).start()


# Threaded speak function to prevent freezing and ensure message queuing
def speak(text):
    # Clear any pending speech tasks so we only announce the most recent hazard
    while not speech_queue.empty():
        try:
            speech_queue.get_nowait()
            speech_queue.task_done()
        except queue.Empty:
            break
    speech_queue.put(text)


# Track the last time a warning was spoken to avoid overlapping audio
last_speech_time = 0 
speech_cooldown = 3.0  # Speak warnings at most every 3 seconds

# Global state tracking for active hazards and heartbeat alerts
active_hazards = {}        # (label, direction) -> (last_seen_time, proximity)
last_heartbeat_times = {}  # (label, direction) -> last_alert_time

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
    selected_index = working_indices[-1]
    print(f"Auto-selected Camera Index {selected_index} (highest index).")
    return selected_index

# Allow manual override via command line parameter: python .\assistive_system.py <index>
if len(sys.argv) > 1:
    try:
        camera_index = int(sys.argv[1])
        print(f"Using manually specified Camera Index: {camera_index}")
    except ValueError:
        print("Invalid index format. Running auto-scan...")
        camera_index = get_best_camera_index()
else:
    print("----------------------------------------------------------------")
    print("Tip: If the system uses the wrong camera, override it by running:")
    print("     python .\\assistive_system.py <index>")
    print("     Example: python .\\assistive_system.py 0   (to use index 0)")
    print("----------------------------------------------------------------")
    camera_index = get_best_camera_index()

cap = cv2.VideoCapture(camera_index)

# Track inference rate (1 detection run per second)
last_inference_time = 0
inference_interval = 1.0  # seconds
# Store the latest bounding boxes to draw between runs
latest_detections = []

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width, _ = frame.shape
    current_time = time.time()
    
    # 1. Run inference ONLY if 1 second has passed
    if current_time - last_inference_time >= inference_interval:
        results = model(frame, stream=False, verbose=False) # verbose=False cleans up console output
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
                            'proximity': proximity
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
                speak(warning_msg)
                last_speech_time = current_time

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

    cv2.imshow("Assistive System Feed", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
