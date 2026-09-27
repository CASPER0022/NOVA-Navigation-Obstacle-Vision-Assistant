# 🚀 Project Roadmap & Next Steps

This document outlines the features and milestones of the **NOVA (Navigation & Obstacle Vision Assistant)** project.

---

## ✅ Completed Tasks

### 1. 🕒 Clock-Position System
- **Goal:** Provide intuitive direction guidance using the clock face (e.g., `"Person at 11 o'clock"`) instead of basic `"Left/Right"` descriptions.
- **Status:** **Completed** 🟢
- **Details:** Divided the horizontal frame space into 6 sectors representing 9 o'clock to 3 o'clock.

### 2. 🎯 Prioritize by Proximity
- **Goal:** Announce the closest obstacle first rather than relying on arbitrary YOLO detection order.
- **Status:** **Completed** 🟢
- **Details:** Sorted detections dynamically using `width_ratio` as a distance proxy.

### 3. 🏹 Visual Direction Arrows & Overlay
- **Goal:** Draw a dynamic, color-coded vector arrow from the bottom center to the nearest hazard.
- **Status:** **Completed** 🟢
- **Details:** Displays a red arrow for `very close` items and orange/yellow for others, along with a warning dashboard overlay at the bottom.

### 4. 🧵 Concurrency Run Loop Fix (Speech Engine)
- **Goal:** Fix the `Speech error: run loop already started` bug.
- **Status:** **Completed** 🟢
- **Details:** Implemented a thread-safe message queue (`queue.Queue`) and a single dedicated daemon background thread worker to serialize all text-to-speech requests, avoiding concurrent engine runs.

### 5. 🔊 Auditory Pulse Warning Frequency
- **Goal:** Vary warning frequency dynamically based on distance.
- **Status:** **Completed** 🟢
- **Details:** Replaced the static 3-second alert cooldown with a dynamic alert frequency. The rate scales dynamically based on the closest hazard's proximity (1.0s for `very close`, 2.5s for `moderately close`, and 4.0s for `far` objects), mimicking an auditory radar.

### 6. 📏 Real-World Distance Estimation (Meters)
- **Goal:** Calculate actual distance in meters instead of relative width categories.
- **Status:** **Completed** 🟢
- **Details:** Calibrated average physical widths of objects (e.g. 8cm for a bottle, 45cm for a person) to calculate an estimated distance using `real_width / width_ratio`. This correctly prioritizes physically smaller close objects (like a bottle) over physically larger, further objects (like a person).

### 7. 👁️ State Tracking & Change Detection (Stop Repetitive Alerts)
- **Goal:** Stop repeating the same warnings if the environment hasn't changed.
- **Status:** **Completed** 🟢
- **Details:** Created an active-hazard tracking state machine. The system only announces new hazards, hazards that get closer, or critical "very close" hazards at a slow, non-intrusive heartbeat interval (6 seconds).

### 8. 📊 Metrics Instrumentation (Latency, TTS reliability, FPS)
- **Goal:** Add lightweight logging to measure end-to-end alert latency, TTS failure/overlap rate, and display FPS, so future changes can be verified with before/after numbers.
- **Status:** **Completed** 🟢
- **Details:** See `metrics_plan.md` for methodology. Logs written as CSVs under `logs/`. Summarize a run (or compare two runs before/after a change) with `python analyze_metrics.py [--log-dir logs] [--compare other_logs_dir] [--json]`.

### 9. 🎬 Recorded Video / Image Input Mode
- **Goal:** Run the pipeline against a saved video file or a folder of still images instead of only a live webcam, so demos and regression tests don't require hardware.
- **Status:** **Completed** 🟢
- **Details:** `--input <path>` accepts either a video file or a directory of images. `--headless` skips `cv2.imshow`/`waitKey` for automated runs.

### 10. 🔌 Camera Reconnect & Failure Recovery
- **Goal:** Stop the system from dying silently when the camera disconnects or fails to open.
- **Status:** **Completed** 🟢
- **Details:** Added `reconnect_camera()`, which retries opening the camera for up to 30 seconds with a 1-second backoff whenever a frame read fails.

