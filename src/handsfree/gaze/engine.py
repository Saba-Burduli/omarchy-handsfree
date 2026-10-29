"""The gaze thread: camera -> features -> screen point -> pointer."""

from __future__ import annotations

import logging
import math
import threading
from pathlib import Path
from typing import Any, Callable

from ..config import data_dir
from ..desktop import Desktop, Monitor
from .clicks import DwellDetector, LongBlinkDetector
from .features import Observation
from .filter import PointFilter
from .mapper import GazeMapper

log = logging.getLogger(__name__)

EYES_CLOSED = 0.35  # blink score above which the gaze estimate is unreliable

Sink = Callable[[Observation], None]


def model_path(settings: dict[str, Any]) -> Path:
    configured = settings.get("model")
    return Path(configured).expanduser() if configured else data_dir() / "models" / "face_landmarker.task"


class GazeEngine:
    def __init__(
        self,
        settings: dict[str, Any],
        desktop: Desktop,
        on_error: Callable[[Exception], None],
        on_click: Callable[[], None] | None = None,
    ):
        self.settings = settings
        self.desktop = desktop
        self.on_error = on_error
        self.on_click = on_click or (lambda: None)
        self.dwell = DwellDetector(float(settings.get("dwell_ms", 0)), float(settings.get("dwell_radius_px", 50)))
        self.blink = LongBlinkDetector(float(settings.get("blink_click_ms", 0)))
        self.mapper: GazeMapper | None = None
        self.monitor: Monitor | None = None
        self.paused = False     # keep tracking but leave the pointer alone
        self.point: tuple[float, float] | None = None
        self.error = ""  # why the camera loop last stopped, if it failed
        self.filter = PointFilter(float(settings.get("min_cutoff", 0.4)), float(settings.get("beta", 0.001)))
        self._sinks: list[Sink] = []
        self._sent: tuple[float, float] | None = None
        self._move_failed = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self.error = ""
        self._thread = threading.Thread(target=self._run, name="gaze", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
        self._thread = None
        self.point = None

    def set_mapping(self, mapper: GazeMapper | None, monitor: Monitor) -> None:
        with self._lock:
            self.mapper = mapper
            self.monitor = monitor
            self.filter.reset()

    def add_sink(self, sink: Sink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def remove_sink(self, sink: Sink) -> None:
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def _run(self) -> None:
        from .camera import FaceTracker

        s = self.settings
        try:
            with FaceTracker(model_path(s), s.get("camera", 0), int(s.get("width", 640)),
                             int(s.get("height", 480)), int(s.get("fps", 30))) as tracker:
                log.info("camera on")
                while not self._stop.is_set():
                    obs = tracker.read()
                    if obs is not None:
                        self.step(obs)
        except Exception as exc:
            log.exception("gaze tracking failed")
            self.error = str(exc) or type(exc).__name__
            self._stop.set()
            self.on_error(exc)
        finally:
            log.info("camera off")

    def step(self, obs: Observation) -> None:
        """Process one observation (separate from the camera loop for tests)."""
        with self._lock:
            sinks = list(self._sinks)
            mapper, monitor = self.mapper, self.monitor
        for sink in sinks:
            sink(obs)
        if self.blink.update(obs.blink, obs.t):
            self.on_click()
            return
        if obs.blink >= EYES_CLOSED or mapper is None or monitor is None:
            return
        x, y = mapper.predict(obs.features)
        x = min(max(x, 0.0), monitor.width - 1) + monitor.x
        y = min(max(y, 0.0), monitor.height - 1) + monitor.y
        x, y = self.filter(x, y, obs.t)
        self.point = (x, y)
        if self.paused:
            self.dwell.reset()
            return
        if self._sent is None or math.dist(self._sent, (x, y)) >= 2:
            try:
                self.desktop.move_cursor(x, y)
            except Exception as exc:  # keep tracking; report the first failure only
                if not self._move_failed:
                    log.warning("cannot move the pointer: %s", exc)
                self._move_failed = True
            else:
                self._move_failed = False
            self._sent = (x, y)
        if self.dwell.update(x, y, obs.t):
            self.on_click()
