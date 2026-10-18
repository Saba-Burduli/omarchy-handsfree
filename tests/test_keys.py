import unittest

from handsfree.desktop.keys import parse_combo


class KeysTest(unittest.TestCase):
    def test_written_combo(self):
        self.assertEqual(parse_combo("ctrl+shift+t"), ["LEFTCTRL", "LEFTSHIFT", "T"])

    def test_spoken_combo(self):
        self.assertEqual(parse_combo("Control L."), ["LEFTCTRL", "L"])
        self.assertEqual(parse_combo("alt left"), ["LEFTALT", "LEFT"])
        self.assertEqual(parse_combo("super five"), ["LEFTMETA", "5"])

    def test_two_word_keys(self):
        self.assertEqual(parse_combo("page down"), ["PAGEDOWN"])
        self.assertEqual(parse_combo("shift page up"), ["LEFTSHIFT", "PAGEUP"])

    def test_function_keys(self):
        self.assertEqual(parse_combo("F5"), ["F5"])

    def test_unknown(self):
        with self.assertRaises(ValueError):
            parse_combo("banana")
        with self.assertRaises(ValueError):
            parse_combo("")


if __name__ == "__main__":
    unittest.main()
