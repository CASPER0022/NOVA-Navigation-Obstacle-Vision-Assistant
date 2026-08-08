# NOVA: Navigation & Obstacle Vision Assistant 👁️🤖

**NOVA** is a real-time computer vision assistance system designed to support spatial orientation, obstacle detection, and navigation for visually impaired individuals. 

The project is inspired by the academic research paper *"A review of assistive spatial orientation and navigation technologies for the visually impaired"* (found in the `References/` directory).

---

## 📌 Project Architecture

The system coordinates three main modules to build a continuous, real-time feedback loop:
1. **Input Module:** Live camera capture (e.g., webcam or smart glasses camera).
2. **Object Detection Module:** Real-time object recognition powered by **YOLOv8** (Nano).
3. **Spatial Direction Guidance & TTS:** Translates the coordinate location of obstacles in the video frame into simple, non-blocking spoken directions (Left, Center, Right) and proximity alerts using a daemon thread.

```
       [ Live Camera Feed ]
                 │
                 ▼
     [ YOLOv8 Obstacle Detection ]
                 │
                 ▼
    [ Direction & Distance Logic ]
                 │
                 ▼
   [ Non-blocking Threaded TTS Engine ]
                 │
                 ▼
       [ "Person Ahead, Close" ]
```

---

## ⚡ Features

*   **Real-time Object Detection:** Detects pedestrians, chairs, bottles, laptops, and vehicles in real-time.
*   **Proximity Estimation:** Classifies obstacle distance based on bounding box width ratio (`very close`, `moderately close`, and `far`).
*   **Spatial Mapping:** Splits the visual field into three distinct zones (Left, Center, Right) using divider guidelines.
*   **Non-Blocking TTS Warnings:** Uses background threads to speak warnings seamlessly without freezing the camera stream.
*   **CPU Optimization:** Limits inference processing to once per second while keeping the display stream fluid.

---

## 🛠️ Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/NOVA.git
   cd NOVA
   ```

2. **Set Up a Virtual Environment (Recommended):**
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install ultralytics opencv-python pyttsx3
   ```

---

## 🚀 How to Run

Execute the main assistant script:
```bash
python assistive_system.py
```
*   Press **`q`** on the video window to quit.

---

## 📅 Roadmap / Future Improvements

*   [ ] **Clock-Face Navigation:** Implement direction reporting using the clock system (e.g., *"Obstacle at 11 o'clock"* instead of *"on your left"*).
*   [ ] **Hazard Prioritization:** Automatically sort obstacles by closeness and speak the most urgent alert first.
*   [ ] **GUI Navigation Arrows:** Draw graphical overlays (e.g. arrows and proximity alerts) to make the demo feed more interactive for presentations.

---

## 📚 References

*   **Review Paper:** *Fernandes, H., Costa, P., Filipe, V. et al. "A review of assistive spatial orientation and navigation technologies for the visually impaired." Universal Access in the Information Society (2019).*
