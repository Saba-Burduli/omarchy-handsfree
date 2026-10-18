"""Offline speech-to-text with faster-whisper."""

from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model: str = "base.en", device: str = "auto", compute_type: str = "int8",
                 language: str = "en", prompt: str = ""):
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language or None
        # Priming Whisper with the command vocabulary makes "Claude" beat "cloud".
        self.prompt = prompt or None
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                device = self.device
                if device == "auto":
                    import ctranslate2

                    device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
                compute = "float16" if device == "cuda" and self.compute_type == "int8" else self.compute_type
                log.info("loading whisper %s on %s (%s)", self.model_name, device, compute)
                self._model = WhisperModel(self.model_name, device=device, compute_type=compute)
        return self._model

    def preload(self) -> None:
        threading.Thread(target=self._load, name="whisper-load", daemon=True).start()

    def transcribe(self, audio) -> str:
        segments, _info = self._load().transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            initial_prompt=self.prompt,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