### 11. 💚 Audible "Path Clear" Heartbeat
- **Goal:** Let the user distinguish "no obstacles detected" from "the system has frozen/crashed".
- **Status:** **Completed** 🟢
- **Details:** Speaks `"Path clear"` every 15 seconds when no active hazards are present.

### 12. 🗣️ Spoken Startup Confirmation
- **Goal:** Confirm the system actually started and is monitoring.
- **Status:** **Completed** 🟢
- **Details:** Speaks `"System ready. Monitoring the path ahead."` on initialization.

### 13. ⌨️ Accessible Quit (Ctrl+C) with Spoken Shutdown
- **Goal:** Remove dependency on the preview window for quitting.
- **Status:** **Completed** 🟢
- **Details:** Terminal `Ctrl+C` triggers graceful shutdown, speaking `"Shutting down."` on exit.

### 14. 🔔 Urgency Earcons
- **Goal:** Give an instant, wordless urgency cue before the spoken phrase.
- **Status:** **Completed** 🟢
- **Details:** Plays distinct proximity tones (`winsound.Beep`) in a background thread.

### 15. ⚡ Preemptible Critical Speech
- **Goal:** Stop a "very close" hazard from being delayed behind a lower-priority phrase.
- **Status:** **Completed** 🟢
- **Details:** Priority-0 alerts interrupt active pyttsx3 speech immediately.

### 16. 🧱 Modular Package & Test Suite (v1.0)
- **Goal:** Replace the single global-state script with maintainable, testable modules.
- **Status:** **Completed** 🟢
- **Details:** `nova/` package (capture, perception, tracker, alerts, audio, controls, environment, traffic_light, scene, hud, app) plus 50+ pytest tests that need no camera, speakers or model. This also fixed a committed merge-conflict marker that stopped the program from starting, and a crash at the end of `--input` videos.

### 17. 📐 True-Angle Clock Positions & Pinhole Distances
- **Goal:** Make directions and distances physically correct.
- **Status:** **Completed** 🟢
- **Details:** Clock hours now equal 30° (the O&M convention), computed from the camera's field of view (`--hfov`). Distances come from a pinhole model using object height or width, whichever isn't cut off by the frame edge, and err towards "closer".

### 18. 🚶 Walking-Corridor Awareness & Urgency Levels
- **Goal:** Warn about what is actually in the user's way, not everything in view.
- **Status:** **Completed** 🟢
- **Details:** Objects are projected to lateral meters and tested against a configurable corridor. Alerts are critical ("Stop. …", interrupts speech), warning or info.

### 19. 🎯 Multi-Object Tracking, Approach Detection & Time-to-Contact
- **Goal:** Stable object identities, fewer false alarms, early warning for fast movers.
- **Status:** **Completed** 🟢
- **Details:** IoU tracker with debounce and least-squares closing speed. Collision-course objects become critical, and approaching vehicles are announced as such. Unspoken alerts are no longer silently dropped.

### 20. ⌨️ On-Demand Keyboard Commands
- **Goal:** Let the user ask instead of only being told.
- **Status:** **Completed** 🟢
- **Details:** Describe surroundings, "is the path ahead clear?" (with a free-side hint), repeat, quiet mode, pause, detail level, units, speech rate and help. Keys are read from the terminal (screen-reader friendly), and preferences persist to `nova_config.json`.

### 21. 🎧 Spatial (Stereo-Panned) Earcons
- **Goal:** Convey direction before the words finish.
- **Status:** **Completed** 🟢
- **Details:** Synthesised WAV tones whose pitch/pattern encode urgency and whose left/right balance encodes direction.

### 22. 🩺 Camera Health Monitoring
- **Goal:** Never let "can't see" sound like "path clear".
- **Status:** **Completed** 🟢
- **Details:** Detects dark scenes, a blocked lens, blur and a frozen feed, and announces recovery.

