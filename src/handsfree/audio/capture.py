"""Microphone capture. The stream is only open while recording."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from .vad import EndpointConfig, Endpointer

PREROLL_FRAMES = 10  # keep ~300 ms before speech starts so the first word isn't clipped


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
        import sounddevice as sd

        frames: queue.Queue = queue.Queue()
        blocksize = self.sample_rate * config.frame_ms // 1000
        endpointer = Endpointer(config)
        kept: list = []

        def callback(indata, _frames, _time, _status) -> None:
            frames.put(indata[:, 0].copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            device=self.device,
            callback=callback,
        ):
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
