import io
import json
import unittest
from contextlib import redirect_stdout

from lorelib import frontmatter, hook, sessionlog, transcript
from tests.fixtures import antigravity_transcript
from tests.helpers import NOW, VaultCase

CID = "00000000-0000-4000-8000-000000000001"  # made up


class AgCase(VaultCase):
    """Antigravity Stop payloads with the keys Antigravity sends (values are made up)."""

    def setUp(self):
        super().setUp()
        self.root = self.notes.parent
        self.log = self.root / "lore.log"
        self.state = self.root / "state"
        self.ws = self.root / "proje"
        self.ws.mkdir()
        self.t = self.root / "brain" / CID / ".system_generated" / "logs" / "transcript.jsonl"
        self.t.parent.mkdir(parents=True)
        antigravity_transcript(self.t, ["istek"], ["yanıt"], tools=1)
        self.sessions_log = self.root / "sessions.jsonl"
        self.cfg = {"remind_min_messages": 10, "private_dirs": [], "allowed_roots": ["/"]}

    def payload(self, **kw):
        data = {"artifactDirectoryPath": str(self.root / "brain" / CID), "conversationId": CID,
                "error": "", "executionNum": 1, "fullyIdle": True, "modelName": "m",
                "terminationReason": "model_stop", "transcriptPath": str(self.t),
                "workspacePaths": [str(self.ws)]}
        data.update(kw)
        return data

    def run_hook(self, data, raw=None):
        out = io.StringIO()
        with redirect_stdout(out):
            code = hook.run("antigravity", io.StringIO(raw if raw is not None else json.dumps(data)),
                            log_path=self.log, notes_dir=self.notes, state_dir=self.state,
                            cfg=self.cfg, session_log=self.sessions_log)
        self.assertEqual(code, 0)
        return out.getvalue()

    def logged(self):
        return self.log.read_text(encoding="utf-8") if self.log.exists() else ""

    def records(self):
        return sessionlog.read(self.sessions_log)


class InputReaderTest(AgCase):
    def test_maps_fields_to_session_record(self):
        self.assertEqual(self.run_hook(self.payload()), "")
        (rec,) = self.records().values()
        self.assertEqual((rec["client"], rec["session"], rec["messages"]), ("antigravity", CID, 3))
        self.assertFalse(self.notes.exists())

    def test_log_has_key_names_not_values(self):
        self.run_hook(self.payload())
        text = self.logged()
        self.assertIn("conversationId", text)
        self.assertIn("transcriptPath", text)
        self.assertIn("result=recorded", text)
        self.assertNotIn(CID, text)
        self.assertNotIn(str(self.t), text)
        self.assertNotIn(self.ws.name, text)

    def test_file_uris(self):
        self.cfg["allowed_roots"] = [str(self.ws)]  # the workspace URI must resolve to be in scope
        self.run_hook(self.payload(transcriptPath=self.t.as_uri(), workspacePaths=[self.ws.as_uri()]))
        self.assertEqual(len(self.records()), 1)  # the transcript URI resolved too

    def test_missing_conversation_id(self):
        data = self.payload()
        del data["conversationId"]
        self.run_hook(data)
        self.assertEqual(self.records(), {})
        self.assertIn("bad-session", self.logged())

    def test_odd_workspace_paths_do_not_crash(self):
        # No usable folder means the scope cannot be checked: silently out of scope.
        for odd in ("C:/tek-metin", [1, 2], None, []):
            self.assertEqual(self.run_hook(self.payload(workspacePaths=odd)), "")
        self.assertEqual(self.records(), {})
        self.assertEqual(self.logged(), "")  # out of scope: not even a log line

    def test_missing_transcript(self):
        self.run_hook(self.payload(transcriptPath=None))
        self.run_hook(self.payload(transcriptPath=str(self.t) + ".yok"))
        self.assertEqual(self.records(), {})
        self.assertEqual(self.logged().count("no-transcript"), 2)

    def test_broken_input(self):
        self.assertEqual(self.run_hook(None, raw="{bozuk"), "")
        self.assertEqual(self.run_hook(None, raw="[1, 2]"), "")
        self.assertEqual(self.run_hook(None, raw=""), "")
        self.assertEqual(self.records(), {})
        self.assertEqual(self.logged().count("bad-input"), 3)




