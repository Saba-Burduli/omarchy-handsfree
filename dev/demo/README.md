# Making the demo video

How `docs/demo.mp4` was made, so it can be redone after UI changes.

1. **Voices**: `tts_elevenlabs.py <dir> list` shows the account's voices;
   `tts_elevenlabs.py <dir> <narrator_id> <commands_id>` voices every line of
   `script.json` (narration plus the spoken commands) into `audio/` and writes
   `durations.json`. The key is read from `~/.config/elevenlabs.env`
   (`ELEVENLABS_API_KEY=...`). The demo used Liam (narrator) and Sarah
   (commands). `tts.py` is a free, offline alternative using Kokoro.
2. **Check**: run the command clips through Whisper with the daemon's prompt
   before recording. This is how "Open Neovim" and "Run fastfetch" were found
   to need vocabulary hints.
3. **Recording**: copy `script.json`, `durations.json`, `record.py` and
   `audio/c*.wav` to the Omarchy machine and run `python3 record.py raw`.
   It records the screen at native resolution with gpu-screen-recorder
   (wf-recorder dies on theme switches), points handsfree at a virtual
   PipeWire mic so room noise can't leak in, plays each command with gaps for
   narration, logs the active window after each step, and restores your
   config, audio and theme afterwards. Firefox runs from a clean English
   profile (`ffprofile/` with a `user.js`), so nothing personal is on screen.
4. **Editing**: write `sync.json` (`{"part_lag": [0.1]}`, the recorder's start
   delay) and run `edit.py <dir> out.mp4`. Each step is cut to "command
   spoken, then the result", skipping the ~1 s wait for end of speech. It
   zooms onto the reported window, capped at 1.8x so the 3456-wide source stays
   sharp at 1080p, and adds captions, a kinetic hook, an install card, an end
   card and the voiceover mix.
