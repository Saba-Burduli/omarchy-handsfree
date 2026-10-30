#!/bin/bash
# Record a demo take on Omarchy. Runs on the Omarchy machine itself.
#
# The screen is recorded at native resolution while each voice clip plays into
# a virtual PipeWire mic that handsfree listens to. Everything that happens on
# screen is handsfree reacting to that audio: this script only plays clips and
# waits for the plugin's command log (HANDSFREE_DEMO_LOG) to report each result.
#
#   ./record.sh           every clip in commands.txt
#   ./record.sh 01 05     only these clips, for quick tests
#
# Output: takes/<timestamp>/
#   screen-0.mp4   video + the voice clips as its audio track (more parts only
#                  if the recorder had to be restarted; see parts.jsonl)
#   log.jsonl      handsfree's command log, t = seconds since recording start
#   clips.jsonl    when each clip played and what handsfree heard
#   meta.json      monitor, fps, start time
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-1}
export HYPRLAND_INSTANCE_SIGNATURE=${HYPRLAND_INSTANCE_SIGNATURE:-$(ls -t "$XDG_RUNTIME_DIR/hypr" | head -1)}

FPS=${FPS:-60}
QUALITY=${QUALITY:-high}  # gpu-screen-recorder -q: medium | high | very_high | ultra
SETTLE=${SETTLE:-1.0}     # keep rolling this long after each logged result
TIMEOUT=${TIMEOUT:-12}    # stop waiting for a clip's log line after this many seconds
profile=${FF_PROFILE:-$here/ffprofile}
conf=${XDG_CONFIG_HOME:-$HOME/.config}/handsfree/config.toml

now() { date +%s.%N; }
since() { awk -v a="$(now)" -v b="$t0" 'BEGIN { printf "%.3f", a - b }'; }
dispatch() {  # Hyprland 0.56+ takes Lua; older takes classic dispatchers
  hyprctl dispatch "$1" 2>/dev/null | grep -qx ok || hyprctl dispatch "$2" >/dev/null
}

