import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from handsfree import ctl
from handsfree.consent import Consent
from handsfree.doctor import report, run_checks
from handsfree.waybar import EYE, MIC, read_state, status


class WaybarTest(unittest.TestCase):
    def test_not_running(self):
        self.assertEqual(status(None)["text"], "")

    def test_idle_shows_nothing(self):
        out = status({"voice": "off", "gaze": False})
        self.assertEqual(out["text"], "")
        self.assertIn("microphone closed", out["tooltip"])

    def test_active_devices(self):
        out = status({"listening": True, "gaze": True, "last": "open google"})
        self.assertEqual(out["text"], f"{MIC} {EYE}")
        self.assertIn("listening", out["class"])
        self.assertIn("open google", out["tooltip"])

    def test_stale_state_from_dead_daemon(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "state.json")
            path.write_text(json.dumps({"pid": 2**22 + 12345, "gaze": True}))
            self.assertIsNone(read_state(path))
            path.write_text(json.dumps({"pid": os.getpid(), "gaze": True}))
            self.assertTrue(read_state(path)["gaze"])


class CtlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {
            "XDG_STATE_HOME": self.tmp.name, "XDG_RUNTIME_DIR": self.tmp.name, "XDG_CONFIG_HOME": self.tmp.name,
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_daemon_down(self):
        with mock.patch("sys.stderr", new=io.StringIO()) as err:
            self.assertEqual(ctl.main(["status"]), 1)
        self.assertIn("not running", err.getvalue())

    def test_setup_records_consent(self):
        with mock.patch("builtins.input", side_effect=["y", "n"]), redirect_stdout(io.StringIO()):
            self.assertEqual(ctl.main(["setup"]), 0)
        consent = Consent.load()
        self.assertTrue(consent.microphone)
        self.assertFalse(consent.camera)

    def test_setup_keeps_current_answer_on_enter(self):
        Consent(microphone=True, camera=True).save()
        with mock.patch("builtins.input", side_effect=["", ""]), redirect_stdout(io.StringIO()):
            ctl.main(["setup"])
        self.assertEqual(Consent.load(), Consent(True, True))

    def test_waybar_without_daemon(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ctl.main(["waybar"]), 0)
        self.assertEqual(json.loads(out.getvalue())["class"], "stopped")

    def test_doctor_runs_anywhere(self):
        checks = run_checks()
        self.assertTrue(any(c.name == "wtype" or c.name == "command wtype" for c in checks))
        with redirect_stdout(io.StringIO()):
            self.assertIn(report(checks), (0, 1))


if __name__ == "__main__":
    unittest.main()
