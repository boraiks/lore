import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from lorelib import hook, sessionlog
from tests.fixtures import claude_transcript
from tests.helpers import VaultCase

CFG = {"remind_min_messages": 10, "private_dirs": [], "allowed_roots": ["/"]}


class HookCase(VaultCase):
    def setUp(self):
        super().setUp()
        self.root = self.notes.parent
        self.log = self.root / "lore.log"
        self.sessions_log = self.root / "sessions.jsonl"
        self.state = self.root / "state"
        self.t = self.root / "t.jsonl"
        self.cfg = dict(CFG)

    def run_hook(self, data, client="claude", raw=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = hook.run(client, io.StringIO(raw if raw is not None else json.dumps(data)),
                            log_path=self.log, notes_dir=self.notes, state_dir=self.state,
                            cfg=self.cfg, session_log=self.sessions_log)
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        return out.getvalue()

    def payload(self, **kw):
        data = {"session_id": "abc-1", "transcript_path": str(self.t), "cwd": "/x",
                "hook_event_name": "Stop"}
        data.update(kw)
        return data

    def records(self):
        return sessionlog.read(self.sessions_log)

    def all_logs(self):
        return "".join(p.read_text(encoding="utf-8") for p in (self.log, self.sessions_log)
                       if p.exists())


class HookTest(HookCase):
    def test_writes_no_note_only_a_session_record(self):
        claude_transcript(self.t, ["Gizli proje planı", "devam"], ["Plan şu", "tamam"], tools=2)
        self.assertEqual(self.run_hook(self.payload()), "")
        self.assertFalse(self.notes.exists(), "hook must not create anything under notes/")
        (rec,) = self.records().values()
        self.assertEqual((rec["client"], rec["session"], rec["messages"]), ("claude", "abc-1", 8))
        self.assertTrue(rec["first"] and rec["last"])

    def test_logs_hold_no_content(self):
        claude_transcript(self.t, ["Gizli proje planı"], ["Plan şu"], tools=1)
        self.run_hook(self.payload())
        text = self.all_logs()
        for leak in ("Gizli proje", "Plan şu", str(self.t), "/x"):
            self.assertNotIn(leak, text)

    def test_repeated_stops_update_one_record(self):
        claude_transcript(self.t, ["bir"], ["iki"])
        self.run_hook(self.payload())
        claude_transcript(self.t, ["bir", "üç"], ["iki", "dört"])
        self.run_hook(self.payload(hook_event_name="SessionEnd"))
        (rec,) = self.records().values()
        self.assertEqual(rec["messages"], 4)

    def test_bad_json_exits_zero_and_logs(self):
        self.assertEqual(self.run_hook(None, raw="{bozuk"), "")
        self.assertEqual(self.records(), {})
        self.assertIn("bad-input", self.log.read_text(encoding="utf-8"))

    def test_missing_transcript_logged(self):
        self.run_hook(self.payload(transcript_path=str(self.t) + ".yok"))
        self.assertEqual(self.records(), {})
        self.assertIn("no-transcript", self.log.read_text(encoding="utf-8"))

    def test_rejects_odd_session_id(self):
        claude_transcript(self.t, ["bir"], ["iki"])
        self.run_hook(self.payload(session_id="../../etc"))
        self.assertEqual(self.records(), {})

    def test_unknown_client(self):
        claude_transcript(self.t, ["bir"], ["iki"])
        self.run_hook(self.payload(), client="vim")
        self.assertEqual(self.records(), {})


class PrivacyTest(HookCase):
    def setUp(self):
        super().setUp()
        claude_transcript(self.t, ["bir", "iki"], ["a", "b"], tools=4)

    def test_private_session_leaves_no_trace(self):
        from lorelib import seal
        seal.mark_private(self.state, "abc-1")
        self.assertEqual(self.run_hook(self.payload()), "")
        self.assertEqual(self.records(), {})

    def test_private_dir_leaves_no_trace(self):
        self.cfg["private_dirs"] = ["/x"]
        self.assertEqual(self.run_hook(self.payload()), "")
        self.assertEqual(self.records(), {})

    def test_out_of_scope_writes_no_log_at_all(self):
        self.cfg["allowed_roots"] = [str(self.root / "baska")]
        self.assertEqual(self.run_hook(self.payload()), "")
        self.assertEqual(self.all_logs(), "")


class ReminderTest(HookCase):
    def setUp(self):
        super().setUp()
        from lorelib import vault
        vault.seed(self.notes)

    def stop(self, event="Stop", client="claude", **kw):
        text = self.run_hook(self.payload(session_id="sess-1", cwd="/p", hook_event_name=event, **kw),
                             client=client)
        return json.loads(text) if text else None

    def long_session(self):
        claude_transcript(self.t, ["staj notlarını düzenle", "devam"], ["tamam", "bitti"], tools=4)

    def test_no_reminder_below_threshold(self):
        claude_transcript(self.t, ["selam"], ["merhaba"])
        self.assertIsNone(self.stop())

    def test_reminds_exactly_once(self):
        self.long_session()
        first = self.stop()
        self.assertEqual(first["decision"], "block")
        self.assertIn("seal", first["reason"])
        self.assertIn("sess-1", first["reason"])
        self.assertIsNone(self.stop())
        self.assertIsNone(self.stop(stop_hook_active=True))

    def test_continuation_never_reminds(self):
        self.long_session()
        self.assertIsNone(self.stop(stop_hook_active=True))

    def test_session_end_never_reminds(self):
        self.long_session()
        self.assertIsNone(self.stop(event="SessionEnd"))

    def test_outcome_stops_reminder(self):
        from lorelib import seal
        self.long_session()
        seal.seal(self.notes, "claude", "Yapılan: a\nKarar: b\nSonraki: c", ["sessions/sessions"],
                  session_id="sess-1", topic="t", state_dir=self.state, cfg=self.cfg, env={})
        self.assertIsNone(self.stop())

    def test_private_session_no_reminder(self):
        from lorelib import seal
        self.long_session()
        seal.mark_private(self.state, "sess-1")
        self.assertIsNone(self.stop())

    def test_private_dir_no_reminder(self):
        self.long_session()
        self.cfg["private_dirs"] = ["/p"]
        self.assertIsNone(self.stop())

    def test_threshold_is_configurable(self):
        claude_transcript(self.t, ["kısa iş"], ["tamam"], tools=1)
        self.cfg["remind_min_messages"] = 3
        self.assertIsNotNone(self.stop())

    def test_codex_reminder_format(self):
        self.long_session()
        self.assertEqual(self.stop(client="codex")["decision"], "block")

    def test_reminder_keeps_the_rules(self):
        self.long_session()
        reason = self.stop()["reason"]
        self.assertIn("before your final answer", reason)
        self.assertIn("does not want it recorded", reason)
        self.assertIn("in the user's language", reason)


if __name__ == "__main__":
    unittest.main()
