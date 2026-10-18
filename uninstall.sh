#!/usr/bin/env bash
# Remove omarchy-handsfree. Keeps ~/.config/handsfree unless --purge is given.
set -euo pipefail

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-handsfree"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/handsfree"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN="$HOME/.local/bin"
PURGE=0
[[ ${1:-} == --purge ]] && PURGE=1

step() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

step "Stopping the service"
systemctl --user disable --now handsfree.service 2>/dev/null || true
rm -f "$CONFIG/systemd/user/handsfree.service"
systemctl --user daemon-reload

step "Removing keybindings"
for file in "$CONFIG/hypr/bindings.lua" "$CONFIG/hypr/bindings.conf"; do
  if [[ -f $file ]] && grep -q "omarchy-handsfree >>>" "$file"; then
    sed -i '/omarchy-handsfree >>>/,/<<< omarchy-handsfree/d' "$file"
    echo "    cleaned $file"
  fi
done
hyprctl reload >/dev/null 2>&1 || true

step "Removing the bar indicator"
if [[ -d $CONFIG/omarchy/plugins/handsfree.status ]]; then
  omarchy plugin disable handsfree.status >/dev/null 2>&1 || true
  rm -rf "$CONFIG/omarchy/plugins/handsfree.status"
fi

step "Removing the uinput rule (sudo)"
sudo rm -f /etc/udev/rules.d/60-handsfree-uinput.rules /etc/modules-load.d/handsfree-uinput.conf
sudo udevadm control --reload || true

step "Removing the program and models"
rm -f "$BIN/handsfree" "$BIN/handsfree-ctl"
rm -rf "$DATA"

if [[ $PURGE == 1 ]]; then
  step "Removing settings, calibration and consent"
  rm -rf "$CONFIG/handsfree" "$STATE"
else
  echo "    Kept $CONFIG/handsfree and $STATE (use --purge to remove them)."
fi
