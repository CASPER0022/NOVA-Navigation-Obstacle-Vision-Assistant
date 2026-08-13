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

---

## 🏃 Upcoming Tasks (Next Steps)

### 4. 🧵 Concurrency Run Loop Fix (Speech Engine)
- **Goal:** Fix the `Speech error: run loop already started` bug.
- **Description:** Implement a robust queue or mutex lock for the text-to-speech engine to prevent overlapping speech threads from clashing during active detection frames.

### 5. 🔊 Auditory Pulse Warning Frequency
- **Goal:** Vary warning frequency dynamically based on distance.
- **Description:** Speed up the warning repetition rate (cooldown) if an object is `very close` (e.g., every 1 second) vs. `far` (e.g., every 4 seconds) to create an intuitive audio radar.

### 6. 📏 Real-World Distance Estimation (Meters)
- **Goal:** Calculate actual distance in meters instead of relative width categories.
- **Description:** Calibrate standard object widths (e.g., average human, chair, bottle) and map focal length/pixel ratios to announce exact distances (e.g., `"Person at 12 o'clock, 1.5 meters away"`).
