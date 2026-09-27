import io
import json
import threading
import wave

import pytest

from nova.audio import PendingSlot, Speech, synth_earcon
from nova.config import load_settings
from nova.controls import KeyboardControls


def test_pending_slot_keeps_more_urgent_message():
    slot = PendingSlot()
    assert slot.offer(0, "Stop. Chair ahead")
    assert not slot.offer(2, "Path clear")      # must not displace the critical alert
    assert slot.offer(0, "Stop. Person ahead")  # newer critical replaces older
    assert slot.take(timeout=0) == (0, "Stop. Person ahead")


class FakeBackend:
    def __init__(self):
        self.rate = 175
        self.spoken = []
        self.stops = 0
        self.gate = threading.Event()

    def speak(self, text):
        self.gate.wait(1)
        self.spoken.append(text)

    def stop(self):
        self.stops += 1
        self.gate.set()


def test_speech_quiet_mode_and_interrupt():
    backend = FakeBackend()
    speech = Speech(backend)
    speech.quiet = True
    assert not speech.say("Person at 1 o'clock", 2)
    assert speech.say("Stop. Chair ahead", 0)
    assert backend.stops == 1
    assert speech.wait_idle(3)
    assert backend.spoken == ["Stop. Chair ahead"]
    speech.repeat_last()
    assert speech.wait_idle(3)
    assert backend.spoken[-1] == "Stop. Chair ahead"


def test_rate_is_clamped():
    speech = Speech(FakeBackend())
    for _ in range(20):
        speech.change_rate(25)
    assert speech.backend.rate == 300


def test_earcon_is_panned_stereo_wav():
    import struct
    data = synth_earcon("warning", pan=-1.0)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getnchannels() == 2
        frames = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    left = max(abs(s) for s in samples[0::2])
    right = max(abs(s) for s in samples[1::2])
    assert left > 1000 and right < 5


def test_config_file_and_overrides(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"units": "steps", "verbosity": "minimal"}))
    s = load_settings(str(cfg), {"verbosity": "detailed", "camera": None})
    assert s.units == "steps" and s.verbosity == "detailed"


def test_config_rejects_bad_values(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"unitz": "steps"}))
    with pytest.raises(ValueError):
        load_settings(str(cfg))
    with pytest.raises(OSError):
        load_settings(str(cfg.with_name("absent.json")), {})
    with pytest.raises(ValueError):
        load_settings(None, {"units": "yards"})


def test_keys_map_to_commands():
    c = KeyboardControls()
    assert c.feed_key(" ") == "describe"
    assert c.feed_key("Q") == "quit"
    assert c.feed_key("x") is None
    assert list(c.drain()) == ["describe", "quit"]
