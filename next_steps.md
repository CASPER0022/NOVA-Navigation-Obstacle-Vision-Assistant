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

### 7. 👁️ State Tracking & Change Detection (Stop Repetitive Alerts)
- **Goal:** Stop repeating the same warnings if the environment hasn't changed.
- **Description:** Implement an object tracking state machine. Only speak warnings when a new obstacle appears, disappears, or changes its danger level (e.g., moves from "far" to "very close"), keeping the system clean and silent otherwise.

### 8. 🧠 Conversational Jarvis LLM Integration
- **Goal:** Feed detections into a Large Language Model (local via Ollama, or online via Gemini API) to generate natural, human-like guidance.
- **Description:** Send structured obstacle coordinates to the model and instruct it to roleplay as an assistant. Instead of *"bottle 12 o'clock very close"*, it will say: *"Careful, there is a water bottle right in front of you. There is also a chair to your right if you want to rest."*

### 9. 🎙️ Interactive Voice Queries & Wake Word ("Hey Jarvis")
- **Goal:** Allow the user to ask the system questions.
- **Description:** Implement an offline speech-to-text (STT) listener. The user can say *"Hey Jarvis, is the path clear?"* or *"Where is my coffee cup?"*, and the system checks the YOLO coordinates to answer dynamically.

### 10. 🗣️ High-Fidelity Neural TTS
- **Goal:** Upgrade the robotic speech voice to a premium, natural human voice.
- **Description:** Switch from basic offline `pyttsx3` to a neural voice synthesizer (like `edge-tts` or ElevenLabs). Choose a British male voice profile (like `en-GB-RyanNeural`) for that premium, conversational Jarvis aesthetic.

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
