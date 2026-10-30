#!/bin/bash
# Record your own voice for the demo on a Mac. Shows each line, records from
# the mic until you press Enter, cleans it up, plays it back, and asks to keep it.
#
#   ./scripts/record-voice.sh                 command clips -> voice/NN.wav (played into handsfree's mic)
#   ./scripts/record-voice.sh narration       narrator lines -> public/vo/<id>.mp3 (+ src/vo.json)
#   ./scripts/record-voice.sh 05 12           redo just these commands
#   ./scripts/record-voice.sh narration intro redo one narrator line
#   ./scripts/record-voice.sh --reprocess     re-clean every raw take (after tuning the filters)
#
# Raw takes are kept in voice/raw/ so they can be re-cleaned later.
set -euo pipefail
cd "$(dirname "$0")/.."
mic=${MIC:-:default}  # ffmpeg avfoundation device; list with: ffmpeg -f avfoundation -list_devices true -i ""
mkdir -p voice/raw public/vo

# Clean a raw take: cut rumble below 80 Hz, reduce steady background noise,
# trim silence at both ends (keeping 80 ms of air), even out the level, then
# normalize loudness so every clip sounds the same.
clean() {
  ffmpeg -loglevel error -y -i "$1" -af "highpass=f=80,afftdn=nf=-25,\
silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,\
silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,\
acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=7" \
    -ar 48000 -ac 1 "$2"
}

out_for() {  # kind id -> output path
  if [ "$1" = narration ]; then echo "public/vo/$2.mp3"; else echo "voice/$2.wav"; fi
}

finish() {  # kind id: clean the raw take into place
  local raw="voice/raw/$1-$2.wav" out
  out=$(out_for "$1" "$2")
  clean "$raw" "${out%.*}.tmp.wav"
  if [ "$1" = narration ]; then
    ffmpeg -loglevel error -y -i "${out%.*}.tmp.wav" -c:a libmp3lame -q:a 2 "$out"
    rm "${out%.*}.tmp.wav"
  else
    mv "${out%.*}.tmp.wav" "$out"
  fi
}

write_durations() {  # src/vo.json: what the edit uses to time narration
  node -e '
    const fs = require("fs"), { execFileSync } = require("child_process");
    const lines = JSON.parse(fs.readFileSync("narration.json", "utf8")), out = {};
    for (const id of Object.keys(lines)) {
      const f = `public/vo/${id}.mp3`;
      if (fs.existsSync(f)) out[id] = +execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], { encoding: "utf8" }).trim();
    }
    fs.writeFileSync("src/vo.json", JSON.stringify(out, null, 1));'
}

if [ "${1:-}" = --reprocess ]; then
  for raw in voice/raw/*.wav; do
    name=$(basename "$raw" .wav)
    finish "${name%%-*}" "${name#*-}"
    echo "cleaned $name"
  done
  write_durations
  exit 0
fi

kind=command
if [ "${1:-}" = narration ]; then kind=narration; shift; fi

# The lines to record: "id|text"
if [ $kind = narration ]; then
  lines=$(node -e 'for (const [k, v] of Object.entries(require("./narration.json"))) console.log(`${k}|${v}`)')
else
  lines=$(grep -v '^#' commands.txt | grep -v '^\s*$' | cut -d'|' -f1,2)
fi

echo "Mic: $mic   (Enter starts and stops each recording; speak the line exactly as shown)"
[ $kind = narration ] && echo "Narration: speak like you're showing a friend, upbeat, not rushed."
[ $kind = command ] && echo "Commands: say each one clearly, as you would to your computer. One take, no 'um'."

while IFS='|' read -r id text; do
  [ -n "$id" ] || continue
  if [ $# -gt 0 ]; then [[ " $* " == *" $id "* ]] || continue
  elif [ -f "$(out_for $kind "$id")" ] && [ -f "voice/raw/$kind-$id.wav" ]; then continue
  fi
  while true; do
    printf '\n\033[2m%s\033[0m  \033[1m%s\033[0m\n   Enter to start... ' "$id" "$text"
    read -r < /dev/tty
    raw="voice/raw/$kind-$id.wav"
    ffmpeg -loglevel error -y -f avfoundation -i "$mic" -ac 1 -ar 48000 "$raw" < /dev/null &
    pid=$!
    printf '   \033[31m● recording\033[0m, Enter to stop... '
    read -r < /dev/tty
    sleep 0.3  # don't clip the last word
    kill -INT "$pid"; wait "$pid" || true
    peak=$(ffmpeg -i "$raw" -af volumedetect -f null - 2>&1 | sed -n 's/.*max_volume: \(-*[0-9.]*\) dB/\1/p')
    if awk -v p="${peak:--99}" 'BEGIN { exit !(p < -40) }'; then
      echo "   almost silent (peak ${peak} dB): check the mic, or System Settings > Privacy > Microphone"
      continue
    fi
    finish $kind "$id"
    afplay "$(out_for $kind "$id")"
    printf '   keep it? [Enter = yes, n = redo] '
    read -r ans < /dev/tty
    [[ "$ans" =~ ^[Nn] ]] || break
  done
done <<< "$lines"

[ $kind = narration ] && write_durations
echo
echo "Done. Tell Claude, and it will record a new take and re-edit the video."
