"""Gaze features from MediaPipe Face Landmarker output (pure math).

Per eye we measure where the iris sits between the two eye corners
(horizontal) and how far it is above/below the corner line (vertical), both
relative to eye width so they don't change as you move closer or further
away. Head yaw and pitch add the "where is my head pointing" part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

Point = Sequence[float]

# (corner, corner, iris centre) landmark indices for each eye.
EYES = ((33, 133, 468), (362, 263, 473))


@dataclass(frozen=True)
class Observation:
    t: float                                     # monotonic seconds
    features: tuple[float, float, float, float]  # (h, v, yaw, pitch)
    blink: float                                 # 0 open .. 1 both eyes closed


def eye_ratios(lm: Sequence[Point], a: int, b: int, iris: int) -> tuple[float, float]:
    (ax, ay), (bx, by) = lm[a][:2], lm[b][:2]
    if ax > bx:  # always measure from the corner on the image's left
        ax, ay, bx, by = bx, by, ax, ay
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        raise ValueError("degenerate eye corners")
    px, py = lm[iris][0] - ax, lm[iris][1] - ay
    h = (px * dx + py * dy) / length2
    v = (py * dx - px * dy) / length2  # positive below the corner line
    return h, v


def head_pose(matrix: Sequence[Sequence[float]]) -> tuple[float, float]:
    """Yaw and pitch in degrees from the 4x4 facial transformation matrix."""
    r = matrix
    yaw = math.degrees(math.atan2(-r[2][0], math.hypot(r[2][1], r[2][2])))
    pitch = math.degrees(math.atan2(r[2][1], r[2][2]))
    return yaw, pitch


def feature_vector(lm: Sequence[Point], matrix: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    ratios = [eye_ratios(lm, *eye) for eye in EYES]
    h = sum(r[0] for r in ratios) / len(ratios)
    v = sum(r[1] for r in ratios) / len(ratios)
    yaw, pitch = head_pose(matrix)
    return (h, v, yaw, pitch)
