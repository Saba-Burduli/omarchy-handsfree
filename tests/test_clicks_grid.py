import unittest

from handsfree.gaze.clicks import DwellDetector, LongBlinkDetector
from handsfree.gaze.grid import around, center, split


class DwellTest(unittest.TestCase):
    def test_fires_once_then_rearms_after_moving(self):
        d = DwellDetector(900, radius=50)
        fired = [d.update(500 + (i % 3), 300, i / 30) for i in range(60)]
        self.assertEqual(sum(fired), 1)
        self.assertEqual(fired.index(True), 27)  # 27 frames = 900 ms
        self.assertFalse(d.update(900, 300, 3.0))  # moved away: re-armed
        self.assertTrue(d.update(900, 300, 4.0))

    def test_disabled(self):
        d = DwellDetector(0)
        self.assertFalse(any(d.update(1, 1, i) for i in range(10)))


class BlinkTest(unittest.TestCase):
    def blink(self, closed_ms, min_ms=600):
        d = LongBlinkDetector(min_ms)
        d.update(0.0, 0.0)
        d.update(0.9, 1.0)
        return d.update(0.1, 1.0 + closed_ms / 1000)

    def test_natural_blink_ignored(self):
        self.assertFalse(self.blink(200))

    def test_deliberate_blink_clicks(self):
        self.assertTrue(self.blink(700))

    def test_resting_eyes_ignored(self):
        self.assertFalse(self.blink(5000))

    def test_disabled(self):
        self.assertFalse(self.blink(700, min_ms=0))


class GridTest(unittest.TestCase):
    def test_split_numbering(self):
        cells = split((0, 0, 900, 600), 3)
        self.assertEqual(len(cells), 9)
        self.assertEqual(cells[0], (0, 0, 300, 200))
        self.assertEqual(cells[2], (600, 0, 300, 200))
        self.assertEqual(cells[3], (0, 200, 300, 200))
        self.assertEqual(center(cells[4]), (450, 300))

    def test_around_stays_on_screen(self):
        self.assertEqual(around((10, 10), 400, (0, 0, 1920, 1080)), (0, 0, 400, 400))
        self.assertEqual(around((1910, 1070), 400, (0, 0, 1920, 1080)), (1520, 680, 400, 400))
        self.assertEqual(around((2000, 500), 400, (1920, 0, 1920, 1080)), (1920, 300, 400, 400))


if __name__ == "__main__":
    unittest.main()
