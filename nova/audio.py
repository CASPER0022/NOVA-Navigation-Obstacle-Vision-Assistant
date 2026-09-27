"""Speech output and spatial earcons.

Speech priorities: 0 = critical (interrupts current speech), 1 = normal, 2 = low.
Only one utterance is ever *pending*: newer messages replace older ones so the
user always hears the current situation, but a pending message is never
displaced by a less urgent one (a queued "Stop" can't be lost to "Path clear").
"""
import io
import math
import struct
import threading
import queue
import wave

try:
    import winsound
except ImportError:  # non-Windows: earcons become a no-op
    winsound = None

CRITICAL_PRIORITY, NORMAL_PRIORITY, LOW_PRIORITY = 0, 1, 2
MIN_RATE, MAX_RATE = 100, 300


class PendingSlot:
    def __init__(self):
        self._item = None
        self._in_flight = False
        self._cond = threading.Condition()

    def offer(self, priority, text):
        with self._cond:
            if self._item is not None and priority > self._item[0]:
                return False
            self._item = (priority, text)
            self._cond.notify_all()
            return True

    def take(self, timeout=None):
        with self._cond:
            if not self._cond.wait_for(lambda: self._item is not None, timeout):
                return None
            item, self._item = self._item, None
            self._in_flight = True
            self._cond.notify_all()
            return item

    def done(self):
        """Mark the item returned by take() as fully handled."""
        with self._cond:
            self._in_flight = False
            self._cond.notify_all()

    def wait_idle(self, timeout=None):
        with self._cond:
            return self._cond.wait_for(
                lambda: self._item is None and not self._in_flight, timeout)


class Pyttsx3Backend:
    """pyttsx3 with a fresh engine per utterance: re-using one engine across
    threads triggers Windows COM 'run loop already started' errors."""

    def __init__(self, rate=175, volume=1.0, voice=None):
        import pyttsx3  # lazy, so tests can run without an audio stack
        self._pyttsx3 = pyttsx3
        self.rate = rate
        self.volume = volume
        self.voice_query = voice
        self._voice_id = None
        self._voice_resolved = voice is None
        self._engine = None
        self._lock = threading.Lock()

    def _resolve_voice(self, engine):
        self._voice_resolved = True
        query = self.voice_query.lower()
        for v in engine.getProperty("voices"):
            if query in (v.name or "").lower() or query in (v.id or "").lower():
                self._voice_id = v.id
                return
        print(f"Voice {self.voice_query!r} not found; using the system default.")

    def speak(self, text):
        engine = self._pyttsx3.init()
        try:
            if not self._voice_resolved:
                self._resolve_voice(engine)
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            with self._lock:
                self._engine = engine
            engine.say(text)
            engine.runAndWait()
        finally:
            with self._lock:
                self._engine = None

    def stop(self):
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.stop()
                except Exception:
                    pass

    @staticmethod
    def list_voices():
        import pyttsx3
        engine = pyttsx3.init()
        return [(v.name, v.id) for v in engine.getProperty("voices")]


class Speech:
    def __init__(self, backend, metrics=None):
        self.backend = backend
        self.metrics = metrics
        self.quiet = False
        self.last_text = None
        self._slot = PendingSlot()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="speech")
        self._thread.start()

    def _log(self, event, text):
        if self.metrics:
            self.metrics.log_tts_event(event, text)

    def _worker(self):
        while True:
            _, text = self._slot.take()
            try:
                self._log("attempt", text)
                self.backend.speak(text)
                self._log("success", text)
            except Exception as e:
                print(f"Speech error: {e}")
                self._log("error", str(e))
            finally:
                self._slot.done()

    def say(self, text, priority=NORMAL_PRIORITY, force=False, remember=True):
        """Queue text. In quiet mode only critical or forced messages are spoken.
        Returns True if the message was accepted."""
        if self.quiet and priority != CRITICAL_PRIORITY and not force:
            return False
        accepted = self._slot.offer(priority, text)
        if accepted:
            if remember:
                self.last_text = text
            if priority == CRITICAL_PRIORITY:
                self.backend.stop()
        return accepted

    def repeat_last(self):
        if self.last_text:
            self.say(self.last_text, NORMAL_PRIORITY, force=True)
        else:
            self.say("Nothing to repeat yet.", NORMAL_PRIORITY, force=True, remember=False)

    def change_rate(self, delta):
        self.backend.rate = max(MIN_RATE, min(MAX_RATE, self.backend.rate + delta))
        return self.backend.rate

    def wait_idle(self, timeout=5.0):
        return self._slot.wait_idle(timeout)


# --------------------------------------------------------------------------
# Earcons: short stereo tones whose pitch/pattern encode urgency and whose
# left/right balance encodes direction (use headphones for the full effect).
# --------------------------------------------------------------------------
SAMPLE_RATE = 22050

EARCON_PATTERNS = {
    # kind: list of (frequency Hz, duration s, silence after s), amplitude
    "critical": ([(1250, 0.08, 0.05), (1250, 0.08, 0.0)], 0.9),
    "warning": ([(850, 0.13, 0.0)], 0.7),
    "info": ([(520, 0.10, 0.0)], 0.45),
    "path_clear": ([(500, 0.08, 0.02), (750, 0.10, 0.0)], 0.35),
}


def synth_earcon(kind, pan=0.0):
    """Render an earcon to 16-bit stereo WAV bytes. pan: -1 left .. 1 right."""
    pattern, amplitude = EARCON_PATTERNS[kind]
    theta = (max(-1.0, min(1.0, pan)) + 1) * math.pi / 4  # equal-power panning
    gain_l, gain_r = math.cos(theta) * amplitude, math.sin(theta) * amplitude
    frames = bytearray()
    for freq, dur, gap in pattern:
        n = int(SAMPLE_RATE * dur)
        fade = max(1, int(SAMPLE_RATE * 0.008))  # avoid clicks
        for i in range(n):
            env = min(1.0, i / fade, (n - i) / fade)
            v = math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * env * 32767
            frames += struct.pack("<hh", int(v * gain_l), int(v * gain_r))
        frames += b"\x00\x00\x00\x00" * int(SAMPLE_RATE * gap)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Earcons:
    def __init__(self, enabled=True):
        self.enabled = enabled and winsound is not None
        self._cache = {}
        self._queue = queue.Queue(maxsize=1)
        if self.enabled:
            threading.Thread(target=self._worker, daemon=True, name="earcons").start()

    def _sound(self, kind, pan):
        key = (kind, round(pan * 4) / 4)
        if key not in self._cache:
            self._cache[key] = synth_earcon(kind, key[1])
        return self._cache[key]

    def _worker(self):
        while True:
            data = self._queue.get()
            try:
                winsound.PlaySound(data, winsound.SND_MEMORY)
            except Exception:
                pass

    def play(self, kind, pan=0.0):
        if not self.enabled:
            return
        data = self._sound(kind, pan)
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            # Replace the stale pending tone with the newest one.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                pass
