import csv
import os
import time


class MetricsLogger:
    """Lightweight CSV logger for alert latency, TTS reliability, and display FPS."""

    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)

        self._latency_path = os.path.join(log_dir, "alert_latency.csv")
        self._tts_path = os.path.join(log_dir, "tts_events.csv")
        self._fps_path = os.path.join(log_dir, "fps.csv")

        self._latency_file = self._open_with_header(
            self._latency_path,
            ["timestamp", "label", "detect_ts", "speak_ts", "latency_sec", "inference_duration_sec"],
        )
        self._tts_file = self._open_with_header(
            self._tts_path, ["timestamp", "event_type", "message"]
        )
        self._fps_file = self._open_with_header(self._fps_path, ["timestamp", "fps"])

        self._latency_writer = csv.writer(self._latency_file)
        self._tts_writer = csv.writer(self._tts_file)
        self._fps_writer = csv.writer(self._fps_file)

    @staticmethod
    def _open_with_header(path, header):
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        f = open(path, "a", newline="")
        if is_new:
            csv.writer(f).writerow(header)
            f.flush()
        return f

    def log_alert_latency(self, label, detect_ts, speak_ts, inference_duration):
        self._latency_writer.writerow(
            [time.time(), label, detect_ts, speak_ts, speak_ts - detect_ts, inference_duration]
        )
        self._latency_file.flush()

    def log_tts_event(self, event_type, message=""):
        self._tts_writer.writerow([time.time(), event_type, message])
        self._tts_file.flush()

    def log_fps_sample(self, fps):
        self._fps_writer.writerow([time.time(), fps])
        self._fps_file.flush()

    def close(self):
        self._latency_file.close()
        self._tts_file.close()
        self._fps_file.close()
