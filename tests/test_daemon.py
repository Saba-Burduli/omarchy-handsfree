import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from handsfree.config import Config
from handsfree.consent import Consent
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

    def test_concurrent_state_updates(self):
        errors = []

        def hammer(n):
            try:
                for i in range(200):
                    self.daemon._set(last=f"{n}-{i}")
            except Exception as exc:  # pragma: no cover - the bug being guarded
                errors.append(exc)

        threads = [threading.Thread(target=hammer, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_continuous_mode_does_not_nag_about_overheard_speech(self):
        self.daemon.handle_text("so anyway I told him", quiet=True)
        self.assertEqual(self.desktop.calls, [])
        self.daemon.handle_text("so anyway I told him")
        self.assertEqual(self.desktop.calls[-1][1][0], "Not understood")

    def test_calibration_fails_fast_without_camera_and_keeps_grid_paused(self):
        Consent(camera=True).save()
        self.say("grid")
        start = time.monotonic()
        self.daemon._calibrating.acquire()
        self.daemon._calibrate()  # no cv2/mediapipe here: the camera thread fails
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(self.desktop.calls[-1][1][0], "Calibration failed")
        self.assertFalse(self.daemon.state["calibrating"])
        self.assertFalse(self.daemon.state["gaze"])
        self.assertTrue(self.daemon.gaze.paused)  # grid is still open
        self.say("close grid")
        self.assertFalse(self.daemon.gaze.paused)

    def test_gaze_requires_camera_consent(self):
        response = self.daemon.handle_request({"cmd": "gaze", "arg": "on"})
        self.assertFalse(response["ok"])
        self.assertIn("camera", response["error"])

    def test_heard_text_runs_off_the_voice_thread(self):
        worker = threading.Thread(target=self.daemon._run_heard, daemon=True)
        worker.start()
        self.daemon.voice.on_text("open google", True)  # what the voice thread calls
        self.daemon._heard.put((None, None))
        worker.join(timeout=2)
        self.assertEqual(self.actions()[-1], ("open_url", ("https://www.google.com",)))

    def test_bad_toggle(self):
        self.assertFalse(self.daemon.handle_request({"cmd": "dictation", "arg": "maybe"})["ok"])


if __name__ == "__main__":
    unittest.main()