class TranscriptReaderTest(AgCase):
    def test_prompts_and_last_answer_only(self):
        antigravity_transcript(self.t, ["Ders notlarını düzenle", "Devam et"], ["Düzenledim", "Bitti"],
                               tools=2)
        conv = transcript.read(self.t)
        self.assertEqual(conv.prompts, ["Ders notlarını düzenle", "Devam et"])
        self.assertEqual(conv.last_answer, "Bitti")
        self.assertEqual(conv.answers, 2)  # rows with only tool calls are not answers
        self.assertEqual(conv.tools, 4)
        self.assertEqual(conv.session_id, CID)  # from brain/<conversationId>/...
        self.assertEqual(conv.started, "2026-10-17T08:02:00Z")

    def test_metadata_thinking_and_tool_output_dropped(self):
        antigravity_transcript(self.t, ["istek"], ["yanıt"])
        conv = transcript.read(self.t)
        text = " ".join(conv.prompts) + conv.last_answer
        for hidden in ("gizli/yol", "gizli düşünce", "dosya içeriği", "önceki konuşmalar"):
            self.assertNotIn(hidden, text)

    def test_unknown_rows_skipped(self):
        extra = [{"type": "YENI_BIR_TUR", "source": "MODEL", "step_index": 99, "content": "x"},
                 {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "step_index": 100,
                  "content": "lore hatırlatması"},
                 {"type": "USER_INPUT", "step_index": 101, "content": None},
                 {"type": "PLANNER_RESPONSE", "step_index": 102, "content": 5, "tool_calls": "x"},
                 "bozuk satır {", "[1, 2]"]
        antigravity_transcript(self.t, ["istek"], ["yanıt"], extra=extra)
        conv = transcript.read(self.t)
        self.assertEqual(conv.prompts, ["istek"])
        self.assertEqual(conv.last_answer, "yanıt")

    def test_truncated_request(self):
        rows = [{"type": "USER_INPUT", "source": "USER_EXPLICIT", "step_index": 1,
                 "content": "<USER_REQUEST>\nkesik istek", "truncated_fields": ["content"]},
                {"type": "USER_INPUT", "source": "USER_EXPLICIT", "step_index": 2,
                 "content": "<USER_REQUEST>ikinci</USER_REQUEST>\n<ADDITIONAL_METADATA>\nkesik meta"}]
        self.t.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                          encoding="utf-8")
        self.assertEqual(transcript.read(self.t).prompts, ["kesik istek", "ikinci"])

    def test_request_without_wrapper(self):
        rows = [{"type": "USER_INPUT", "source": "USER_EXPLICIT", "step_index": 1,
                 "content": "düz istek\n<ADDITIONAL_METADATA>meta</ADDITIONAL_METADATA>"}]
        self.t.write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertEqual(transcript.read(self.t).prompts, ["düz istek"])


class AgNoNotesTest(AgCase):
    def test_hook_never_writes_notes_even_when_busy(self):
        for idle in (False, True):
            self.run_hook(self.payload(fullyIdle=idle))
        self.assertFalse(self.notes.exists())
        self.assertEqual(len(self.records()), 1)


class AgReminderTest(AgCase):
    def long(self):
        antigravity_transcript(self.t, ["staj notlarını düzenle", "devam"], ["tamam", "bitti"], tools=3)

    def stop(self, **kw):
        out = self.run_hook(self.payload(**kw))
        return json.loads(out) if out else None

    def test_no_reminder_below_threshold(self):
        antigravity_transcript(self.t, ["selam"], ["merhaba"], tools=0)
        self.assertIsNone(self.stop())

    def test_reminds_once_with_continue(self):
        self.long()
        first = self.stop()
        self.assertEqual(first["decision"], "continue")
        self.assertIn(f"--client antigravity --session {CID}", first["reason"])
        self.assertIn(transcript.REMINDER_TAG, first["reason"])
        self.assertIsNone(self.stop(executionNum=2))  # the continued turn stops again: no loop
        self.assertIsNone(self.stop(executionNum=3))

    def test_never_block_format(self):
        self.long()
        self.assertNotEqual(self.stop()["decision"], "block")

    def test_only_after_a_normal_model_stop(self):
        self.long()
        self.assertIsNone(self.stop(terminationReason="user_cancel"))
        self.assertIsNone(self.stop(terminationReason=""))
        self.assertIsNone(self.stop(error="model hatası"))
        self.assertIsNotNone(self.stop())  # the marker was not spent by the skipped stops

    def test_not_while_busy(self):
        self.long()
        self.assertIsNone(self.stop(fullyIdle=False))

    def test_outcome_stops_reminder(self):
        from lorelib import seal, vault
        self.long()
        vault.seed(self.notes)
        seal.seal(self.notes, "antigravity", "Yapılan: a\nKarar: b\nSonraki: c", ["sessions/sessions"],
                  session_id=CID, state_dir=self.state, cfg=self.cfg, env={})
        self.assertIsNone(self.stop())

    def test_private_session(self):
        from lorelib import seal
        self.long()
        seal.mark_private(self.state, CID)
        self.assertIsNone(self.stop())


class AgSealTest(AgCase):
    BODY = "Yapılan: ders planı\nKarar: haftalık, çünkü düzenli\nSonraki: başla"

    def setUp(self):
        super().setUp()
        from lorelib import vault
        vault.seed(self.notes)
        antigravity_transcript(self.t, ["Ders planı yap"], ["Yaptım"])

    def seal(self, **kw):
        from lorelib import seal
        args = dict(session_id=CID, topic="Ders planı", cwd=str(self.ws), now=NOW, machine="M",
                    state_dir=self.state, cfg=self.cfg, env={}, ag_roots=[self.root])
        args.update(kw)
        return seal.seal(self.notes, "antigravity", self.BODY, ["courses/courses"], **args)

    def session_files(self):
        return sorted((self.notes / "sessions").glob("2*.md"))

    def test_same_conversation_id_updates_in_place(self):
        first = self.seal()
        again = self.seal(topic="Başka konu")
        self.assertEqual((first.action, again.action), ("created", "updated"))
        self.assertEqual(self.session_files(), [first.path])

    def test_without_session_uses_running_conversation(self):
        result = self.seal(session_id=None, now=None)  # the transcript was just written
        self.assertEqual((result.session_id, result.action), (CID, "created"))
        meta, _ = frontmatter.parse(result.path.read_text(encoding="utf-8"))
        self.assertEqual(meta["session"], CID)

    def test_stale_transcript_falls_back_to_topic_day(self):
        import os
        old = self.t.stat().st_mtime - 3600
        os.utime(self.t, (old, old))
        result = self.seal(session_id=None, now=None)
        self.assertTrue(result.session_id.startswith("antigravity-"))
        self.assertNotEqual(result.session_id, CID)


if __name__ == "__main__":
    unittest.main()
