"""Optional wake word for continuous mode, via openWakeWord (offline)."""

from __future__ import annotations

import threading
from typing import Any

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
        import sounddevice as sd

        model = self._load()
        model.reset()
        with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=CHUNK, device=self.device) as stream:
            while not cancel.is_set():
                block, _overflowed = stream.read(CHUNK)
                scores = model.predict(block[:, 0])
                if max(scores.values(), default=0.0) >= self.threshold:
                    model.reset()
                    return True
        return False