### 23. 🚦 Traffic-Light Colour Reading
- **Goal:** Report the colour of the nearest traffic light.
- **Status:** **Completed** 🟢
- **Details:** HSV classification inside the YOLO box, confirmed over two cycles, phrased as "appears …". This is an aid only.

### 24. ⚙️ Configuration File, Units & Voice Selection
- **Goal:** Personalise NOVA without long command lines.
- **Status:** **Completed** 🟢
- **Details:** `nova_config.json` (see `nova_config.example.json`), `--save-config`, meters/steps/feet, `--voice`, `--list-voices`, `--list-cameras`.

### 24b. 🤫 Announce-Once Alerting
- **Goal:** Stop repeated "Stop." alerts about an object the user already knows about.
- **Status:** **Completed** 🟢
- **Details:** Warnings are said once and critical alerts at most `critical_repeats` times (default 2). An object speaks again only if its urgency rises. Short dropouts and label flicker (TV ↔ laptop) keep the same memory. Space/A answer from everything seen in the last second instead of a single frame.

---

## 🏃 Upcoming Tasks (Next Steps)

### 25. 🎙️ Voice Commands & Wake Word
- **Goal:** Hands-free versions of the keyboard commands (the user may be holding a cane).
- **Description:** An offline STT listener (e.g. Vosk) that maps phrases like *"what's around me?"* or *"is the path clear?"* onto the existing command handlers in `nova/app.py`.

### 26. 🪜 Stairs, Kerbs, Poles & Doors
- **Goal:** Cover hazards that COCO-trained YOLO cannot see.
- **Description:** Fine-tune on a navigation dataset, or add monocular depth (e.g. Depth Anything / MiDaS) to detect drop-offs and generic obstacles without needing a class label.

### 27. 🔤 Text Reading (OCR) for Signs
- **Goal:** Read room numbers, shop names and signs on request.
- **Description:** A key or voice command that runs OCR (e.g. PaddleOCR/EasyOCR) on the current frame and reads out the largest text.

### 28. 🧠 Conversational LLM Guidance
- **Goal:** Natural-language scene descriptions on demand.
- **Description:** Feed the structured detections (already produced for `describe_scene`) to a small local model for richer answers. Keep all safety alerts on the fast rule-based path (see the design strategy below).

### 29. 🗣️ High-Fidelity Neural TTS
- **Goal:** A more natural voice.
- **Description:** A pluggable backend in `nova/audio.py` (e.g. `edge-tts` or Piper for offline use) alongside `Pyttsx3Backend`.

---

## 💡 Low-Latency Design Strategy (Avoiding LLM Delays)

Because this is a real-time safety application, we must maintain sub-100ms latency for hazards. When implementing the conversational "Jarvis" features above, apply these architecture tips:

### 1. ⚡ Dual-Path (Hybrid) Processing
- **Fast Path (Instant Avoidance):** If a hazard is detected at a critical distance (e.g., `< 1.0` meter), bypass the LLM entirely and immediately play an alarm tone or direct system warning (e.g., *"Stop!"*). This runs locally at **~10-30ms** latency.
- **Slow Path (Conversational Guidance):** Feed the LLM coordinates in the background. Trigger conversational descriptions at a slower rate (e.g., every 8-10 seconds) or *only when the user asks a question* (e.g., *"What is in front of me?"*), where a 1-second delay is naturally acceptable.

### 2. 🏠 Local Small Language Models (SLMs)
- Run a tiny, highly quantized model (such as **Llama-3.2-1B** or **Phi-3.5-mini**) locally via Ollama. This keeps processing offline and reduces generation start time to under **200ms**.

### 3. 🔄 Template-Based Speech Chaining (0ms Conversational Fallback)
- Maintain a list of pre-defined conversational sentence variations (e.g., *"Watch out for the...", "Mind the...", "You have a... ahead"*). Mix and match these programmatically based on detection values. This sounds human-like and conversational, but executes instantaneously with zero compute overhead.
