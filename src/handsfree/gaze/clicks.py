"""Hands-free click triggers: dwelling on a spot, or a deliberate long blink."""

from __future__ import annotations

import math


class DwellDetector:
    """Fires once when the point stays within `radius` px for `dwell_ms`.

    It re-arms only after the point moves away, so staring at one spot clicks
    once, not repeatedly.
    """

    def __init__(self, dwell_ms: float, radius: float = 50):
        self.dwell_ms = dwell_ms
        self.radius = radius
        self.reset()

    def reset(self) -> None:
        self._anchor: tuple[float, float] | None = None
        self._since = 0.0
        self._fired = False

    def update(self, x: float, y: float, t: float) -> bool:
        if self.dwell_ms <= 0:
            return False
        if self._anchor is None or math.dist(self._anchor, (x, y)) > self.radius:
            self._anchor, self._since, self._fired = (x, y), t, False
            return False
        if not self._fired and (t - self._since) * 1000 >= self.dwell_ms:
            self._fired = True
            return True
        return False


class LongBlinkDetector:
    """Fires when both eyes reopen after being closed for min_ms..max_ms.

    Natural blinks last ~100-300 ms, so a minimum around 600 ms separates a
    deliberate blink from an involuntary one; very long closures (resting
    your eyes) are ignored.
    """

    def __init__(self, min_ms: float, max_ms: float = 2000, threshold: float = 0.5):
        self.min_ms = min_ms
        self.max_ms = max_ms
        self.threshold = threshold
        self._closed_since: float | None = None

    def update(self, blink: float, t: float) -> bool:
        if self.min_ms <= 0:
            return False
        if blink >= self.threshold:
            if self._closed_since is None:
                self._closed_since = t
            return False
        if self._closed_since is None:
            return False
        duration = (t - self._closed_since) * 1000
        self._closed_since = None
        return self.min_ms <= duration <= self.max_ms
