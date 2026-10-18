"""Energy-based end-of-utterance detection.

Whisper's own VAD trims silence inside the clip; this only decides when to
stop recording. It adapts to background noise while waiting for speech.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EndpointConfig:
    frame_ms: int = 30
    threshold: float = 0.012          # minimum RMS that counts as speech
    noise_multiplier: float = 3.0     # speech must also be this much above the noise floor
    min_speech_ms: int = 120          # ignore clicks and pops
    silence_ms: int = 700             # this much quiet after speech ends the utterance
    max_ms: int = 12000               # hard cap on utterance length
    start_timeout_ms: int | None = 5000  # give up if nobody speaks; None waits forever


class Endpointer:
    WAITING, SPEAKING, DONE = "waiting", "speaking", "done"

    def __init__(self, config: EndpointConfig):
        self.config = config
        self.state = self.WAITING
        self.reason = ""  # end | max | timeout | stopped
        self.noise: float | None = None
        self._speech_ms = 0
        self._waited_ms = 0
        self._spoken_ms = 0
        self._silence_ms = 0

    @property
    def waiting(self) -> bool:
        return self.state == self.WAITING

    def threshold(self) -> float:
        floor = (self.noise or 0.0) * self.config.noise_multiplier
        return max(self.config.threshold, floor)

    def feed(self, rms: float) -> bool:
        """Feed one frame's RMS level; returns True once the utterance is over."""
        cfg = self.config
        loud = rms > self.threshold()
        if self.state == self.WAITING:
            self._waited_ms += cfg.frame_ms
            if loud:
                self._speech_ms += cfg.frame_ms
                if self._speech_ms >= cfg.min_speech_ms:
                    self.state = self.SPEAKING
                    self._spoken_ms = self._speech_ms
            else:
                self._speech_ms = 0
                self.noise = rms if self.noise is None else 0.95 * self.noise + 0.05 * rms
                if cfg.start_timeout_ms is not None and self._waited_ms >= cfg.start_timeout_ms:
                    return self._finish("timeout")
            return False
        if self.state == self.SPEAKING:
            self._spoken_ms += cfg.frame_ms
            self._silence_ms = 0 if loud else self._silence_ms + cfg.frame_ms
            if self._silence_ms >= cfg.silence_ms:
                return self._finish("end")
            if self._spoken_ms >= cfg.max_ms:
                return self._finish("max")
            return False
        return True

    def stop(self) -> None:
        """Push-to-talk released early."""
        self._finish("stopped" if self.state == self.SPEAKING else "timeout")

    def _finish(self, reason: str) -> bool:
        self.state = self.DONE
        self.reason = reason
        return True
