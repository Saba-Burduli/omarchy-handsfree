"""Calibration: look at dots, fit the mapper, measure accuracy, save it."""

from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from ..config import state_dir
from ..desktop import Monitor
from .engine import EYES_CLOSED
from .features import Observation
from .mapper import GazeMapper


class CalibrationError(Exception):
    pass


class DotDisplay(Protocol):
    def dot(self, x: float, y: float, label: str = "") -> None: ...


class SampleSource(Protocol):
    def add_sink(self, sink: Callable[[Observation], None]) -> None: ...
    def remove_sink(self, sink: Callable[[Observation], None]) -> None: ...


def calibration_targets(width: float, height: float, points: int = 9, margin: float = 0.08) -> list[tuple[float, float]]:
    side = max(2, round(math.sqrt(points)))
    steps = [margin + (1 - 2 * margin) * i / (side - 1) for i in range(side)]
    return [(width * fx, height * fy) for fy in steps for fx in steps]


def validation_targets(width: float, height: float) -> list[tuple[float, float]]:
    return [(width * fx, height * fy) for fx, fy in ((0.3, 0.3), (0.7, 0.35), (0.35, 0.7), (0.65, 0.65))]


class SampleCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._armed = False
        self._samples: list[tuple[float, ...]] = []

    def __call__(self, obs: Observation) -> None:
        with self._lock:
            if self._armed and obs.blink < EYES_CLOSED:
                self._samples.append(obs.features)

    def arm(self) -> None:
        with self._lock:
            self._samples = []
            self._armed = True

    def disarm(self) -> list[tuple[float, ...]]:
        with self._lock:
            self._armed = False
            return self._samples


def _mean(samples: list[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(sum(s[i] for s in samples) / len(samples) for i in range(len(samples[0])))


def run_calibration(
    source: SampleSource,
    display: DotDisplay,
    monitor: Monitor,
    points: int = 9,
    settle: float = 0.9,
    collect: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[GazeMapper, float]:
    """Returns the fitted mapper (monitor-local coords) and mean error in px."""
    collector = SampleCollector()
    source.add_sink(collector)
    try:
        train = calibration_targets(monitor.width, monitor.height, points)
        check = validation_targets(monitor.width, monitor.height)
        features: list[tuple[float, ...]] = []
        targets: list[tuple[float, float]] = []
        held_out: list[tuple[tuple[float, ...], tuple[float, float]]] = []
        total = len(train) + len(check)
        for i, (x, y) in enumerate(train + check):
            display.dot(x, y, f"Look at the dot  {i + 1}/{total}")
            sleep(settle)  # eyes travel and settle before we sample
            collector.arm()
            sleep(collect)
            samples = collector.disarm()
            if len(samples) < 3:
                raise CalibrationError("Couldn't see your eyes; check the camera, lighting and glare")
            if i < len(train):
                features.extend(samples)
                targets.extend([(x, y)] * len(samples))
            else:
                held_out.append((_mean(samples), (x, y)))
        mapper = GazeMapper.fit(features, targets)
        error = sum(math.dist(mapper.predict(f), t) for f, t in held_out) / len(held_out)
        return mapper, error
    finally:
        source.remove_sink(collector)


class CalibrationStore:
    """One calibration per monitor, invalidated if the monitor size changes."""

    def __init__(self, path: Path | None = None):
        self.path = path or state_dir() / "calibration.json"

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def load(self, monitor: Monitor) -> GazeMapper | None:
        entry = self._read().get(monitor.name)
        if not entry or (entry.get("width"), entry.get("height")) != (monitor.width, monitor.height):
            return None
        return GazeMapper.from_dict(entry["mapper"])

    def save(self, monitor: Monitor, mapper: GazeMapper, error_px: float) -> None:
        data = self._read()
        data[monitor.name] = {
            "width": monitor.width,
            "height": monitor.height,
            "error_px": round(error_px, 1),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mapper": mapper.to_dict(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, self.path)
