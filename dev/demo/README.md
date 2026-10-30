# Making the demo video

How `docs/demo.mp4` was made, so it can be redone after UI changes.

1. **Voices**: `tts.py <this dir> <kokoro dir>` synthesizes the narration
   (Kokoro `af_heart`) and the spoken commands (`am_michael`) from
   `script.json` into `audio/`, and writes `durations.json`. It needs
   `kokoro-onnx`, the Kokoro v1.0 model files, and espeak-ng (Homebrew's,
   because the bundled one has a broken data path on macOS).
2. **Recording**: copy this folder, `audio/` and `durations.json` into the
   Omarchy machine and run `python3 record.py raw2`. It creates a virtual
   PipeWire mic, points handsfree at it (`input_device = "pulse:hf_demo_mic"`)
   so room noise can't leak in, plays each command clip into it with gaps for
   the narration, records the screen with wf-recorder, and writes
   `timeline.json`. Firefox runs from a clean profile (`ffprofile/` with an
   English, no-bookmarks `user.js`) so nothing personal is on screen.
3. **Editing**: `edit.py <dir> out.mp4` turns `raw2.mp4` + `timeline.json`
   into the final cut: title card, eased zooms on each action, "YOU SAY"
   captions, narration subtitles, a cut, an end card, and the mixed
   voiceover. Needs opencv, pillow, numpy and ffmpeg.
