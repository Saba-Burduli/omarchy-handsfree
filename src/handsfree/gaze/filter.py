"""Smoothing for the gaze point.

The One Euro filter (Casiez et al., CHI 2012) smooths heavily while the
point is still, which kills jitter, and lightly while it moves fast, which
keeps saccades responsive.
"""

from __future__ import annotations

import math


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._x: float | None = None
        self._dx = 0.0
        self._t: float | None = None

    def __call__(self, x: float, t: float) -> float:
        if self._x is None or self._t is None:
            self._x, self._t = x, t
            return x
        dt = t - self._t
        if dt <= 0:
            return self._x
        a_d = _alpha(self.d_cutoff, dt)
        self._dx = a_d * (x - self._x) / dt + (1 - a_d) * self._dx
        a = _alpha(self.min_cutoff + self.beta * abs(self._dx), dt)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x


class PointFilter:
    def __init__(self, min_cutoff: float = 0.4, beta: float = 0.001):
        self.x = OneEuroFilter(min_cutoff, beta)
        self.y = OneEuroFilter(min_cutoff, beta)

    def reset(self) -> None:
        self.x.reset()
        self.y.reset()

    def __call__(self, x: float, y: float, t: float) -> tuple[float, float]:
        return self.x(x, t), self.y(y, t)
