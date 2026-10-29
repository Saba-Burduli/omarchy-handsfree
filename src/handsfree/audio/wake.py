"""Optional wake word for continuous mode, via openWakeWord (offline)."""

from __future__ import annotations

import queue
import threading
from typing import Any

from .capture import open_input

CHUNK = 1280  # 80 ms at 16 kHz, the frame size openWakeWord expects


class WakeWord:
    def __init__(self, model: str, threshold: float = 0.5, device: Any = None):
        self.model_name = model
        self.threshold = threshold
        self.device = device or None
        self._model = None

    def _load(self):
        if self._model is None:
            from openwakeword.model import Model

            self._model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        return self._model

    def wait(self, cancel: threading.Event) -> bool:
        """Block until the wake word is heard (True) or cancel is set (False)."""
        import numpy as np

        model = self._load()
        model.reset()
        blocks: queue.Queue = queue.Queue()

        def callback(indata, _frames, _time, _status) -> None:
            blocks.put(indata[:, 0].copy())

        with open_input(self.device, 16000, CHUNK, callback):
            while not cancel.is_set():
                try:
                    block = blocks.get(timeout=0.25)
                except queue.Empty:
                    continue
                scores = model.predict((np.clip(block, -1, 1) * 32767).astype(np.int16))
                if max(scores.values(), default=0.0) >= self.threshold:
                    model.reset()
                    return True
        return False
