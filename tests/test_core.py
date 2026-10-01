import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from chat_assistant.capture import rows_to_transcript
from chat_assistant.core import Settings, StableGate, parse_manual
from chat_assistant.storage import SettingsStore


def row(text, x1, y1, x2, y2, confidence=.98):
    return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]], text, confidence]


class CoreTests(unittest.TestCase):
    def test_sender_alignment_and_wrapped_message(self):
        rows = [row("今天", 270, 10, 330, 30), row("对方的长消息", 30, 55, 510, 77), row("这是续行", 30, 82, 180, 104), row("我的回答", 420, 160, 560, 182), row("低质量噪点", 10, 220, 100, 240, .2)]
        transcript = rows_to_transcript(rows, 600)
        self.assertEqual([(m.speaker, m.text) for m in transcript.messages], [("对方", "对方的长消息\n这是续行"), ("我", "我的回答")])
        reversed_transcript = rows_to_transcript(rows, 600, False)
        self.assertEqual(reversed_transcript.messages[1].speaker, "对方")

    def test_manual_keeps_unknown_and_continuation(self):
        transcript = parse_manual("是谁说的还不知道\n对方: 今天很累\n还有很多事\n我：先休息一下")
        self.assertEqual(transcript.messages[0].speaker, "未确认")
        self.assertEqual(transcript.messages[1].text, "今天很累\n还有很多事")
        self.assertTrue(transcript.warnings)

    def test_stable_gate_dedupe_cooldown_and_failed_retry(self):
        gate = StableGate()
        gate.observe("A")
        self.assertFalse(gate.ready(10))
        gate.observe("B")
        self.assertFalse(gate.ready(10))
        gate.observe("B")
        self.assertTrue(gate.ready(10))
        gate.submitted(10, 8)
        self.assertFalse(gate.ready(15))
        self.assertTrue(gate.ready(18))  # A failed request is not marked completed.
        gate.succeeded("B")
        self.assertFalse(gate.ready(50))
        gate.observe("C")
        gate.observe("C")
        self.assertTrue(gate.ready(50))

    def test_dpapi_roundtrip_no_plaintext_and_forget_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(Path(folder))
            settings = Settings(chat_key="synthetic-secret-deepseek", jev_key="synthetic-secret-jev")
            store.save(settings)
            saved = store.path.read_text(encoding="utf-8")
            self.assertNotIn("synthetic-secret", saved)
            self.assertEqual(store.load().chat_key, settings.chat_key)
            self.assertEqual(store.load().jev_key, settings.jev_key)
            store.save(replace(settings, remember_keys=False))
            self.assertNotIn("encrypted", store.path.read_text(encoding="utf-8"))

    def test_settings_reject_nan_and_invalid_limits(self):
        for settings in (Settings(interval=float("nan")), Settings(cooldown=0), Settings(timeout=1)):
            with self.assertRaises(ValueError):
                settings.validate(False)


if __name__ == "__main__":
    unittest.main()
