import math
import random
import statistics
import tempfile
import unittest
from pathlib import Path

from handsfree.desktop import DryRunDesktop, Monitor
from handsfree.gaze.calibrate import (
    CalibrationError, CalibrationStore, calibration_targets, run_calibration,
)
from handsfree.gaze.engine import GazeEngine
from handsfree.gaze.features import Observation, eye_ratios, feature_vector, head_pose
from handsfree.gaze.filter import OneEuroFilter
from handsfree.gaze.mapper import GazeMapper, mean_error

IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
MONITOR = Monitor("eDP-1", 0, 0, 1920, 1080)


def fake_features(x, y, noise=0.0, rng=random):
    """A plausible eye model: iris and head move a little with the target."""
    n = lambda s: rng.gauss(0, s * noise)
    return (
        0.35 + 0.3 * x / 1920 + 0.02 * (x / 1920) ** 2 + n(0.01),
        0.05 + 0.15 * y / 1080 + n(0.01),
        (x - 960) / 80 + n(0.5),
        (y - 540) / 90 + n(0.5),
    )


class FeaturesTest(unittest.TestCase):
    def landmarks(self, iris_offset):
        lm = [(0.0, 0.0)] * 478
        lm[33], lm[133], lm[468] = (100, 200), (140, 200), (120 + iris_offset, 200)
        lm[362], lm[263], lm[473] = (180, 200), (220, 200), (200 + iris_offset, 200)
        return lm

    def test_centered_iris(self):
        h, v, yaw, pitch = feature_vector(self.landmarks(0), IDENTITY)
        self.assertAlmostEqual(h, 0.5)
        self.assertAlmostEqual(v, 0.0)
        self.assertAlmostEqual(yaw, 0.0)
        self.assertAlmostEqual(pitch, 0.0)

    def test_both_eyes_move_the_same_way(self):
        lm = self.landmarks(8)
        left = eye_ratios(lm, 33, 133, 468)[0]
        right = eye_ratios(lm, 362, 263, 473)[0]
        self.assertAlmostEqual(left, right)
        self.assertGreater(left, 0.5)

    def test_vertical_is_positive_below(self):
        lm = self.landmarks(0)
        lm[468] = (120, 205)
        self.assertGreater(eye_ratios(lm, 33, 133, 468)[1], 0)

    def test_head_yaw(self):
        a = math.radians(20)
        rot = [[math.cos(a), 0, math.sin(a), 0], [0, 1, 0, 0], [-math.sin(a), 0, math.cos(a), 0], [0, 0, 0, 1]]
        self.assertAlmostEqual(head_pose(rot)[0], 20.0)


class MapperTest(unittest.TestCase):
    def test_recovers_mapping(self):
        rng = random.Random(1)
        targets = [t for t in calibration_targets(1920, 1080, 9) for _ in range(20)]
        feats = [fake_features(x, y, 1.0, rng) for x, y in targets]
        mapper = GazeMapper.fit(feats, targets)
        check = [(500, 400), (1400, 700)]
        error = mean_error(mapper, [fake_features(x, y) for x, y in check], check)
        self.assertLess(error, 40)

    def test_roundtrip(self):
        targets = calibration_targets(1920, 1080, 9)
        mapper = GazeMapper.fit([fake_features(*t) for t in targets], targets)
        again = GazeMapper.from_dict(mapper.to_dict())
        self.assertEqual(mapper.predict(fake_features(700, 300)), again.predict(fake_features(700, 300)))

    def test_rejects_identical_samples(self):
        with self.assertRaises(ValueError):
            GazeMapper.fit([(0.5, 0.1, 0, 0)] * 9, [(i * 10.0, 0.0) for i in range(9)], lam=0)


class FilterTest(unittest.TestCase):
    def test_constant_input_is_stable(self):
        f = OneEuroFilter(0.4, 0.004)
        out = [f(100.0, i / 30) for i in range(30)]
        self.assertAlmostEqual(out[-1], 100.0)

    def test_reduces_jitter(self):
        rng = random.Random(2)
        f = OneEuroFilter(0.4, 0.001)
        raw = [500 + rng.gauss(0, 40) for _ in range(300)]
        out = [f(x, i / 30) for i, x in enumerate(raw)][30:]
        self.assertLess(statistics.pstdev(out), statistics.pstdev(raw[30:]) * 0.4)

    def test_follows_big_jumps(self):
        f = OneEuroFilter(0.4, 0.001)
        for i in range(30):
            f(0.0, i / 30)
        out = [f(1000.0, 1 + i / 30) for i in range(6)]
        self.assertGreater(out[-1], 900)  # within 200 ms


