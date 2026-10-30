#!/bin/bash
# Placeholder command clips from macOS `say`, for testing the pipeline only.
# Writes voice/placeholder/NN.wav (48 kHz mono) for every line of commands.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
voice=${VOICE:-Samantha}
mkdir -p voice/placeholder
grep -v '^#' commands.txt | while IFS='|' read -r n words _hold; do
  [ -n "$n" ] || continue
  say -v "$voice" -r 175 -o "/tmp/hf-$n.aiff" "$words"
  ffmpeg -loglevel error -y -i "/tmp/hf-$n.aiff" -ar 48000 -ac 1 "voice/placeholder/$n.wav"
  rm -f "/tmp/hf-$n.aiff"
  echo "$n  $words"
done
