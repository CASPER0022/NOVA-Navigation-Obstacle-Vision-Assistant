import json

import nova.app as app_module
from nova.config import Settings
from nova.controls import KEYMAP

from helpers import make_det


class FakeBackend:
    def __init__(self, rate=175, volume=1.0, voice=None):
        self.rate = rate
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)

    def stop(self):
        pass


def make_app(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "Pyttsx3Backend", FakeBackend)
    settings = Settings(log_dir=str(tmp_path / "logs"), earcons=False).validate()
    return app_module.NovaApp(settings, config_path=str(tmp_path / "prefs.json"))


def spoken_after(app, command):
    app.handle(command)
    app.speech.wait_idle(3)
    return app.speech.backend.spoken[-1]


def test_every_key_command_is_handled(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    for command in set(KEYMAP.values()) - {"quit"}:
        app.handle(command)
    app.handle("quit")
    assert app.running is False
    app.speech.wait_idle(3)
    app.metrics.close()


def test_describe_quiet_pause_and_preferences(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    app.recent_objects = [make_det("chair", 2.0)]
    assert spoken_after(app, "describe") == "1 object. Chair ahead, 2 meters."
    assert spoken_after(app, "ahead") == "Chair in your path, 2 meters."
    assert spoken_after(app, "quiet").startswith("Quiet mode on")
    assert app.speech.quiet
    assert spoken_after(app, "pause").startswith("Paused")
    assert spoken_after(app, "describe").startswith("Paused. Last seen:")
    assert spoken_after(app, "units") == "Distances in steps."
    assert spoken_after(app, "verbosity") == "Detail level detailed."
    app.handle("faster")
    assert app.s.speech_rate == 200

    app.shutdown(None)
    prefs = json.loads((tmp_path / "prefs.json").read_text())
    assert prefs == {"verbosity": "detailed", "units": "steps", "speech_rate": 200}
