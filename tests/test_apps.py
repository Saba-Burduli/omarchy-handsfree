import tempfile
import unittest
from pathlib import Path

from handsfree.intents.apps import AppIndex


def write(base, rel, body):
    path = Path(base, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


class AppIndexTest(unittest.TestCase):
    def test_scan(self):
        with tempfile.TemporaryDirectory() as user, tempfile.TemporaryDirectory() as system:
            write(system, "firefox.desktop", "[Desktop Entry]\nType=Application\nName=Firefox\nName[de]=Feuerfuchs\nExec=firefox %u\n[Desktop Action new]\nName=New Window\n")
            write(system, "hidden.desktop", "[Desktop Entry]\nType=Application\nName=Hidden\nNoDisplay=true\n")
            write(system, "kde/dolphin.desktop", "[Desktop Entry]\nType=Application\nName=Dolphin\nKeywords=files;manager;\n")
            write(user, "firefox.desktop", "[Desktop Entry]\nType=Application\nName=Firefox (mine)\n")
            write(user, "HEY.desktop", "[Desktop Entry]\nType=Application\nName=HEY\n")
            index = AppIndex.scan([Path(user), Path(system)])
        names = sorted(e.name for e in index.entries)
        self.assertEqual(names, ["Dolphin", "Firefox (mine)", "HEY"])
        self.assertEqual(index.find("hey")[0].desktop_id, "HEY.desktop")
        self.assertEqual(index.find("firefox")[1], 100.0)  # matches the file stem
        self.assertEqual(index.find("dolphin")[0].desktop_id, "kde-dolphin.desktop")
        self.assertEqual(index.find("files")[0].name, "Dolphin")
        self.assertIsNone(index.find("photoshop"))


if __name__ == "__main__":
    unittest.main()
