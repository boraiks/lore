import unittest

from lorelib import transcript
from tests.fixtures import claude_transcript, codex_transcript
from tests.helpers import VaultCase


class ClaudeTest(VaultCase):
    def test_user_and_assistant_text_only(self):
        path = claude_transcript(self.notes.parent / "t.jsonl", ["Merhaba", "İkinci soru"],
                                 ["Selam", "Cevap iki"])
        conv = transcript.read(path)
        self.assertEqual(conv.prompts, ["Merhaba", "İkinci soru"])
        self.assertEqual(conv.last_answer, "Cevap iki")
        self.assertEqual(conv.answers, 2)
        self.assertEqual(conv.session_id, "abc")
        self.assertEqual(conv.started, "2026-10-17T08:00:00.000Z")

    def test_skips_injected_and_meta(self):
        extra = [
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "meta"}},
            {"type": "user", "message": {"role": "user", "content": "<command-name>/clear</command-name>"}},
            {"type": "user", "isSidechain": True, "message": {"role": "user", "content": "alt ajan"}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "araç çıktısı"}]}},
            {"type": "user", "message": {"role": "user",
                                         "content": "<system-reminder>gizli</system-reminder>Gerçek soru"}},
            "bozuk satır",
        ]
        path = claude_transcript(self.notes.parent / "t.jsonl", ["Bir"], ["İki"], title="Başlık",
                                 extra=extra)
        conv = transcript.read(path)
        self.assertEqual(conv.prompts, ["Bir", "Gerçek soru"])
        self.assertEqual(conv.title, "Başlık")


class CodexTest(VaultCase):
    def test_codex_rollout(self):
        path = codex_transcript(self.notes.parent / "r.jsonl", ["Kodu düzelt"], ["Düzelttim"])
        conv = transcript.read(path)
        self.assertEqual(conv.prompts, ["Kodu düzelt"])
        self.assertEqual(conv.last_answer, "Düzelttim")
        self.assertEqual(conv.session_id, "019a-codex")

    def test_missing_file(self):
        with self.assertRaises(OSError):
            transcript.read(self.notes.parent / "yok.jsonl")


if __name__ == "__main__":
    unittest.main()
