"""Run Whisper and the intent parser on WAV files, without the daemon.

    python dev/check_stt.py recording1.wav recording2.wav

Record test clips with `arecord -f S16_LE -r 16000 -c 1 -d 3 clip.wav` (Linux)
to see what Whisper hears for your voice and which command it maps to. Uses
your ~/.config/handsfree settings and commands.
"""

import sys
import time
import wave

import numpy as np

from handsfree.audio.stt import Transcriber
from handsfree.config import Config
from handsfree.intents.apps import LazyAppIndex
from handsfree.intents.parser import Parser

ACTIONS = ("run", "url", "app", "hypr", "type", "key", "mouse", "internal")


def load(path: str) -> np.ndarray:
    with wave.open(path) as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
            sys.exit(f"{path}: need 16 kHz mono 16-bit WAV")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def main() -> None:
    config = Config.load()
    voice = config.section("voice")
    stt = Transcriber(voice["model"], voice["device"], voice["compute_type"], voice["language"], voice["prompt"])
    parser = Parser(config.commands, apps=LazyAppIndex(), threshold=float(voice["fuzzy_threshold"]))
    for path in sys.argv[1:]:
        start = time.monotonic()
        text = stt.transcribe(load(path))
        intent = parser.parse(text)
        action = next((f"{k} = {intent.command[k]!r} {intent.slots}" for k in ACTIONS if intent and k in intent.command), "not understood")
        print(f"{path}: {time.monotonic() - start:.1f}s  heard {text!r} -> {action}")


if __name__ == "__main__":
    main()
