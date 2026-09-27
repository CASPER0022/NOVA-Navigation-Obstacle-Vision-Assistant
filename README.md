# NOVA: Navigation & Obstacle Vision Assistant 👁️🤖

**NOVA** is a real-time computer vision assistant that supports spatial orientation, obstacle detection and navigation for visually impaired people. It watches the path ahead through a camera, works out what is in the way, how far away it is and whether it is approaching, and tells the user through short spoken phrases and directional tones.

The project is inspired by the research paper *"A review of assistive spatial orientation and navigation technologies for the visually impaired"* (in `References/`).

> ⚠️ **Safety notice:** NOVA is a research/educational aid. It is **not** a replacement for a white cane, guide dog or orientation & mobility training, and it must never be the sole basis for crossing a road. Monocular distance estimates are approximate, and the detector can miss objects (especially ones it was never trained on: poles, kerbs, stairs, holes).

---

## 📌 Architecture

```
 [ Camera / video / images ]      nova/capture.py      auto-select, reconnect, end-of-file
              │
              ▼
 [ YOLOv8 detection ]             nova/perception.py   pinhole geometry: clock angle, distance,
              │                                        "is it in my walking path?"
              ▼
 [ Multi-object tracker ]         nova/tracker.py      stable ids, debounce, closing speed, TTC
              │
              ├──► [ Camera health ]    nova/environment.py   dark / blocked / blurry / frozen
              ├──► [ Traffic lights ]   nova/traffic_light.py HSV colour of the nearest light
              ▼
 [ Alert policy ]                 nova/alerts.py       urgency ranking, one phrase per cycle,
              │                                        reminders, verbosity, path-clear feedback
              ▼
 [ Speech + spatial earcons ]     nova/audio.py        priority slot, interruptible, quiet mode
              ▲
 [ Keyboard commands ]            nova/controls.py     works from the terminal, no window needed
```

`assistive_system.py` is the command-line entry point; `nova/app.py` runs the loop.

---

## ⚡ Features

### Safety-first alerting
*   **Three urgency levels.** *Critical* (something in your walking path within ~1.2 m, or on a collision course) says **"Stop. Chair ahead, 1 step"** and interrupts any other speech. *Warning* covers things in your path within ~2.5 m, anything very close at your side, and approaching vehicles. *Info* covers everything else in range.
*   **Walking-corridor awareness.** Every object's sideways offset is converted into meters. Only objects that overlap a ~1 m-wide corridor in front of you count as "in your path", so a person 3 m away off to the side doesn't trigger a warning.
*   **Approach detection and time-to-contact.** Tracking each object's distance over time gives a closing speed. A cyclist closing fast is flagged before it's "close", and vehicles are announced as *"Car approaching at 2 o'clock"*.
*   **No lost or repeated alerts.** Stable track IDs mean an object isn't re-announced every time it moves slightly, and two people side by side are two hazards. Warnings the system didn't have time to say are kept and spoken next rather than dropped. A single-frame false detection has to persist before it's announced (critical ones are announced immediately). Each object is announced **once**, or **twice** if critical, then NOVA stays quiet about it. It speaks again only if the object becomes more urgent. Press `Space` any time for a full description. Objects that YOLO briefly loses or relabels (TV → laptop) are recognised as the same object and aren't repeated.
*   **"Path clear ahead" feedback** as soon as a blocking obstacle leaves your path, plus a periodic *"Path clear"* heartbeat, so silence is never mistaken for a frozen system.

### Accurate directions and distances
*   **True clock positions.** One hour is 30°, as taught in orientation & mobility training. The old version stretched a 60° camera across 9-to-3 o'clock, calling something 25° to the right "3 o'clock" (90°).
*   **Pinhole-model distances.** These come from the camera's field of view and each object's typical real size, using its height or width, whichever isn't cut off by the frame edge. When unsure, it errs towards "closer". Covers 26 object types: people, vehicles, bicycles, animals, benches, chairs, tables, plants, hydrants, bags and more.
*   **Spoken units:** meters, **steps** (with configurable step length) or feet.

### Audio designed for non-visual use
*   **Spatial earcons.** A short tone plays before each phrase. Its pitch and pattern encode urgency, and its **left/right stereo balance encodes direction**, so with headphones you know which side to react to before the words finish.
*   **Interruptible, prioritised speech.** Only the most current message waits in the queue, and a waiting critical alert can never be pushed out by a less urgent one.
*   **Configurable voice, rate and volume.** Use `--list-voices` to see what's installed.

### On-demand information (keyboard)
Keys are read straight from the terminal, so they work with a screen reader running and without seeing or focusing the preview window.

