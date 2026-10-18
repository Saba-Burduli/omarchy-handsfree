import unittest

from handsfree.desktop import DryRunDesktop
from handsfree.intents.actions import Executor
from handsfree.intents.apps import AppEntry
from handsfree.intents.parser import Intent


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        self.desktop = DryRunDesktop()
        self.internal = []
        self.executor = Executor(self.desktop, lambda name, slots: self.internal.append(name) or name)

    def last(self):
        return self.desktop.calls[-1]

    def test_run_quotes_slots(self):
        self.executor.execute(Intent({"run": "echo {text}"}, {"text": "hi; rm -rf ~"}))
        self.assertEqual(self.last(), ("run_shell", ("echo 'hi; rm -rf ~'",)))

    def test_url_encodes_text_but_not_site(self):
        self.executor.execute(Intent({"url": "https://g.co/search?q={text}"}, {"text": "arch & wiki"}))
        self.assertEqual(self.last(), ("open_url", ("https://g.co/search?q=arch+%26+wiki",)))
        self.executor.execute(Intent({"url": "{site}"}, {"site": "https://claude.ai"}))
        self.assertEqual(self.last(), ("open_url", ("https://claude.ai",)))

    def test_url_unhyphenates_whisper_names(self):
        self.executor.execute(Intent({"url": "https://g.co/?q={text}"}, {"text": "Arch-Wicki-Hipperland - tips"}))
        self.assertEqual(self.last(), ("open_url", ("https://g.co/?q=Arch+Wicki+Hipperland+-+tips",)))

    def test_app(self):
        self.executor.execute(Intent({"app": "{app}"}, {"app": AppEntry("firefox.desktop", "Firefox")}))
        self.assertEqual(self.last(), ("launch_app", ("firefox.desktop",)))

    def test_hypr(self):
        self.executor.execute(Intent({"hypr": "workspace {n}"}, {"n": "2"}))
        self.assertEqual(self.last(), ("hypr", ("workspace 2",)))

    def test_internal(self):
        self.assertEqual(self.executor.execute(Intent({"internal": "voice_off"})), "voice_off")
        self.assertEqual(self.internal, ["voice_off"])

    def test_missing_slot(self):
        with self.assertRaises(KeyError):
            self.executor.execute(Intent({"run": "echo {text}"}))


if __name__ == "__main__":
    unittest.main()
