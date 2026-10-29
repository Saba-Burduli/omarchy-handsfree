"""Microphone capture. The stream is only open while recording."""

from __future__ import annotations

import queue
import subprocess
import threading
from typing import Any, Callable

from .vad import EndpointConfig, Endpointer

PREROLL_FRAMES = 10  # keep ~300 ms before speech starts so the first word isn't clipped
PULSE_PREFIX = "pulse:"

Callback = Callable[[Any, int, Any, Any], None]


class PulseStream:
    """Capture one named PulseAudio/PipeWire source with `parec`.

    sounddevice only reaches ALSA devices, whose "default" the session may
    route anywhere; naming the source (input_device = "pulse:<name>", see
    `pactl list short sources`) pins capture to exactly that microphone.
    Mirrors sounddevice's callback interface: float32 frames of shape (n, 1).
    """

    def __init__(self, source: str, samplerate: int, blocksize: int, callback: Callback):
        self.args = [
            "parec", f"--device={source}", f"--rate={samplerate}", "--channels=1",
            "--format=float32le", "--raw", "--latency-msec=30",
        ]
        self.blocksize = blocksize
        self.callback = callback
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "PulseStream":
        self._proc = subprocess.Popen(self.args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._thread = threading.Thread(target=self._pump, name="parec", daemon=True)
        self._thread.start()
        return self

    def _pump(self) -> None:
        import numpy as np

        size = self.blocksize * 4  # float32
        while True:
            data = self._proc.stdout.read(size)
            if len(data) < size:
                return
            self.callback(np.frombuffer(data, dtype=np.float32).reshape(-1, 1), self.blocksize, None, None)

    def __exit__(self, *exc) -> None:
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._thread.join(timeout=1)


def open_input(device: Any, samplerate: int, blocksize: int, callback: Callback):
    """A float32 mono input stream on `device` (sounddevice name/index or pulse:<source>)."""
    if isinstance(device, str) and device.startswith(PULSE_PREFIX):
        return PulseStream(device[len(PULSE_PREFIX):], samplerate, blocksize, callback)
    import sounddevice as sd

    return sd.InputStream(
        samplerate=samplerate, channels=1, dtype="float32",
        blocksize=blocksize, device=device, callback=callback,
    )


class Microphone:
    def __init__(self, sample_rate: int = 16000, device: Any = None):
        self.sample_rate = sample_rate
        self.device = device or None

    def record_utterance(
        self,
        config: EndpointConfig,
        cancel: threading.Event,
        finish: threading.Event,
        on_speech: Callable[[], None] | None = None,
    ):
        """Record one utterance; returns float32 mono samples or None."""
        import numpy as np

        frames: queue.Queue = queue.Queue()
        blocksize = self.sample_rate * config.frame_ms // 1000
        endpointer = Endpointer(config)
        kept: list = []

        def callback(indata, _frames, _time, _status) -> None:
            frames.put(indata[:, 0].copy())

        with open_input(self.device, self.sample_rate, blocksize, callback):
            while not cancel.is_set():
                if finish.is_set():
                    endpointer.stop()
                    break
                try:
                    frame = frames.get(timeout=0.25)
                except queue.Empty:
                    continue
                kept.append(frame)
                was_waiting = endpointer.waiting
                if endpointer.feed(float(np.sqrt(np.mean(frame * frame)))):
                    break
                if endpointer.waiting:
                    del kept[:-PREROLL_FRAMES]
                elif was_waiting and on_speech:
                    on_speech()

        if cancel.is_set() or endpointer.reason in ("", "timeout"):
            return None
        return np.concatenate(kept)
