"""Virtual keyboard and pointer via /dev/uinput (works on any Wayland compositor).

Needs write access to /dev/uinput; install.sh adds a udev rule that grants
it to the logged-in user only (TAG+="uaccess"), not the whole input group.
"""

from __future__ import annotations

import time

BUTTONS = {
    "click": ("BTN_LEFT", 1),
    "double_click": ("BTN_LEFT", 2),
    "right_click": ("BTN_RIGHT", 1),
    "middle_click": ("BTN_MIDDLE", 1),
}
SCROLL = {
    "scroll_up": ("REL_WHEEL", 1),
    "scroll_down": ("REL_WHEEL", -1),
    "scroll_left": ("REL_HWHEEL", -1),
    "scroll_right": ("REL_HWHEEL", 1),
}


class VirtualInput:
    def __init__(self, scroll_steps: int = 5):
        from evdev import UInput, ecodes

        self.e = ecodes
        self.scroll_steps = scroll_steps
        keys = {code for name, code in ecodes.ecodes.items()
                if name.startswith("KEY_") and isinstance(code, int) and code < 0x100}
        self.keyboard = UInput({ecodes.EV_KEY: sorted(keys)}, name="handsfree keyboard")
        self.pointer = UInput(
            {
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL],
            },
            name="handsfree pointer",
        )
        time.sleep(0.3)  # let libinput pick up the new devices before the first event

    def _button(self, code: int, value: int) -> None:
        self.pointer.write(self.e.EV_KEY, code, value)
        self.pointer.syn()

    def mouse(self, op: str) -> None:
        if op in BUTTONS:
            name, count = BUTTONS[op]
            code = self.e.ecodes[name]
            for i in range(count):
                if i:
                    time.sleep(0.06)
                self._button(code, 1)
                self._button(code, 0)
        elif op in ("mouse_down", "mouse_up"):
            self._button(self.e.BTN_LEFT, 1 if op == "mouse_down" else 0)
        elif op in SCROLL:
            name, direction = SCROLL[op]
            for _ in range(self.scroll_steps):
                self.pointer.write(self.e.EV_REL, self.e.ecodes[name], direction)
                self.pointer.syn()
                time.sleep(0.015)
        else:
            raise ValueError(f"unknown mouse action {op!r}")

    def key_combo(self, names: list[str]) -> None:
        codes = [self.e.ecodes[f"KEY_{name}"] for name in names]
        for code in codes:
            self.keyboard.write(self.e.EV_KEY, code, 1)
            self.keyboard.syn()
        for code in reversed(codes):
            self.keyboard.write(self.e.EV_KEY, code, 0)
            self.keyboard.syn()

    def close(self) -> None:
        self.keyboard.close()
        self.pointer.close()
