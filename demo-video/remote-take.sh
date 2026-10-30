#!/bin/bash
# For recording in a VM (e.g. Try Omarchy on a Mac): copy this folder to the
# Omarchy machine, run record.sh there, and bring the take back to takes/.
#
#   ./remote-take.sh [clip numbers...]
#   OMARCHY=user@host OMARCHY_PORT=2222 ./remote-take.sh
set -euo pipefail
cd "$(dirname "$0")"
host=${OMARCHY:-$USER@127.0.0.1}
port=${OMARCHY_PORT:-2222}
dir=${OMARCHY_DIR:-demo-video}
ssh_cmd="ssh -p $port"

rsync -a -e "$ssh_cmd" --exclude node_modules --exclude takes --exclude out --exclude public \
  --exclude src --exclude ffprofile ./ "$host:$dir/"
$ssh_cmd "$host" "cd $dir && ./record.sh $*"
name=$($ssh_cmd "$host" "ls -t $dir/takes | head -1")
rsync -a -e "$ssh_cmd" "$host:$dir/takes/$name" takes/
# The voice on its own, for the editor's waveform and mix.
ffmpeg -loglevel error -y -i "takes/$name/screen-0.mp4" -vn -ac 1 -ar 48000 "takes/$name/voice.wav"
echo "takes/$name"
