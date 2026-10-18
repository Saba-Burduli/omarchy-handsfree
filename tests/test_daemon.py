import os
import tempfile
import unittest
from pathlib import Path

from handsfree.config import Config
from handsfree.daemon import Daemon
from handsfree.desktop import DryRunDesktop


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {k: os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME")}
        for key in self.env:
            os.environ[key] = str(Path(self.tmp.name, key.lower()))
        config = Config.load()
        config.settings["desktop"]["waybar_signal"] = 0
        self.desktop = DryRunDesktop()
        self.daemon = Daemon(config, self.desktop)

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_unknown_command(self):
        self.assertFalse(self.daemon.handle_request({"cmd": "nope"})["ok"])

    def test_status(self):
        response = self.daemon.handle_request({"cmd": "status"})
        self.assertEqual(response["state"]["voice"], "off")

    def test_say_records_last_text(self):
        self.daemon.handle_request({"cmd": "say", "arg": "hello"})
        self.assertEqual(self.daemon.state["last"], "hello")

    def say(self, text):
        return self.daemon.handle_request({"cmd": "say", "arg": text})

    def actions(self):
        return [c for c in self.desktop.calls if c[0] != "notify"]

    def test_say_runs_command(self):
        self.say("Open Google.")
        self.assertEqual(self.actions()[-1], ("open_url", ("https://www.google.com",)))

    def test_unknown_phrase_notifies(self):
        self.assertIn("not understood", self.say("blah blah blah")["message"])

    def test_listen_requires_consent(self):
        response = self.daemon.handle_request({"cmd": "listen"})
        self.assertFalse(response["ok"])
        self.assertIn("setup", response["error"])

    def test_dictation_types_everything_but_escape_commands(self):
        self.say("start dictation")
        self.assertTrue(self.daemon.state["dictation"])
        self.say("Open Google, she said.")
        self.say("new line")
        self.say("Stop dictation.")
        self.say("open google")
        self.assertEqual(self.actions(), [
            ("type_text", ("Open Google, she said. ",)),
            ("key", ("enter",)),
            ("open_url", ("https://www.google.com",)),
        ])
        self.assertFalse(self.daemon.state["dictation"])

    def test_grid_zooms_then_click_closes_it(self):
        self.say("show grid")
        self.assertTrue(self.daemon.state["grid"])
        overlay = self.desktop.last_overlay
        self.assertEqual(overlay.messages[-1]["cells"][0], [0, 0, 640, 360])
        self.say("five")  # centre cell of the whole 1920x1080 screen
        self.assertEqual(self.actions()[-1], ("move_cursor", (960.0, 540.0)))
        self.assertEqual(overlay.messages[-1]["cells"][0], [640, 360, 640 / 3, 120])
        self.say("click")
        self.assertEqual(self.actions()[-1], ("mouse", ("click",)))
        self.assertTrue(overlay.closed)
        self.assertFalse(self.daemon.state["grid"])

    def test_grid_stops_zooming_when_cells_get_small(self):
        self.daemon.config.settings["gaze"]["grid_min_px"] = 100
        self.say("grid")
        self.assertIn("zoomed", self.say("one")["message"])
        self.assertIn("pointer on", self.say("one")["message"])

    def test_number_without_grid(self):
        self.assertIn("no grid", self.say("three")["message"])

    def test_grid_number_out_of_range(self):
        self.say("grid")
        self.assertIn("failed", self.say("twelve")["message"])

    def test_bad_toggle(self):
        self.assertFalse(self.daemon.handle_request({"cmd": "dictation", "arg": "maybe"})["ok"])


if __name__ == "__main__":
    unittest.main()
