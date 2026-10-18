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

## What current Omarchy looks like (checked in basecamp/omarchy, branch `quattro`)
- **Hyprland config is Lua now.** User bindings live in
  `~/.config/hypr/bindings.lua` as `o.bind("SUPER + ALT + V", "desc", "cmd")`.
  install.sh appends a marked block there, falling back to `bindings.conf`
  (hyprlang `bindd`) on older installs; uninstall.sh removes the block.
- **Hotkeys picked to avoid clashes:** Super+Alt+G is taken by Omarchy, so
  the grid is Super+Alt+M. Super+Alt+V / Super+Shift+Alt+V / Super+Alt+E were
  all free.
- **Waybar is gone**; the bar is the Quickshell-based Omarchy shell with
  manifest plugins in `~/.config/omarchy/plugins/<id>/`. A `handsfree.status`
  bar-widget plugin is installed and enabled with `omarchy plugin enable`.
  It uses only the documented widget contract (`bar`, `bar.run`, tooltips,
  `Text.PlainText`) plus Quickshell's `FileView`, and polls the state file
  because atomic replaces can drop file watches. The Waybar module and
  RTMIN signal remain for older Omarchy installs.
- **Launchers:** `omarchy-launch-browser [url]` and
  `omarchy-launch-terminal [command...]` exist, so "open Claude Code" runs
  `omarchy-launch-terminal claude` and URLs open via `omarchy-launch-browser`.
- **Omarchy ships its own dictation** (Super+Ctrl+X, F9 hold) with pluggable
  backends. handsfree's dictation is a separate mode for hands-free use and
  does not touch those bindings. Registering handsfree as an Omarchy
  dictation backend is a possible follow-up.

## Verified on macOS (no Omarchy hardware here)
- 81 unit tests (`python3 -m unittest`), shellcheck on both scripts.
- Built the wheel with `uv build`, installed it into a Python 3.12 venv and
  ran a `--dry-run` daemon session over the real socket: "Open Claude Code.",
  "search for ...", "show grid", "seven", consent refusal, Waybar JSON.
- Real libraries in a Python 3.12 venv (faster-whisper 1.2.1, MediaPipe
  1.1.1, OpenCV 5.0):
  - Whisper `base.en` on CPU, fed 14 commands synthesized with macOS `say`:
    14/14 transcribed and mapped to the right action, ~0.2 s each after a
    one-time model load. Reproduce with `dev/check_stt.py`.
  - `FaceTracker` against MediaPipe's own sample portrait and model:
    stable features across frames, low blink score, `None` on a blank frame.
- Hardware layers tested with fakes: Hyprland socket protocol (real Unix
  socket), uinput event sequences (fake evdev), overlay process protocol,
  notify-send arguments, wtype stdin.
- Not verified: a live microphone, a live webcam, real uinput/wtype on
  Wayland, the GTK layer-shell overlay, and the QML bar widget. These need an
  Omarchy machine; `handsfree-ctl doctor` checks the environment first.

## Known limitations
- Gaze maps to the monitor that was focused when tracking started.
- Webcam gaze is roughly 100-200 px accurate; the grid exists for small targets.
- Omarchy script names (`omarchy-launch-browser`, `xdg-terminal-exec`) can
  change between releases; they live in `commands.toml`, not in code.
- Nothing here has been run on real Omarchy hardware yet (this was built on
  macOS); see README "Verifying on Omarchy".
