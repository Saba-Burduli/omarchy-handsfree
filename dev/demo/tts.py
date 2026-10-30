"""Synthesize narration (af_heart) and spoken commands (am_michael) with Kokoro."""
import json, sys
from pathlib import Path
import soundfile as sf
from kokoro_onnx import Kokoro

# espeakng-loader's bundled library has its CI build path baked in; use Homebrew's espeak-ng.
BREW = "/opt/homebrew/opt/espeak-ng"

base = Path(sys.argv[1]); tts = Path(sys.argv[2])
from kokoro_onnx.config import EspeakConfig
k = Kokoro(str(tts / "kokoro-v1.0.onnx"), str(tts / "voices-v1.0.bin"),
           espeak_config=EspeakConfig(f"{BREW}/lib/libespeak-ng.dylib", f"{BREW}/share/espeak-ng-data"))
script = json.loads((base / "script.json").read_text())
out = base / "audio"; meta = {}

def make(name, text, voice, speed):
    samples, rate = k.create(text, voice=voice, speed=speed, lang="en-us")
    sf.write(out / f"{name}.wav", samples, rate)
    meta[name] = round(len(samples) / rate, 3)

make("intro", script["intro"], "af_heart", 1.0)
make("outro", script["outro"], "af_heart", 1.0)
for i, step in enumerate(script["steps"], 1):
    if step.get("narration"):
        make(f"n{i:02d}", step["narration"], "af_heart", 1.0)
    make(f"c{i:02d}", step["command"], "am_michael", 0.95)
(base / "durations.json").write_text(json.dumps(meta, indent=1))
print(json.dumps(meta))
