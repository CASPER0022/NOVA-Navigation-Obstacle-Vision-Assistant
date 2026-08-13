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
*   **Clock-Position Navigation:** Divides the frame into 6 visual sectors from 9 o'clock to 3 o'clock to provide natural directions (e.g. `"Person at 11 o'clock"`).
*   **Proximity Estimation & Prioritization:** Classifies obstacle distance and automatically sorts alerts to warn about the closest hazard first.
*   **Visual Vector HUD:** Draws a real-time vector arrow from the bottom center pointing directly to the nearest hazard, dynamically color-coded by threat level.
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
   pip install -r requirements.txt
   ```

---

## 🚀 How to Run

Execute the main assistant script:
```bash
python assistive_system.py
```
*   Press **`q`** on the video window to quit.

---

## 📅 Roadmap & Next Steps

Detailed tasks can be tracked in [next_steps.md](file:///e:/Downloads/SEM%207/Computer%20Vision/Project/next_steps.md):
*   [x] **Clock-Face Navigation**
*   [x] **Hazard Prioritization** (announce closest obstacle first)
*   [x] **GUI Navigation Arrows**
*   [ ] **Concurrency Run Loop Fix** (fixes overlapping speech engine clashing)
*   [ ] **Auditory Pulse Warning Frequency** (varying alert rate by proximity)
*   [ ] **Real-World Distance Estimation** (calibrating pixel-widths to estimate physical meters)

---

## 📚 References

*   **Review Paper:** *Fernandes, H., Costa, P., Filipe, V. et al. "A review of assistive spatial orientation and navigation technologies for the visually impaired." Universal Access in the Information Society (2019).*
