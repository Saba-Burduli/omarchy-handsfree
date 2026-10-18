"""Map gaze features to screen coordinates with a small ridge regression.

Pure Python on purpose: a calibration is a few hundred samples and eight
terms, so numpy would buy nothing but a dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

Features = Sequence[float]


def expand(f: Features) -> list[float]:
    """Standardized (h, v, yaw, pitch) -> regression terms."""
    h, v, yaw, pitch = f
    return [1.0, h, v, yaw, pitch, h * h, v * v, h * v]


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise ValueError("singular system; calibration samples are too similar")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def ridge(rows: list[list[float]], y: list[float], lam: float) -> list[float]:
    k = len(rows[0])
    xtx = [[sum(r[i] * r[j] for r in rows) for j in range(k)] for i in range(k)]
    for i in range(1, k):  # never shrink the intercept
        xtx[i][i] += lam
    xty = [sum(r[i] * t for r, t in zip(rows, y)) for i in range(k)]
    return solve(xtx, xty)


@dataclass
class GazeMapper:
    mean: list[float]
    std: list[float]
    coef_x: list[float]
    coef_y: list[float]

    @classmethod
    def fit(cls, features: list[Features], targets: list[tuple[float, float]], lam: float = 0.05) -> "GazeMapper":
        if len(features) != len(targets) or not features:
            raise ValueError("need matching, non-empty features and targets")
        dims = len(features[0])
        mean = [sum(f[i] for f in features) / len(features) for i in range(dims)]
        std = [
            max(math.sqrt(sum((f[i] - mean[i]) ** 2 for f in features) / len(features)), 1e-6)
            for i in range(dims)
        ]
        mapper = cls(mean, std, [], [])
        rows = [expand(mapper._standardize(f)) for f in features]
        lam *= len(rows)  # scale with sample count so the default works for any calibration size
        mapper.coef_x = ridge(rows, [t[0] for t in targets], lam)
        mapper.coef_y = ridge(rows, [t[1] for t in targets], lam)
        return mapper

    def _standardize(self, f: Features) -> list[float]:
        return [(v - m) / s for v, m, s in zip(f, self.mean, self.std)]

    def predict(self, f: Features) -> tuple[float, float]:
        terms = expand(self._standardize(f))
        return (
            sum(c * t for c, t in zip(self.coef_x, terms)),
            sum(c * t for c, t in zip(self.coef_y, terms)),
        )

    def to_dict(self) -> dict:
        return {"mean": self.mean, "std": self.std, "coef_x": self.coef_x, "coef_y": self.coef_y}

    @classmethod
    def from_dict(cls, data: dict) -> "GazeMapper":
        return cls(data["mean"], data["std"], data["coef_x"], data["coef_y"])


def mean_error(mapper: GazeMapper, features: list[Features], targets: list[tuple[float, float]]) -> float:
    """Average pixel distance between predictions and targets."""
    errors = [math.dist(mapper.predict(f), t) for f, t in zip(features, targets)]
    return sum(errors) / len(errors)
