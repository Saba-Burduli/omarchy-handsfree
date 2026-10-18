import sys
import threading
import types
import unittest
from unittest import mock

try:
    import numpy as np
except ImportError:  # the capture loop needs numpy; the rest of the suite doesn't
    np = None

from handsfree.audio.vad import EndpointConfig


def fake_sounddevice(levels, frame=480):
    """An InputStream that plays one frame per level (constant amplitude)."""

    class InputStream:
        def __init__(self, samplerate, channels, dtype, blocksize, device, callback):
            self.callback = callback
            self.thread = threading.Thread(target=self.play, daemon=True)

        def play(self):
            for level in levels:
                self.callback(np.full((frame, 1), level, dtype=np.float32), frame, None, None)

        def __enter__(self):
            self.thread.start()
            return self

        def __exit__(self, *exc):
            self.thread.join(timeout=1)

    return types.SimpleNamespace(InputStream=InputStream)


@unittest.skipIf(np is None, "numpy not installed")
class MicrophoneTest(unittest.TestCase):
    def record(self, levels, finish_after=None, **cfg):
        from handsfree.audio.capture import Microphone

        cancel, finish = threading.Event(), threading.Event()
        if finish_after is not None:
            threading.Timer(finish_after, finish.set).start()
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sounddevice(levels)}):
            return Microphone().record_utterance(EndpointConfig(**cfg), cancel, finish)

    def test_returns_speech_with_preroll(self):
        audio = self.record([0.001] * 40 + [0.2] * 20 + [0.001] * 30)
        self.assertIsNotNone(audio)
        # 10 preroll frames + 20 speech frames + trailing silence up to the end point
        self.assertEqual(len(audio) % 480, 0)
        self.assertGreaterEqual(len(audio), 30 * 480)
        self.assertLess(len(audio), 70 * 480)
        self.assertAlmostEqual(float(audio[:480].max()), 0.001, places=5)

    def test_silence_times_out(self):
        self.assertIsNone(self.record([0.001] * 200, start_timeout_ms=900))


if __name__ == "__main__":
    unittest.main()