# -- which clips -------------------------------------------------------------
steps=()
while IFS='|' read -r n words hold; do
  [[ -z "$n" || "$n" == \#* ]] && continue
  if [ $# -gt 0 ] && [[ " $* " != *" $n "* ]]; then continue; fi
  clip=voice/$n.wav
  [ -f "$clip" ] || clip=voice/placeholder/$n.wav
  [ -f "$clip" ] || { echo "no clip for $n ($words): record voice/$n.wav" >&2; exit 1; }
  steps+=("$n|$words|${hold:-0}|$clip")
done < commands.txt
[ ${#steps[@]} -gt 0 ] || { echo "no clips selected" >&2; exit 1; }

if grep -qE '^\[(voice|desktop)\]' "$conf" 2>/dev/null; then
  echo "$conf already has a [voice] or [desktop] table; record.sh appends its own." >&2
  echo "Move those settings aside for the take." >&2
  exit 1
fi

take=takes/$(date +%Y%m%d-%H%M%S)
mkdir -p "$take"
log=$here/$take/log.jsonl
: > "$log"; : > "$take/clips.jsonl"; : > "$take/parts.jsonl"

# -- setup (none of this is in the footage) ------------------------------------
orig_theme=$(omarchy-theme-current 2>/dev/null || true)
sink=$(pactl load-module module-null-sink sink_name=hf_demo sink_properties=device.description=HandsfreeDemo)
mic=$(pactl load-module module-remap-source master=hf_demo.monitor source_name=hf_demo_mic \
  source_properties=device.description=HandsfreeDemoMic)
cp "$conf" "$take/.config-backup"
supervisor=""

cleanup() {
  set +e
  touch "$take/.stop"
  [ -f "$take/.recpid" ] && kill -INT "$(cat "$take/.recpid")" 2>/dev/null
  [ -n "$supervisor" ] && wait "$supervisor"  # the encoder flushes before exiting
  handsfree-ctl voice off >/dev/null 2>&1
  cp "$take/.config-backup" "$conf" && rm -f "$take/.config-backup"
  systemctl --user unset-environment HANDSFREE_DEMO_LOG HANDSFREE_DEMO_T0
  systemctl --user restart handsfree
  pactl unload-module "$mic"; pactl unload-module "$sink"
  if [ -n "$orig_theme" ] && [ "$(omarchy-theme-current)" != "$orig_theme" ]; then
    omarchy-theme-set "$orig_theme" >/dev/null 2>&1
  fi
  pkill -x firefox
  rm -f "$take/.stop" "$take/.recpid"
  echo "take saved: $here/$take"
}
trap cleanup EXIT

printf '\n[voice]\ninput_device = "pulse:hf_demo_mic"\n\n[desktop]\nurl_opener = ["firefox", "--profile", "%s"]\n' \
  "$profile" >> "$conf"

# A clean English Firefox profile, so nothing personal is on screen.
mkdir -p "$profile"
[ -f "$profile/user.js" ] || cp ffprofile-user.js "$profile/user.js"
pkill -x firefox || true
sleep 1
rm -rf "$profile"/sessionstore.jsonlz4 "$profile"/sessionstore-backups "$profile"/sessionCheckpoints.json

# Start on workspace 1 with the pointer in the middle of the screen, where
# new windows land, so scrolling reaches whatever window opens.
dispatch 'hl.dsp.focus({ workspace = "1" })' 'workspace 1'
read -r mx my mw mh scale < <(hyprctl -j monitors | jq -r '.[] | select(.focused) | "\(.x) \(.y) \(.width) \(.height) \(.scale)"')
cx=$(awk -v x="$mx" -v w="$mw" -v s="$scale" 'BEGIN { printf "%d", x + w / s / 2 }')
cy=$(awk -v y="$my" -v h="$mh" -v s="$scale" 'BEGIN { printf "%d", y + h / s / 2 }')
dispatch "hl.dsp.cursor.move({ x = $cx, y = $cy })" "movecursor $cx $cy"

# -- record --------------------------------------------------------------------
t0=$(now)
(
  # gpu-screen-recorder survives Omarchy theme switches (wf-recorder doesn't);
  # restart it anyway if it ever dies, as a new part.
  i=0
  while [ ! -f "$take/.stop" ] && [ $i -lt 5 ]; do
    echo "{\"file\": \"screen-$i.mp4\", \"t\": $(since)}" >> "$take/parts.jsonl"
    gpu-screen-recorder -w screen -f "$FPS" -fm cfr -k h264 -encoder cpu -q "$QUALITY" \
      -a hf_demo.monitor -ac aac -o "$take/screen-$i.mp4" >> "$take/recorder.log" 2>&1 &
    echo $! > "$take/.recpid"
    wait $! || true
    i=$((i + 1))
  done
) &
supervisor=$!

# Restart handsfree with the command log on, timed from the recording start.
systemctl --user set-environment HANDSFREE_DEMO_LOG="$log" HANDSFREE_DEMO_T0="$t0"
systemctl --user restart handsfree
for _ in $(seq 150); do
  journalctl --user -u handsfree --since "@${t0%.*}" -q --no-pager | grep -q "handsfree ready" && break
  sleep 0.2
done
handsfree-ctl dictation off >/dev/null
handsfree-ctl voice on >/dev/null
sleep 1

missed=0
for step in "${steps[@]}"; do
  IFS='|' read -r n words hold clip <<< "$step"
  before=$(wc -l < "$log")
  start=$(since)
  paplay --device=hf_demo "$clip"
  end=$(since)
  deadline=$(( $(date +%s) + TIMEOUT ))
  while [ "$(wc -l < "$log")" -le "$before" ] && [ "$(date +%s)" -lt "$deadline" ]; do sleep 0.1; done
  heard=$(tail -n +$((before + 1)) "$log" | jq -rs 'map(.heard) | join(" / ")')
  ok=$(tail -n +$((before + 1)) "$log" | jq -s 'length > 0 and all(.ok)')
  jq -cn --arg n "$n" --arg words "$words" --arg clip "$clip" --arg heard "$heard" \
    --argjson start "$start" --argjson end "$end" --argjson ok "$ok" \
    '{n: $n, words: $words, clip: $clip, start: $start, end: $end, heard: $heard, ok: $ok}' >> "$take/clips.jsonl"
  if [ "$ok" = true ]; then
    printf '%s  %-24s heard: %s\n' "$n" "$words" "$heard"
  else
    printf '%s  %-24s MISSED (heard: %s)\n' "$n" "$words" "${heard:-nothing}"
    missed=$((missed + 1))
  fi
  sleep "$(awk -v a="$SETTLE" -v b="$hold" 'BEGIN { print a + b }')"
done
sleep 0.5

jq -n --argjson t0 "$t0" --argjson fps "$FPS" --argjson missed "$missed" \
  --argjson monitor "$(hyprctl -j monitors | jq '.[] | select(.focused) | {x, y, width, height, scale}')" \
  '{t0: $t0, fps: $fps, missed: $missed, monitor: $monitor}' > "$take/meta.json"
[ "$missed" -eq 0 ] || echo "$missed clip(s) missed; see $take/clips.jsonl" >&2
