#!/usr/bin/env bash
# Install omarchy-handsfree for the current user on Omarchy (Arch + Hyprland).
# Safe to re-run: every step checks before it changes anything.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-handsfree"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN="$HOME/.local/bin"
VENV="$DATA/venv"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
WAKE_MODEL="hey_jarvis"
MARK_BEGIN="omarchy-handsfree >>>"

WITH_WAKE=0
ASSUME_YES=0

usage() {
  cat <<EOF
Usage: ./install.sh [--with-wake] [--yes]

  --with-wake  also install openWakeWord and its "$WAKE_MODEL" model
  --yes        answer yes to every question except camera/microphone consent
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-wake) WITH_WAKE=1 ;;
    -y | --yes) ASSUME_YES=1 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
confirm() {
  [[ $ASSUME_YES == 1 ]] && return 0
  local answer
  read -r -p "    $1 [Y/n] " answer
  [[ -z $answer || $answer =~ ^[Yy] ]]
}
fill() { sed "s|@BIN@|$BIN|g" "$1"; }
# sudo can ask for a password only with a terminal; over a plain pipe it must already be cached.
can_sudo() { [[ -t 0 ]] || sudo -n true 2>/dev/null; }

if ! command -v pacman >/dev/null; then
  echo "This installer is for Arch-based Omarchy (pacman not found)." >&2
  exit 1
fi
if [[ $EUID -eq 0 ]]; then
  echo "Run as your normal user; the installer uses sudo where it must." >&2
  exit 1
fi

step "System packages"
export PATH="$HOME/.local/bin:$PATH"
packages=(wtype libnotify portaudio python-gobject python-cairo gtk4 gtk4-layer-shell base-devel linux-api-headers curl)
command -v uv >/dev/null || packages+=(uv)  # a per-user uv works too
missing=()
for pkg in "${packages[@]}"; do
  pacman -Q "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]})); then
  note "Installing: ${missing[*]}"
  if ! can_sudo; then
    echo "Missing packages need sudo. Run this, then re-run ./install.sh:" >&2
    echo "  sudo pacman -S --needed ${missing[*]}" >&2
    exit 1
  fi
  sudo pacman -S --needed --noconfirm "${missing[@]}"
else
  note "All present."
fi

step "Python environment ($VENV)"
# MediaPipe wheels lag the newest CPython, so pin 3.12 in an isolated venv.
uv venv --allow-existing --python 3.12 "$VENV"
extras="all"
[[ $WITH_WAKE == 1 ]] && extras="all,wake"
uv pip install --python "$VENV/bin/python" --upgrade "${REPO}[${extras}]"
mkdir -p "$BIN"
ln -sf "$VENV/bin/handsfree" "$BIN/handsfree"
ln -sf "$VENV/bin/handsfree-ctl" "$BIN/handsfree-ctl"
note "Commands linked into $BIN"

step "Offline models"
model="$DATA/models/face_landmarker.task"
if [[ -f $model ]]; then
  note "Face landmarker already downloaded."
else
  curl -fL --create-dirs -o "$model.part" "$MODEL_URL"
  mv "$model.part" "$model"
fi
# Download the configured model once now; at runtime it only loads from cache.
whisper_model="$("$VENV/bin/python" -c "from handsfree.config import Config; print(Config.load().section('voice')['model'])")"
"$VENV/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('$whisper_model', device='cpu', compute_type='int8')"
note "Whisper $whisper_model ready (re-run install.sh after changing voice.model)."
if [[ $WITH_WAKE == 1 ]]; then
  "$VENV/bin/python" -c "import openwakeword.utils as u; u.download_models(model_names=['$WAKE_MODEL'])"
  note "Wake word $WAKE_MODEL ready; set voice.wake_word = \"$WAKE_MODEL\" to use it."
fi

step "Configuration (~/.config/handsfree)"
mkdir -p "$CONFIG/handsfree"
defaults="$("$VENV/bin/python" -c 'import handsfree, pathlib; print(pathlib.Path(handsfree.__file__).parent / "data")')"
for name in config.toml commands.toml; do
  if [[ ! -f $CONFIG/handsfree/$name ]]; then
    printf '# Your overrides for omarchy-handsfree. Only list what you change.\n# All defaults, with comments: %s/%s\n' "$defaults" "$name" >"$CONFIG/handsfree/$name"
    note "Created $CONFIG/handsfree/$name"
  fi
