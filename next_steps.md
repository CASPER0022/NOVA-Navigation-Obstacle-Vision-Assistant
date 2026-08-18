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

### 6. 📏 Real-World Distance Estimation (Meters)
- **Goal:** Calculate actual distance in meters instead of relative width categories.
- **Status:** **Completed** 🟢
- **Details:** Calibrated average physical widths of objects (e.g. 8cm for a bottle, 45cm for a person) to calculate an estimated distance using `real_width / width_ratio`. This correctly prioritizes physically smaller close objects (like a bottle) over physically larger, further objects (like a person).

### 5. 🔊 Auditory Pulse Warning Frequency
- **Goal:** Vary warning frequency dynamically based on distance.
- **Status:** **Completed** 🟢
- **Details:** Replaced the static 3-second alert cooldown with a dynamic alert frequency. The rate scales dynamically based on the closest hazard's proximity (1.0s for `very close`, 2.5s for `moderately close`, and 4.0s for `far` objects), mimicking an auditory radar.

---

## 🏃 Upcoming Tasks (Next Steps)

*All core goals on the initial project roadmap have been successfully implemented!* 🎉
