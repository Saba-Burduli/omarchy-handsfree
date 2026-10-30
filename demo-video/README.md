# Demo video

The Omarchy Hands-Free demo, recorded for real and edited with [Remotion](https://remotion.dev).
Every action on screen is the plugin reacting to voice audio. The scripts only
play clips into a virtual mic and record the screen; nothing is triggered directly.

## 1. Voice clips

`commands.txt` lists the commands in order (`NN|words|extra hold seconds`).
Record each one as `voice/NN.wav` (`voice/01.wav`, `voice/02.wav`, ...).
`scripts/record-voice.sh` does this on a Mac: it shows each line, records until
you press Enter, trims the silence and plays it back.
Until those exist, `scripts/placeholder-voice.sh` makes test clips with macOS `say`
in `voice/placeholder/`.

## 2. Record a take

On the Omarchy machine:

```bash
./record.sh            # every clip
./record.sh 04 07      # just these, for a quick test
```

From a Mac running Try Omarchy (SSH on port 2222), this copies the folder over,
records there, and brings the take back:

```bash
./remote-take.sh
```

`record.sh` makes a PipeWire null sink + virtual source, points handsfree at it
(`input_device = "pulse:hf_demo_mic"`), restarts handsfree with
`HANDSFREE_DEMO_LOG` on, records the screen with gpu-screen-recorder at native
resolution and 60 fps (the voice is the video's audio track), plays each clip,
waits for the command log to report the result, then restores the config,
audio and theme. Takes land in `takes/<timestamp>/`; misheard clips are flagged.

## 3. Edit

```bash
node scripts/prep.mjs          # newest take -> public/take/, src/take.json
npx remotion studio            # preview
npx remotion render Wide out/demo-wide.mp4
npx remotion render Vertical out/demo-vertical.mp4
```

`src/config.ts` picks the hook, clip order, montage clips, section chips and the
outro text. Zooms come only from the command log: the camera springs onto the
window handsfree reported after each command, capped at 1:1 source pixels so
it stays sharp. Put a track at `music.mp3` and re-run prep to add music; cuts
snap to its beats.
