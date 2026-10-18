import threading
import time
import unittest

from handsfree.audio.worker import VoiceWorker


class FakeMic:
    def __init__(self, utterances):
        self.utterances = list(utterances)

    def record_utterance(self, config, cancel, finish, on_speech=None):
        if not self.utterances:
            cancel.wait(5)  # like a quiet room: block until cancelled
            return None
        if on_speech:
            on_speech()
        return self.utterances.pop(0)


class FakeTranscriber:
    def transcribe(self, audio):
        return audio


class WorkerTest(unittest.TestCase):
    def make(self, utterances, **settings):
        self.heard = []
        self.listening = []
        self.done = threading.Event()

        def on_text(text, push):
            self.heard.append((text, push))
            self.done.set()

        worker = VoiceWorker(settings, on_text, self.listening.append, lambda exc: None)
        worker.microphone = FakeMic(utterances)
        worker.transcriber = FakeTranscriber()
        self.addCleanup(worker.shutdown)
        return worker

    def test_push_to_talk(self):
        worker = self.make(["open google"])
        self.assertEqual(worker.listen_once(), "listening")
        self.assertTrue(self.done.wait(2))
        self.assertEqual(self.heard, [("open google", True)])
        self.assertEqual(self.listening[:1], [True])

    def test_push_to_talk_interrupts_wake_word_wait(self):
        class FakeWake:
            def wait(self, cancel):
                cancel.wait(5)
                return False

        worker = self.make(["open browser"], wake_word="hey_jarvis")
        worker._wake_word = FakeWake()
        worker.set_continuous(True)
        deadline = time.monotonic() + 2
        while not worker.awaiting_wake_word and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(worker.awaiting_wake_word)
        worker.listen_once()
        self.assertTrue(self.done.wait(2))
        self.assertEqual(self.heard, [("open browser", True)])
        worker.set_continuous(False)

    def test_continuous_until_turned_off(self):
        worker = self.make(["one", "two"])
        worker.set_continuous(True)
        deadline = time.monotonic() + 2
        while len(self.heard) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        worker.set_continuous(False)
        self.assertEqual(self.heard, [("one", False), ("two", False)])


if __name__ == "__main__":
    unittest.main()
