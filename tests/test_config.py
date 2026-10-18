import tempfile
import unittest
from pathlib import Path

from handsfree.config import Config, deep_merge


class ConfigTest(unittest.TestCase):
    def test_defaults_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config.load(Path(tmp))
        self.assertEqual(config.section("desktop")["url_opener"], ["omarchy-launch-browser"])

    def test_user_settings_override_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.toml").write_text("[desktop]\nnotify = false\n")
            config = Config.load(Path(tmp))
        self.assertFalse(config.section("desktop")["notify"])
        self.assertEqual(config.section("desktop")["app_launcher"], ["uwsm", "app", "--"])

    def test_user_commands_come_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "commands.toml").write_text(
                '[[command]]\nsay = "open notes"\nrun = "obsidian"\n\n[sites]\nhn = "https://news.ycombinator.com"\n'
            )
            config = Config.load(Path(tmp))
        self.assertEqual(config.commands["command"][0]["say"], "open notes")
        self.assertEqual(config.commands["sites"]["hn"], "https://news.ycombinator.com")

    def test_deep_merge(self):
        self.assertEqual(deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3}}), {"a": {"b": 1, "c": 3}})


if __name__ == "__main__":
    unittest.main()