class FakeSource:
    def __init__(self):
        self.sinks = []

    def add_sink(self, sink):
        self.sinks.append(sink)

    def remove_sink(self, sink):
        self.sinks.remove(sink)


class FakeDisplay:
    def __init__(self):
        self.dots = []

    def dot(self, x, y, label=""):
        self.dots.append((x, y))


class CalibrationTest(unittest.TestCase):
    def run_with(self, blink=0.0):
        source, display, rng = FakeSource(), FakeDisplay(), random.Random(3)
        t = [0.0]

        def sleep(seconds):
            for _ in range(int(seconds * 30)):
                t[0] += 1 / 30
                x, y = display.dots[-1]
                for sink in list(source.sinks):
                    sink(Observation(t[0], fake_features(x, y, 1.0, rng), blink))

        return source, display, run_calibration(source, display, MONITOR, sleep=sleep)

    def test_calibration(self):
        source, display, (mapper, error) = self.run_with()
        self.assertEqual(len(display.dots), 13)  # 9 targets + 4 validation
        self.assertLess(error, 60)
        self.assertEqual(source.sinks, [])

    def test_closed_eyes_fail(self):
        with self.assertRaises(CalibrationError):
            self.run_with(blink=0.9)

    def test_store_invalidated_by_resolution_change(self):
        _, _, (mapper, error) = self.run_with()
        with tempfile.TemporaryDirectory() as tmp:
            store = CalibrationStore(Path(tmp, "cal.json"))
            store.save(MONITOR, mapper, error)
            self.assertIsNotNone(store.load(MONITOR))
            self.assertIsNone(store.load(Monitor("eDP-1", 0, 0, 2560, 1440)))
            self.assertIsNone(store.load(Monitor("HDMI-A-1", 0, 0, 1920, 1080)))


class EngineTest(unittest.TestCase):
    def setUp(self):
        targets = calibration_targets(1920, 1080, 9)
        self.mapper = GazeMapper.fit([fake_features(*t) for t in targets], targets)
        self.desktop = DryRunDesktop()
        self.engine = GazeEngine({}, self.desktop, on_error=lambda e: None)

    def test_moves_pointer_with_monitor_offset(self):
        self.engine.set_mapping(self.mapper, Monitor("DP-1", 1920, 0, 1920, 1080))
        self.engine.step(Observation(0.0, fake_features(800, 300), 0.0))
        name, (x, y) = self.desktop.calls[-1]
        self.assertEqual(name, "move_cursor")
        self.assertAlmostEqual(x, 1920 + 800, delta=40)
        self.assertAlmostEqual(y, 300, delta=40)

    def test_ignores_closed_eyes_and_respects_pause(self):
        self.engine.set_mapping(self.mapper, MONITOR)
        self.engine.step(Observation(0.0, fake_features(800, 300), 0.9))
        self.engine.paused = True
        self.engine.step(Observation(0.1, fake_features(800, 300), 0.0))
        self.assertEqual(self.desktop.calls, [])
        self.assertIsNotNone(self.engine.point)

    def test_dwell_clicks(self):
        clicks = []
        engine = GazeEngine({"dwell_ms": 500}, self.desktop, on_error=lambda e: None, on_click=lambda: clicks.append(1))
        engine.set_mapping(self.mapper, MONITOR)
        for i in range(30):
            engine.step(Observation(i / 30, fake_features(800, 300), 0.0))
        self.assertEqual(clicks, [1])

    def test_long_blink_clicks(self):
        clicks = []
        engine = GazeEngine({"blink_click_ms": 600}, self.desktop, on_error=lambda e: None, on_click=lambda: clicks.append(1))
        engine.set_mapping(self.mapper, MONITOR)
        for i in range(60):
            blink = 0.9 if 10 <= i < 35 else 0.0  # ~830 ms closed
            engine.step(Observation(i / 30, fake_features(800, 300), blink))
        self.assertEqual(clicks, [1])

    def test_clamps_to_monitor(self):
        self.engine.set_mapping(self.mapper, MONITOR)
        self.engine.step(Observation(0.0, fake_features(5000, -900), 0.0))
        _, (x, y) = self.desktop.calls[-1]
        self.assertLessEqual(x, 1919)
        self.assertGreaterEqual(y, 0)


if __name__ == "__main__":
    unittest.main()
