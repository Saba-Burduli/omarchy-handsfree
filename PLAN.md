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
- [x] 5. Gaze clicking: dwell click, long-blink click, numbered mouse grid that zooms
- [x] 6. Polish: wake word (openWakeWord), Waybar module, first-run consent (`handsfree-ctl setup`),
       Hyprland bindings, systemd unit, udev rule, `install.sh`, README
- [x] 7. Review pass: missing tests, bugs, cleanups; repeat until nothing useful is left
       Fixed: wake-word mode crash (name clash), state-file write race, short-phrase
       fuzzy misfires, calibration stall without a camera, grid pause after calibration,
       "not understood" spam in continuous mode, runtime network access by Whisper,
       push-to-talk blocked by wake-word wait. Added tests for the hardware layers
       with fakes and checked real Whisper / MediaPipe / openWakeWord APIs.

## Next (needs an Omarchy machine)
- [ ] Run ./install.sh, then `handsfree-ctl doctor`; fix anything it flags.
- [ ] Try the README's voice commands with push-to-talk; tune `energy_threshold`.
- [ ] Calibrate and note the reported error; check the overlay and the grid render.
- [ ] Confirm the bar widget appears and the icons change with state.
- [ ] Possible follow-up: register handsfree as an Omarchy dictation backend.
