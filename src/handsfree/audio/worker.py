"""The voice thread: push-to-talk and continuous listening."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from .capture import Microphone
from .stt import Transcriber
from .vad import EndpointConfig

log = logging.getLogger(__name__)


class VoiceWorker:
    def __init__(
        self,
        settings: dict[str, Any],
        on_text: Callable[[str], None],
        on_listening: Callable[[bool], None],
        on_error: Callable[[Exception], None],
    ):
        self.settings = settings
        self.on_text = on_text
        self.on_listening = on_listening
        self.on_error = on_error
        self.continuous = False
        self.recording = False
        self._wake = threading.Event()
        self._once = threading.Event()
        self._cancel = threading.Event()
        self._finish = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self.microphone = Microphone(int(settings.get("sample_rate", 16000)), settings.get("input_device"))
        self.transcriber = Transcriber(
            model=settings.get("model", "base.en"),
            device=settings.get("device", "auto"),
            compute_type=settings.get("compute_type", "int8"),
            language=settings.get("language", "en"),
            prompt=settings.get("prompt", ""),
        )

    # -- controls (called from the IPC thread) -------------------------------

    def listen_once(self) -> str:
        if self.recording and not self.continuous:
            self._finish.set()  # second press of push-to-talk: stop and transcribe
            return "processing"
        self._ensure_thread()
        self._once.set()
        self._wake.set()
        return "listening"

    def set_continuous(self, on: bool) -> None:
        self.continuous = on
        if on:
            self._ensure_thread()
            self._wake.set()
        else:
            self._cancel.set()

    def shutdown(self) -> None:
        self._stopping.set()
        self._cancel.set()
        self._wake.set()

    # -- thread --------------------------------------------------------------

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="voice", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stopping.is_set():
            self._wake.wait()
            self._wake.clear()
            while not self._stopping.is_set():
                once = self._once.is_set()
                self._once.clear()
                if not (once or self.continuous):
                    break
                self._cancel.clear()
                self._finish.clear()
                try:
                    text = self._capture(push_to_talk=once)
                except Exception as exc:
                    log.exception("voice capture failed")
                    self.continuous = False
                    self.on_error(exc)
                    break
                if text:
                    self.on_text(text)

    def _endpoint_config(self, push_to_talk: bool) -> EndpointConfig:
        s = self.settings
        return EndpointConfig(
            threshold=float(s.get("energy_threshold", 0.012)),
            silence_ms=int(s.get("silence_ms", 700)),
            max_ms=int(s.get("max_utterance_ms", 12000)),
            start_timeout_ms=int(s.get("start_timeout_ms", 5000)) if push_to_talk else None,
        )

    def _capture(self, push_to_talk: bool) -> str | None:
        if push_to_talk:
            self.on_listening(True)
        self.recording = True
        try:
            audio = self.microphone.record_utterance(
                self._endpoint_config(push_to_talk),
                self._cancel,
                self._finish,
                on_speech=None if push_to_talk else lambda: self.on_listening(True),
            )
        finally:
            self.recording = False
            self.on_listening(False)
        if audio is None:
            return None
        return self.transcriber.transcribe(audio)
