"""Voice the demo with ElevenLabs: narrator + a second voice for spoken commands.

    python tts_elevenlabs.py <demo dir> list            # show available voices
    python tts_elevenlabs.py <demo dir> <narrator_id> <commands_id>

The API key is read from ~/.config/elevenlabs.env and never printed.
"""
import json, os, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

raw = Path(os.path.expanduser("~/.config/elevenlabs.env")).read_text()
match = re.search(r"ELEVENLABS_API_KEY\s*=\s*['\"]?([^'\"\s]+)", raw)
KEY = match.group(1) if match else raw.strip()
API = "https://api.elevenlabs.io"


def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs {path}: HTTP {e.code} {e.read()[:300].decode(errors='replace')}")


base = Path(sys.argv[1])
if sys.argv[2] == "list":
    for v in json.loads(call("/v2/voices?page_size=100"))["voices"]:
        l = v.get("labels") or {}
        print(v["voice_id"], v["name"], "|", l.get("gender", ""), l.get("age", ""), l.get("accent", ""),
              l.get("descriptive", ""), l.get("use_case", ""), "|", v.get("category", ""))
    sys.exit()

narrator, commander = sys.argv[2], sys.argv[3]
script = json.loads((base / "script.json").read_text())
out = base / "audio"; out.mkdir(exist_ok=True)
lines = {k: (script[k], narrator) for k in ("hook", "intro", "install", "outro")}
for i, step in enumerate(script["steps"], 1):
    if step.get("narration"):
        lines[f"n{i:02d}"] = (step["narration"], narrator)
    lines[f"c{i:02d}"] = (step["command"], commander)

durations = {}
for name, (text, voice) in lines.items():
    settings = ({"stability": 0.35, "similarity_boost": 0.8, "style": 0.45, "use_speaker_boost": True}
                if voice == narrator else {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15})
    mp3 = call(f"/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
               {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": settings})
    (out / f"{name}.mp3").write_bytes(mp3)
    # trim leading/trailing silence so timing is tight, then 48 kHz mono WAV
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / f"{name}.mp3"), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "apad=pad_dur=0.08", "-ar", "48000", "-ac", "1", str(out / f"{name}.wav")], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(out / f"{name}.wav")], capture_output=True, text=True).stdout)
    durations[name] = round(dur, 3)
    print(f"{name:8} {dur:5.2f}s  {text}")
(base / "durations.json").write_text(json.dumps(durations, indent=1))