done

step "Virtual mouse and keyboard (uinput)"
rule=/etc/udev/rules.d/60-handsfree-uinput.rules
if [[ -f $rule ]] && cmp -s "$REPO/omarchy/60-handsfree-uinput.rules" "$rule"; then
  note "udev rule already installed."
elif ! can_sudo; then
  note "Skipped (needs sudo). For clicks and key presses, run in a terminal:"
  note "  sudo install -Dm644 $REPO/omarchy/60-handsfree-uinput.rules $rule && sudo udevadm control --reload && sudo udevadm trigger /dev/uinput"
elif confirm "Install a udev rule so voice and gaze can click and press keys (needs sudo)?"; then
  sudo install -Dm644 "$REPO/omarchy/60-handsfree-uinput.rules" "$rule"
  echo uinput | sudo tee /etc/modules-load.d/handsfree-uinput.conf >/dev/null
  sudo modprobe uinput
  sudo udevadm control --reload
  sudo udevadm trigger /dev/uinput || true
  note "Installed. If clicks fail, log out and back in once."
else
  note "Skipped: clicks and key presses will not work until you add it."
fi

step "Background service"
unit="$CONFIG/systemd/user/handsfree.service"
mkdir -p "$(dirname "$unit")"
fill "$REPO/omarchy/handsfree.service" >"$unit"
systemctl --user daemon-reload
systemctl --user enable handsfree.service >/dev/null
systemctl --user restart handsfree.service
note "handsfree.service enabled and (re)started."

step "Hyprland keybindings"
if [[ -f $CONFIG/hypr/bindings.lua ]]; then
  bindings="$CONFIG/hypr/bindings.lua"
  snippet="$REPO/omarchy/bindings.lua"
elif [[ -f $CONFIG/hypr/bindings.conf ]]; then
  bindings="$CONFIG/hypr/bindings.conf"
  snippet="$REPO/omarchy/bindings.conf"
else
  bindings=""
fi
if [[ -z $bindings ]]; then
  note "No ~/.config/hypr/bindings.lua or bindings.conf found; add the bindings from omarchy/ yourself."
elif grep -q "$MARK_BEGIN" "$bindings"; then
  note "Already in $bindings."
elif confirm "Add Super+Alt+V (listen), Super+Shift+Alt+V (continuous), Super+Alt+E (eyes), Super+Alt+M (grid) to $bindings?"; then
  { echo; fill "$snippet"; } >>"$bindings"
  hyprctl reload >/dev/null 2>&1 || true
  note "Added."
fi

step "Status indicator"
if command -v omarchy-shell >/dev/null; then
  plugin="$CONFIG/omarchy/plugins/handsfree.status"
  mkdir -p "$plugin"
  cp "$REPO/omarchy/bar-plugin/manifest.json" "$plugin/manifest.json"
  fill "$REPO/omarchy/bar-plugin/BarWidget.qml" >"$plugin/BarWidget.qml"
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
  if confirm "Show the hands-free microphone/camera indicator on the Omarchy bar?"; then
    omarchy plugin enable handsfree.status --section centerEnd || note "Enable it later with: omarchy plugin enable handsfree.status --section centerEnd"
  fi
else
  note "For Waybar, add this module (and the CSS in omarchy/waybar.css):"
  fill "$REPO/omarchy/waybar-module.jsonc" | sed 's/^/      /'
fi

step "Microphone and camera consent"
if [[ -t 0 ]]; then
  "$BIN/handsfree-ctl" setup
else
  note "Run handsfree-ctl setup to allow the microphone and camera."
fi

step "Checking the install"
"$BIN/handsfree-ctl" doctor || true

cat <<EOF

Done. Try it:
  * Press Super+Alt+V and say "open browser" (or "open Google", "open Claude Code").
  * Say "start eye tracking", then "calibrate" and follow the dots.
  * Run "handsfree-ctl say open google" to test without the microphone.
EOF
