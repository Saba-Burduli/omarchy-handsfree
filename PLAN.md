# Plan: omarchy-handsfree

Goal: an offline, opt-in daemon for Omarchy (Arch + Hyprland) that lets you
drive the desktop with your voice ("open browser", "open Google", "open Claude
Code", "search for ...", dictation) and your eyes (webcam gaze moves the
pointer; voice, dwell or a long blink clicks; a numbered grid handles small
targets).

Each item: implement, run `PYTHONPATH=src python3 -m unittest discover -s tests -t .`,
fix failures, commit.

- [x] 1. Skeleton: daemon, control socket, `handsfree-ctl`, TOML config, `--dry-run`
- [x] 2. Voice commands: push-to-talk capture, energy endpointing, faster-whisper,
       intent parser (slots, fuzzy matching), .desktop app index, actions
- [x] 3. Dictation mode, key combos (uinput), mouse clicks/scroll (uinput), typing (wtype)
- [x] 4. Gaze pointer: MediaPipe features, ridge-regression mapper, One Euro filter,
       calibration with GTK layer-shell overlay, per-monitor calibration store
- [ ] 5. Gaze clicking: dwell click, long-blink click, numbered mouse grid that zooms
- [ ] 6. Polish: wake word (openWakeWord), Waybar module, first-run consent (`handsfree-ctl setup`),
       Hyprland bindings, systemd unit, udev rule, `install.sh`, README
- [ ] 7. Review pass: missing tests, bugs, cleanups; repeat until nothing useful is left
