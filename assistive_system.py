import cv2
from ultralytics import YOLO
import pyttsx3
import time
import threading

# Initialize YOLO model
model = YOLO('yolov8n.pt')

# Threaded speak function to prevent freezing
def speak(text):
    def _run_speech():
        try:
            # Initialize engine inside the thread to avoid Windows COM thread issues
            th_engine = pyttsx3.init()
            th_engine.setProperty('rate', 170)  # slightly faster speech
            th_engine.say(text)
            th_engine.runAndWait()
        except Exception as e:
            print(f"Speech error: {e}")

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

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]
                
                if class_id in [0, 1, 2, 39, 56, 62, 63]:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    obj_center_x = (x1 + x2) // 2
                    
                    # Direction mapping
                    if obj_center_x < (width * 0.35):
                        direction = "on your left"
                    elif obj_center_x > (width * 0.65):
                        direction = "on your right"
                    else:
                        direction = "straight ahead"

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
                    latest_detections.append((x1, y1, x2, y2, label, proximity))
                    obstacles_detected.append(f"{label} {direction}, {proximity}")

        last_inference_time = current_time

        # 2. Speak warnings if any are detected (already handled by cooldown)
        if obstacles_detected and (current_time - last_speech_time > speech_cooldown):
            warning_msg = obstacles_detected[0]
            print(f"Alert: {warning_msg}")
            speak(warning_msg)
            last_speech_time = current_time

    # 3. Draw the LATEST detections on the live frame (keeps visuals smooth)
    for x1, y1, x2, y2, label, proximity in latest_detections:
        color = (0, 0, 255) if proximity == "very close" else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{label} ({proximity})", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


    # Draw vertical divider lines on the frame for visual debugging
    cv2.line(frame, (int(width * 0.35), 0), (int(width * 0.35), height), (255, 255, 255), 1)
    cv2.line(frame, (int(width * 0.65), 0), (int(width * 0.65), height), (255, 255, 255), 1)

    cv2.imshow("Assistive System Feed", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