| Key | Action |
|-----|--------|
| `Space` / `D` | **Describe surroundings**: *"3 objects. Chair ahead, 2 meters. 2 people 1 o'clock, 4 meters."* |
| `A` | **Is the way ahead clear?**: *"Chair in your path, 1.5 meters. More room on your right."* |
| `R` | Repeat the last message |
| `M` | Quiet mode (only urgent warnings are spoken) |
| `P` | Pause / resume warnings (e.g. while seated), with a reminder every minute while paused |
| `V` | Cycle detail level: minimal → normal → detailed |
| `U` | Cycle units: meters → steps → feet |
| `+` / `-` | Speech faster / slower |
| `H` | Spoken help |
| `Q` / `Esc` / `Ctrl+C` | Quit (spoken confirmation) |

Changes made with `V`, `U` and `+`/`-` are **saved automatically** to `nova_config.json`, so you don't have to set them again after a restart.

### Trustworthy operation
*   **Camera health warnings:** *"It's very dark. I may miss obstacles."* NOVA also warns about a blocked lens, a blurry image or a frozen feed, and says when the view is clear again, so "no alerts" never silently means "can't see".
*   **Traffic-light colour reading.** *"Traffic light at 12 o'clock appears red"*, then *"…changed to green"*. This is an aid only; see the safety notice above.
*   **Camera reconnect**, spoken startup/shutdown, and the model is warmed up before "ready" so the first obstacle isn't delayed.
*   **Preview HUD** for sighted helpers and low-vision users. Boxes are coloured by urgency and show distance and clock position. It also draws true clock sectors, the walking corridor, and an arrow to the nearest hazard.
*   **Metrics** (alert latency, TTS reliability, FPS) are logged to `logs/`. Summarise them with `analyze_metrics.py`.

---

## 🛠️ Installation

```bash
git clone https://github.com/your-username/NOVA.git
cd NOVA
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Windows is the primary platform (earcons use `winsound`; keys use `msvcrt`). On other platforms NOVA runs without earcons, and keys are typed followed by Enter.

---

## 🚀 Usage

```bash
python assistive_system.py                          # auto-select camera
python assistive_system.py --camera 1               # or legacy: python assistive_system.py 1
python assistive_system.py --units steps --verbosity minimal --voice Zira
python assistive_system.py --input clip.mp4 --headless   # recorded video / image folder
python assistive_system.py --list-cameras
python assistive_system.py --list-voices
python assistive_system.py --help                   # every option
```

**Calibrate for your camera.** Set `--hfov` to your camera's horizontal field of view (most webcams are 55–80°; the default is 60). It drives both clock positions and distances.

### Configuration file
Copy `nova_config.example.json` to `nova_config.json` and edit it, or save your current flags with:
```bash
python assistive_system.py --units steps --rate 200 --save-config
```
Precedence: built-in defaults → `nova_config.json` → command-line flags. Useful keys:

| Setting | Default | Meaning |
|---------|---------|---------|
| `camera_hfov_deg` | 60 | Camera horizontal field of view |
| `critical_distance` / `warning_distance` | 1.2 / 2.5 m | Urgency thresholds for objects in your path |
| `max_alert_distance` | 6 m | Ignore things farther than this |
| `corridor_half_width` | 0.5 m | Half-width of your walking path |
| `critical_ttc` | 2 s | Time-to-contact that counts as critical |
| `critical_repeats` | 2 | How many times a critical object is announced before NOVA goes quiet about it (1 = once) |
| `inference_interval` | 0.25 s | Seconds between detector runs on a live camera (0 = every frame; `--input` always analyses every frame) |
| `units`, `step_length`, `verbosity`, `speech_rate`, `voice`, `volume` | | Speech preferences |
| `earcons`, `traffic_lights`, `environment_checks`, `path_clear_interval` | | Feature switches |

### Metrics
```bash
python analyze_metrics.py                       # summarise logs/
python analyze_metrics.py --compare logs_a logs_b
```

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```
The suite covers geometry (clock angles, distance, walking corridor), tracking and closing speed, the alert policy (urgency, debounce, escalation, reminders, grouping, verbosity, path-clear), scene descriptions, camera-health checks, traffic-light colours, speech priority handling, config loading and every keyboard command. None of the tests need a camera, speakers or the YOLO model.

---

## 📅 Roadmap

See [next_steps.md](next_steps.md) for completed milestones and what's next: voice commands, OCR for signs, stair/kerb detection, depth models and a neural TTS voice.

---

## 📚 References

*   *Fernandes, H., Costa, P., Filipe, V. et al. "A review of assistive spatial orientation and navigation technologies for the visually impaired." Universal Access in the Information Society (2019).*
