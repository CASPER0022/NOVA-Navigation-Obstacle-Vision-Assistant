"""Keyboard commands, read straight from the terminal so they work without
seeing or focusing the preview window (and with a screen reader running).

Each key maps to a command name; the main loop drains `commands` each frame.
"""
import queue
import sys
import threading

KEYMAP = {
    " ": "describe", "d": "describe",
    "a": "ahead",
    "r": "repeat",
    "m": "quiet",
    "p": "pause",
    "v": "verbosity",
    "u": "units",
    "+": "faster", "=": "faster",
    "-": "slower", "_": "slower",
    "h": "help", "?": "help",
    "q": "quit", "\x1b": "quit", "\x03": "quit",
}

HELP_TEXT = (
    "Keys: Space, describe surroundings. A, is the path ahead clear. "
    "R, repeat last message. M, quiet mode. P, pause or resume. "
    "V, change detail level. U, change distance units. "
    "Plus or minus, speech speed. H, help. Q, quit."
)


class KeyboardControls:
    def __init__(self):
        self.commands = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        try:
            import msvcrt  # noqa: F401  (Windows console)
            target = self._poll_msvcrt
        except ImportError:
            if not sys.stdin or not sys.stdin.isatty():
                return self
            target = self._poll_stdin_lines
        self._thread = threading.Thread(target=target, daemon=True, name="keyboard")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def feed_key(self, key):
        """Translate a key (e.g. from cv2.waitKey) into a command."""
        command = KEYMAP.get(key.lower() if key.isalpha() else key)
        if command:
            self.commands.put(command)
        return command

    def _poll_msvcrt(self):
        import msvcrt
        while not self._stop.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):  # function/arrow key prefix: swallow the scan code
                    msvcrt.getwch()
                    continue
                self.feed_key(ch)
            else:
                self._stop.wait(0.03)

    def _poll_stdin_lines(self):
        # POSIX fallback without raw-mode tricks: type a key then Enter.
        for line in sys.stdin:
            if self._stop.is_set():
                break
            key = line[:1] if line.strip() else " "
            self.feed_key(key)

    def drain(self):
        while True:
            try:
                yield self.commands.get_nowait()
            except queue.Empty:
                return
