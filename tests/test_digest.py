"""Automatic session summaries: `digest` turns a transcript into a short excerpt a subagent
can summarize, `pending` lists sessions still without an outcome, and `seal` takes a
Details section and records who wrote it."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from lorelib import cli, digest, frontmatter, hook, mesh, seal, sessionlog, sessions, vault
from tests.fixtures import antigravity_transcript, claude_transcript, codex_transcript
from tests.helpers import NOW, VaultCase

SID = "11111111-2222-3333-4444-555555555555"


class DigestTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.root = self.notes.parent

    def test_claude_turns_files_and_no_thinking(self):
        edit = {"type": "assistant", "sessionId": "abc", "timestamp": "t",
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "name": "Edit",
                     "input": {"file_path": "C:/proje/app.py", "old_string": "a", "new_string": "b"}}]}}
        path = claude_transcript(self.root / "c.jsonl", ["Uygulamayı düzelt", "Testleri çalıştır"],
                                 ["Hata app.py'de; düzelttim.", "Testler geçti."], extra=[edit])
        text = digest.build(path)
        self.assertIn("DATA", text.splitlines()[0])
        for part in ("Uygulamayı düzelt", "düzelttim", "Testler geçti", "C:/proje/app.py"):
            self.assertIn(part, text)
        self.assertNotIn("gizli düşünce", text)          # thinking is never included

    def test_codex_and_antigravity_are_read(self):
        c = codex_transcript(self.root / "x.jsonl", ["Rapor yaz"], ["Rapor hazır."])
        self.assertIn("Rapor hazır.", digest.build(c))
        self.assertNotIn("sistem talimatı", digest.build(c))
        a = antigravity_transcript(self.root / "ag" / "t.jsonl", ["Ders planı"], ["Plan bitti."])
        text = digest.build(a)
        self.assertIn("Ders planı", text)
        self.assertNotIn("gizli/yol.txt", text)            # client metadata is dropped

    def test_reminder_turns_and_secrets_are_dropped(self):
        path = claude_transcript(
            self.root / "c.jsonl",
            ["Anahtarım sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA ile dene",
             "[lore-reminder] This session has no outcome record yet"],
            ["Tamam.", "Kaydettim."])
        text = digest.build(path)
        self.assertNotIn("sk-ant-api03-AAAA", text)
        self.assertNotIn("lore-reminder", text)

    def test_long_sessions_keep_the_start_and_the_end(self):
        prompts = [f"istek {i} " + "x" * 400 for i in range(120)]
        answers = [f"cevap {i} " + "y" * 400 for i in range(120)]
        text = digest.build(claude_transcript(self.root / "c.jsonl", prompts, answers))
        self.assertLessEqual(len(text), digest.MAX_CHARS + 500)
        self.assertIn("istek 0 ", text)
        self.assertIn("cevap 119 ", text)
        self.assertIn("left out", text)

    def test_find_transcript_per_client(self):
        claude_root, codex_root, ag_root = self.root / "cl", self.root / "cx", self.root / "ag"
        (claude_root / "C--proje").mkdir(parents=True)
        (claude_root / "C--proje" / f"{SID}.jsonl").write_text("{}", encoding="utf-8")
        (codex_root / "2026" / "11").mkdir(parents=True)
        (codex_root / "2026" / "11" / f"rollout-2026-11-01T10-00-00-{SID}.jsonl").write_text("{}", encoding="utf-8")
        ag = ag_root / "brain" / SID / ".system_generated" / "logs"
        ag.mkdir(parents=True)
        (ag / "transcript.jsonl").write_text("{}", encoding="utf-8")
        roots = {"claude": [claude_root], "codex": [codex_root], "antigravity": [ag_root]}
        for client in roots:
            self.assertIsNotNone(digest.find_transcript(client, SID, roots), client)
        self.assertIsNone(digest.find_transcript("claude", "yok-yok", roots))


class PendingTest(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")
        for sid, n in (("aaaa1111", 40), ("bbbb2222", 30), ("cccc3333", 3), ("dddd4444", 25),
                       ("eeee5555", 50)):
            sessionlog.record("claude", sid, n, "Stop")
        seal.seal(self.notes, "claude", "a\nb\nc", ["home"], session_id="bbbb2222", now=NOW,
                  machine="M")
        sessions.mark_private(vault.STATE_DIR, "dddd4444")
        sessions.mark_skipped(vault.STATE_DIR, "eeee5555")

    def test_only_meaningful_unrecorded_sessions(self):
        ids = [p.session for p in digest.pending(self.notes, env={})]
        self.assertEqual(ids, ["aaaa1111"])                # sealed, small, private, skipped out
        self.assertEqual(digest.pending(self.notes, env={"CLAUDE_CODE_SESSION_ID": "aaaa1111"}), [])

    def test_mesh_leaves_skipped_sessions_out(self):
        ids = [m[1] for m in mesh.check(self.notes).missing_outcome]
        self.assertNotIn("eeee5555", ids)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": ""}):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def test_me_tells_the_agent_to_delegate(self):
        code, out = self.run_cli("me")
        self.assertIn("PENDING: 1 session", out)
        self.assertIn("aaaa1111", out)
        self.assertIn("subagent", out)

    def test_pending_and_skip_commands(self):
        code, out = self.run_cli("pending")
        self.assertIn("claude aaaa1111", out)
        code, out = self.run_cli("pending", "--skip", "aaaa1111")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("pending")
        self.assertIn("No session", out)
        code, out = self.run_cli("me")
        self.assertNotIn("PENDING", out)


class DetailsTest(VaultCase):
    BODY = "Yapıldı\nKarar\nSonraki adım\n## Details\n- Neden A seçildi\n- app.py değişti"

    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")

    def note(self, sid=SID):
        path = sessions.find(self.notes, sid)
        return frontmatter.parse(path.read_text(encoding="utf-8"))

    def test_details_go_inside_the_block_after_the_outcome(self):
        seal.seal(self.notes, "claude", self.BODY, ["home"], session_id=SID, now=NOW, machine="M",
                  summarizer="subagent")
        meta, body = self.note()
        self.assertEqual(meta["summarizer"], "subagent")
        self.assertIn("## Outcome\n- Yapıldı", body)
        self.assertIn("### Details\n- Neden A seçildi\n- app.py değişti", body)
        self.assertLess(body.index("Related:"), body.index("### Details"))
        self.assertEqual(mesh.check(self.notes).outcome_problems, [])

    def test_too_many_detail_lines(self):
        body = "a\nb\nc\n## Details\n" + "\n".join(f"- {i}" for i in range(seal.DETAIL_LINES + 1))
        with self.assertRaises(ValueError):
            seal.seal(self.notes, "claude", body, ["home"], session_id=SID, now=NOW)

    def test_subagent_never_overwrites_the_agents_own_outcome(self):
        seal.seal(self.notes, "claude", "kendi\nözetim\nbu", ["home"], session_id=SID, now=NOW)
        with self.assertRaises(ValueError):
            seal.seal(self.notes, "claude", self.BODY, ["home"], session_id=SID, now=NOW,
                      summarizer="subagent")
        self.assertIn("kendi", self.note()[1])

    def test_agent_replaces_a_subagent_outcome(self):
        seal.seal(self.notes, "claude", self.BODY, ["home"], session_id=SID, now=NOW,
                  summarizer="subagent")
        seal.seal(self.notes, "claude", "yeni\nözet\nburada", ["home"], session_id=SID, now=NOW)
        meta, body = self.note()
        self.assertEqual(meta["summarizer"], "agent")
        self.assertNotIn("### Details", body)

    def test_no_folder_tag_when_working_in_the_vault(self):
        seal.seal(self.notes, "claude", "a\nb\nc", ["home"], session_id=SID, now=NOW,
                  cwd=str(self.notes))
        self.assertEqual(self.note()[0]["tags"], ["session", "client/claude"])
        seal.seal(self.notes, "claude", "a\nb\nc", ["home"], session_id="x2222222", now=NOW,
                  cwd="C:/projects/layercraft")
        self.assertIn("layercraft", self.note("x2222222")[0]["tags"])


class ReminderTest(unittest.TestCase):
    def test_reminder_hands_the_summary_to_a_subagent(self):
        text = hook.reminder_text("claude", SID)
        self.assertIn("subagent", text)
        self.assertIn(f"digest --client claude --session {SID}", text)
        self.assertIn("--summarizer subagent", text)
        self.assertIn(f"seal --client claude --session {SID} --private", text)


if __name__ == "__main__":
    unittest.main()
