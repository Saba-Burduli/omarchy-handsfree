import json
import tempfile
import unittest
from pathlib import Path

from handsfree.demolog import DemoLog

MONITORS = json.dumps([{"focused": True, "x": 0, "y": 0, "width": 3456, "height": 1944, "scale": 2.0}])


def window(x, w, cls="kitty"):
    return json.dumps({"at": [x, 40], "size": [w, 900], "class": cls})


class FakeHypr:
    """Replies with the next active window each time it's asked."""

    def __init__(self, windows):
        self.windows = list(windows)

    def __call__(self, command):
        if command == "j/monitors":
            return MONITORS
        return self.windows.pop(0) if len(self.windows) > 1 else self.windows[0]


class DemoLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name, "log.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def entries(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_off_by_default(self):
        self.assertIsNone(DemoLog.from_env({}))
        self.assertIsNone(DemoLog.from_env({"HANDSFREE_DEMO_LOG": "0"}))

    def test_path_and_start_time_from_env(self):
        demo = DemoLog.from_env({"HANDSFREE_DEMO_LOG": str(self.path), "HANDSFREE_DEMO_T0": "100.5"})
        self.assertEqual((demo.path, demo.t0), (self.path, 100.5))
        default = DemoLog.from_env({"HANDSFREE_DEMO_LOG": "1", "XDG_RUNTIME_DIR": self.tmp.name})
        self.assertEqual(default.path, Path(self.tmp.name, "handsfree-demo.jsonl"))

    def test_launch_waits_for_new_window_to_settle(self):
        old = window(0, 800)
        # The new window appears, is still animating, then holds still.
        hypr = FakeHypr([old, window(10, 400, "nvim"), window(20, 1600, "nvim")])
        demo = DemoLog(self.path, t0=1000.0, query=hypr)
        before = demo.snapshot()
        demo._settle_and_write("open neovim", "ran omarchy-launch-editor", True, before, 1002.0, launches=True)
        (entry,) = self.entries()
        self.assertEqual(entry["t"], 2.0)
        self.assertEqual(entry["heard"], "open neovim")
        self.assertEqual(entry["window"], {"x": 20, "y": 40, "w": 1600, "h": 900, "class": "nvim"})
        self.assertEqual(entry["monitor"]["scale"], 2.0)
        self.assertTrue(entry["ok"])

    def test_no_window_change_logs_current_window(self):
        demo = DemoLog(self.path, t0=0.0, query=FakeHypr([window(0, 800)]))
        demo._settle_and_write("scroll down", "pressed", True, demo.snapshot(), 5.0, sleep=lambda _s: None)
        (entry,) = self.entries()
        self.assertEqual(entry["window"]["w"], 800)

    def test_no_hyprland(self):
        def broken(_command):
            raise OSError("no socket")

        demo = DemoLog(self.path, t0=0.0, query=broken)
        demo._settle_and_write("hello", "not understood", False, None, 1.0, sleep=lambda _s: None)
        (entry,) = self.entries()
        self.assertIsNone(entry["window"])
        self.assertIsNone(entry["monitor"])


if __name__ == "__main__":
    unittest.main()
