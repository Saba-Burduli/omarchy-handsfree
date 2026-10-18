# Decisions and notes

Decisions made while building without the owner available. Each one is the
standard or recommended option, with the reason.

## Process
- **Separate git repo.** The home folder is itself a git repo, so the project
  got its own `git init` to keep its history out of it.
- **Remote.** A private GitHub repo (`Saba-Burduli/omarchy-handsfree`) was
  created and milestones 1-3 were pushed to it *before* the owner's later
  instruction "don't push to remote". From milestone 4 on, commits are local
  only. The private repo was left as is (deleting it is the owner's call).
- **Tests use stdlib `unittest`, not pytest.** The workspace rule is not to
  install dependencies without approval, and this Mac has no pytest/numpy.
  All pure logic (parser, mapper, filter, VAD, calibration, grid) is
  dependency-free so it is tested here; hardware code is tested on Omarchy.

## Design
- **TOML instead of YAML for config.** `tomllib` is in the standard library
  (Python 3.11+), so the daemon core has zero required dependencies.
- **Python 3.12 venv via uv.** MediaPipe wheels lag the newest CPython that
  Arch ships, so install.sh pins 3.12.
- **Hyprland IPC over its socket**, not `hyprctl` subprocesses, so gaze can
  move the pointer at camera frame rate cheaply.
- **Typing via `wtype`**, keys/clicks via a **uinput** virtual device
  (`python-evdev`). `xdotool` does not work on Wayland; `ydotool` needs an
  extra root daemon.
- **uinput permission via udev `TAG+="uaccess"`** (logged-in seat user only)
  instead of adding the user to the `input` group, which would let any user
  process read every keyboard (keylogging risk).
- **Push-to-talk by default**; the mic is only open while recording.
  Continuous listening and the wake word are opt-in.
- **Energy-based endpointing** decides when to stop recording; Whisper's
  built-in Silero VAD trims silence inside the clip. Avoids a torch dependency.
- **Whisper `initial_prompt`** primed with command words so "Claude" isn't
  heard as "cloud" (an alias "open cloud code" is also included).
- **Gaze model:** iris position relative to the eye corners (scale invariant)
  + head yaw/pitch, 8-term quadratic ridge regression, 9-point calibration
  plus 4 held-out validation points that report the real error in px.
- **One Euro filter** (min_cutoff 0.4 Hz, beta 0.001) - measured on synthetic
  40 px jitter: ~2.8x less jitter, reaches a 1000 px jump within 200 ms.
- **Overlay as a separate process** under the system Python (PyGObject +
  gtk4-layer-shell from pacman, which needs LD_PRELOAD). Keeps GTK out of the
  daemon and the uv venv.
- **Explicit consent file.** Linux has no per-app camera/mic prompt, so
  `handsfree-ctl setup` records consent and the daemon refuses devices
  without it.

## Known limitations
- Gaze maps to the monitor that was focused when tracking started.
- Webcam gaze is roughly 100-200 px accurate; the grid exists for small targets.
- Omarchy script names (`omarchy-launch-browser`, `xdg-terminal-exec`) can
  change between releases; they live in `commands.toml`, not in code.
- Nothing here has been run on real Omarchy hardware yet (this was built on
  macOS); see README "Verifying on Omarchy".
