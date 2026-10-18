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


if __name__ == "__main__":
    unittest.main()
