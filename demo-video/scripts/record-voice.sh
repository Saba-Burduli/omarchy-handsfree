#!/bin/bash
# Record your own command clips on a Mac: shows each line of commands.txt,
# records from the default mic until you press Enter, trims the silence and
# saves voice/NN.wav (48 kHz mono, peak-normalized).
#
#   ./scripts/record-voice.sh          every clip that isn't recorded yet
#   ./scripts/record-voice.sh 05 12    redo just these
set -euo pipefail
cd "$(dirname "$0")/.."
mic=${MIC:-:default}  # ffmpeg avfoundation device; list with: ffmpeg -f avfoundation -list_devices true -i ""
mkdir -p voice

trim() {  # drop silence at both ends, keep 80 ms of air, normalize the peak
  ffmpeg -loglevel error -y -i "$1" -af "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,dynaudnorm=f=150:g=15:p=0.9" \
    -ar 48000 -ac 1 "$2"
}

grep -v '^#' commands.txt | while IFS='|' read -r n words _hold; do
  [ -n "$n" ] || continue
  if [ $# -gt 0 ]; then [[ " $* " == *" $n "* ]] || continue
  elif [ -f "voice/$n.wav" ]; then continue
  fi
  while true; do
    printf '\n%s  say: \033[1m%s\033[0m\n   Enter to start...' "$n" "$words"
    read -r < /dev/tty
    raw=$(mktemp -t hfvoice).wav
    ffmpeg -loglevel error -y -f avfoundation -i "$mic" -ac 1 "$raw" < /dev/null &
    pid=$!
    printf '   recording, Enter to stop...'
    read -r < /dev/tty
    kill -INT "$pid"; wait "$pid" || true
    trim "$raw" "voice/$n.wav"; rm -f "$raw"
    afplay "voice/$n.wav"
    printf '   keep it? [Y/n] '
    read -r ans < /dev/tty
    [[ "$ans" =~ ^[Nn] ]] || break
  done
done
echo; echo "clips in voice/. Next: ./remote-take.sh (or ./record.sh on Omarchy)"
