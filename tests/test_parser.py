import tempfile
import unittest
from pathlib import Path

from handsfree.config import load_commands
from handsfree.intents.apps import AppEntry, AppIndex
from handsfree.intents.parser import Parser

APPS = AppIndex([
    AppEntry("firefox.desktop", "Firefox", ("web", "browser")),
    AppEntry("google-chrome.desktop", "Google Chrome"),
    AppEntry("org.gnome.Nautilus.desktop", "Files"),
])


class ParserTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.parser = Parser(load_commands(Path(tmp)), apps=APPS)

    def action(self, text):
        intent = self.parser.parse(text)
        self.assertIsNotNone(intent, text)
        for key in ("run", "url", "app", "hypr", "type", "key", "mouse", "internal"):
            if key in intent.command:
                return key, intent.command[key], intent.slots
        self.fail(f"no action for {text}")

    def test_open_browser(self):
        self.assertEqual(self.action("Open browser.")[:2], ("run", "omarchy-launch-browser"))

    def test_open_site(self):
        kind, template, slots = self.action("Open Google.")
        self.assertEqual((kind, slots["site"]), ("url", "https://www.google.com"))

    def test_literal_phrase_beats_site_slot(self):
        self.assertEqual(self.action("Open Claude Code.")[1], "uwsm app -- xdg-terminal-exec claude")
        self.assertEqual(self.action("open cloud code")[1], "uwsm app -- xdg-terminal-exec claude")
        self.assertEqual(self.action("open claude")[2]["site"], "https://claude.ai")

    def test_multi_word_site(self):
        self.assertEqual(self.action("go to arch wiki")[2]["site"], "https://wiki.archlinux.org")

    def test_search_keeps_spoken_text(self):
        kind, template, slots = self.action("Search for Arch Wiki Hyprland.")
        self.assertEqual(slots["text"], "Arch Wiki Hyprland")
        self.assertIn("google.com/search", template)

    def test_more_specific_search_wins(self):
        self.assertIn("youtube.com", self.action("search youtube for lofi beats")[1])

    def test_open_app(self):
        kind, _, slots = self.action("open firefox")
        self.assertEqual((kind, slots["app"].desktop_id), ("app", "firefox.desktop"))
        self.assertEqual(self.action("launch google chrome")[2]["app"].name, "Google Chrome")

    def test_number_words(self):
        self.assertEqual(self.action("Workspace two.")[2]["n"], "2")
        self.assertEqual(self.action("go to workspace 3")[2]["n"], "3")

    def test_fillers_ignored(self):
        self.assertEqual(self.action("Okay, please open browser please")[1], "omarchy-launch-browser")

    def test_fuzzy_phrase(self):
        intent = self.parser.parse("open browsers")
        self.assertEqual(intent.command["run"], "omarchy-launch-browser")
        self.assertFalse(intent.exact)

    def test_nonsense(self):
        self.assertIsNone(self.parser.parse("the quick brown fox"))
        self.assertIsNone(self.parser.parse("..."))


if __name__ == "__main__":
    unittest.main()
