import json
import os
import socket
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from handsfree.desktop import Monitor
from handsfree.desktop import overlay_client
from handsfree.desktop.hypr import Hyprland, logical_monitor
from handsfree.desktop.notify import Notifier

MONITORS = [
    {"name": "eDP-1", "x": 0, "y": 0, "width": 2880, "height": 1800, "scale": 2.0, "transform": 0, "focused": False},
    {"name": "DP-1", "x": 1440, "y": 0, "width": 2560, "height": 1440, "scale": 1.0, "transform": 1, "focused": True},
]


class FakeHyprland:
    """Serves Hyprland's request socket protocol: one command per connection."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(dir="/tmp")  # AF_UNIX paths must stay short
        self.path = Path(self.dir, "hypr", "sig", ".socket.sock")
        self.path.parent.mkdir(parents=True)
        self.requests = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.path))
        self.sock.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                request = conn.recv(4096).decode()
                self.requests.append(request)
                reply = json.dumps(MONITORS) if request == "j/monitors" else "ok"
                conn.sendall(reply.encode())

    def close(self):
        self.sock.close()


class HyprlandTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeHyprland()
        self.addCleanup(self.fake.close)
        env = mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "sig", "XDG_RUNTIME_DIR": self.fake.dir})
        env.start()
        self.addCleanup(env.stop)

    def test_dispatch_and_cursor(self):
        hypr = Hyprland()
        hypr.dispatch("workspace 2")
        hypr.move_cursor(100.4, 200.6)
        self.assertEqual(self.fake.requests, ["dispatch workspace 2", "dispatch movecursor 100 201"])

    def test_focused_monitor_is_logical(self):
        # DP-1 is rotated 90 degrees, so its width and height swap.
        self.assertEqual(Hyprland().focused_monitor(), Monitor("DP-1", 1440, 0, 1440, 2560))

    def test_scale(self):
        self.assertEqual(logical_monitor(MONITORS[0]), Monitor("eDP-1", 0, 0, 1440, 900))

    def test_missing_session(self):
        with mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": ""}):
            with self.assertRaises(RuntimeError):
                Hyprland().dispatch("killactive")


def fake_evdev():
    names = {"EV_KEY": 1, "EV_REL": 2, "BTN_LEFT": 272, "BTN_RIGHT": 273, "BTN_MIDDLE": 274,
             "REL_X": 0, "REL_Y": 1, "REL_WHEEL": 8, "REL_HWHEEL": 6,
             "KEY_LEFTCTRL": 29, "KEY_L": 38, "KEY_LEFTSHIFT": 42, "KEY_T": 20}
    ecodes = types.SimpleNamespace(ecodes=names, **names)
    events = []

    class UInput:
        def __init__(self, caps, name):
            self.name = name

        def write(self, etype, code, value):
            events.append((self.name, etype, code, value))

        def syn(self):
            pass

        def close(self):
            pass

    return types.SimpleNamespace(UInput=UInput, ecodes=ecodes), events


class VirtualInputTest(unittest.TestCase):
    def setUp(self):
        module, self.events = fake_evdev()
        patcher = mock.patch.dict(sys.modules, {"evdev": module})
        patcher.start()
        self.addCleanup(patcher.stop)
        from handsfree.desktop import uinput

        with mock.patch.object(uinput.time, "sleep"):
            self.vi = uinput.VirtualInput(scroll_steps=3)
        self.sleep = mock.patch.object(uinput.time, "sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def presses(self):
        return [(code, value) for _, etype, code, value in self.events if etype == 1]

    def test_double_click(self):
        self.vi.mouse("double_click")
        self.assertEqual(self.presses(), [(272, 1), (272, 0), (272, 1), (272, 0)])

    def test_right_click_and_drag(self):
        self.vi.mouse("right_click")
        self.vi.mouse("mouse_down")
        self.vi.mouse("mouse_up")
        self.assertEqual(self.presses(), [(273, 1), (273, 0), (272, 1), (272, 0)])

    def test_scroll(self):
        self.vi.mouse("scroll_down")
        self.assertEqual([(c, v) for _, t, c, v in self.events if t == 2], [(8, -1)] * 3)

    def test_key_combo_releases_in_reverse(self):
        self.vi.key_combo(["LEFTCTRL", "LEFTSHIFT", "T"])
        self.assertEqual(self.presses(), [(29, 1), (42, 1), (20, 1), (20, 0), (42, 0), (29, 0)])
        self.assertTrue(all(name == "handsfree keyboard" for name, *_ in self.events))

    def test_unknown_mouse_action(self):
        with self.assertRaises(ValueError):
            self.vi.mouse("triple_click")


class OverlayClientTest(unittest.TestCase):
    def test_sends_json_lines_and_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp, "out.jsonl")
            script = Path(tmp, "echo.py")
            script.write_text(f"import sys\nopen({str(out)!r}, 'w').write(sys.stdin.read())\n")
            with mock.patch.object(overlay_client, "SCRIPT", script):
                overlay = overlay_client.Overlay("DP-1", python=sys.executable, layer_shell_lib="")
                overlay.dot(10, 20, "hi")
                overlay.grid([(0, 0, 5, 5)])
                overlay.clear()
                overlay.close()
            lines = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual([m["mode"] for m in lines], ["dot", "grid", "clear"])
        self.assertEqual(lines[1]["cells"], [[0, 0, 5, 5]])

    def test_dead_overlay_reports_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp, "crash.py")
            script.write_text("raise SystemExit(1)\n")
            with mock.patch.object(overlay_client, "SCRIPT", script):
                overlay = overlay_client.Overlay("DP-1", python=sys.executable, layer_shell_lib="")
                overlay._proc.wait(timeout=5)
                with self.assertRaises(RuntimeError):
                    overlay.dot(1, 1)
                overlay.close()


class NotifierTest(unittest.TestCase):
    def test_replaces_previous_notification(self):
        runs = []

        def fake_run(args, **kwargs):
            runs.append(args)
            return types.SimpleNamespace(stdout="42\n")

        with mock.patch("handsfree.desktop.notify.subprocess.run", fake_run):
            n = Notifier()
            n.show("one")
            n.show("two", "body")
        self.assertNotIn("--replace-id=42", runs[0])
        self.assertIn("--replace-id=42", runs[1])
        self.assertEqual(runs[1][-2:], ["two", "body"])

    def test_missing_notify_send_is_not_fatal(self):
        with mock.patch("handsfree.desktop.notify.subprocess.run", side_effect=FileNotFoundError):
            Notifier().show("hello")


class OmarchyDesktopTest(unittest.TestCase):
    def test_typing_goes_through_stdin(self):
        from handsfree.desktop.omarchy import OmarchyDesktop

        desktop = OmarchyDesktop({}, {})
        with mock.patch("handsfree.desktop.omarchy.subprocess.run") as run:
            desktop.type_text("-rf hello")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["wtype", "-"])
        self.assertEqual(kwargs["input"], "-rf hello")

    def test_url_and_app_launchers(self):
        from handsfree.desktop.omarchy import OmarchyDesktop
        from handsfree.intents.apps import AppEntry

        desktop = OmarchyDesktop({"url_opener": ["omarchy-launch-browser"]}, {})
        with mock.patch("handsfree.desktop.omarchy._spawn") as spawn:
            desktop.open_url("https://claude.ai")
            desktop.launch_app(AppEntry("obsidian.desktop", "Obsidian"))
        self.assertEqual(spawn.call_args_list[0].args[0], ["omarchy-launch-browser", "https://claude.ai"])
        self.assertEqual(spawn.call_args_list[1].args[0], ["uwsm", "app", "--", "obsidian.desktop"])


if __name__ == "__main__":
    unittest.main()
