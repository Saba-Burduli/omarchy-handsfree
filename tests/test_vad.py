import unittest

from handsfree.audio.vad import EndpointConfig, Endpointer


def run(levels, **kw):
    ep = Endpointer(EndpointConfig(**kw))
    for i, rms in enumerate(levels):
        if ep.feed(rms):
            return ep.reason, i
    return ep.state, None


class EndpointerTest(unittest.TestCase):
    def test_speech_then_silence_ends(self):
        reason, _ = run([0.001] * 10 + [0.1] * 20 + [0.001] * 30)
        self.assertEqual(reason, "end")

    def test_timeout_without_speech(self):
        self.assertEqual(run([0.001] * 200, start_timeout_ms=900)[0], "timeout")

    def test_wait_forever_in_continuous_mode(self):
        self.assertEqual(run([0.001] * 1000, start_timeout_ms=None)[0], "waiting")

    def test_click_is_not_speech(self):
        self.assertEqual(run([0.001] * 5 + [0.5] + [0.001] * 5, start_timeout_ms=None)[0], "waiting")

    def test_max_length(self):
        self.assertEqual(run([0.1] * 1000, max_ms=3000)[0], "max")

    def test_adapts_to_noise_floor(self):
        # Constant fan noise above the fixed threshold must not count as speech.
        ep = Endpointer(EndpointConfig(threshold=0.001, start_timeout_ms=None))
        ep.noise = 0.02
        self.assertGreater(ep.threshold(), 0.02)

    def test_early_stop(self):
        ep = Endpointer(EndpointConfig())
        for rms in [0.1] * 10:
            ep.feed(rms)
        ep.stop()
        self.assertEqual(ep.reason, "stopped")


if __name__ == "__main__":
    unittest.main()
