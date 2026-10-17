import io
import json
import unittest
from contextlib import redirect_stdout

from lorelib import cli, config, hook, sessionlog, vault
from tests.fixtures import antigravity_transcript, claude_transcript
from tests.helpers import VaultCase


class InScopeTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.other = self.notes.parent / "baska-proje"
        self.other.mkdir()
        self.cfg = config.load()

    def test_repo_is_always_in_scope(self):
        self.assertTrue(config.in_scope(str(vault.REPO), self.cfg))
        self.assertTrue(config.in_scope(str(vault.REPO / "lorelib"), self.cfg))

    def test_other_folders_are_out_by_default(self):
        self.assertFalse(config.in_scope(str(self.other), self.cfg))
        self.assertFalse(config.in_scope("", self.cfg))

    def test_allowed_root_and_children(self):
        self.cfg["allowed_roots"] = [str(self.other)]
        self.assertTrue(config.in_scope(str(self.other), self.cfg))
        self.assertTrue(config.in_scope(str(self.other / "alt" / "klasor"), self.cfg))
        self.assertFalse(config.in_scope(str(self.other) + "-ikiz", self.cfg))

    def test_config_file_value(self):
        config.CONFIG_PATH.write_text(json.dumps({"allowed_roots": [str(self.other), 5]}),
                                      encoding="utf-8")
        self.assertEqual(config.load()["allowed_roots"], [str(self.other)])


class HookScopeTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.root = self.notes.parent
        self.log = self.root / "lore.log"
        self.inside = self.root / "izinli"
        self.outside = self.root / "izinsiz"
        self.inside.mkdir()
        self.outside.mkdir()
        self.cfg = {"remind_min_messages": 1, "private_dirs": [], "allowed_roots": [str(self.inside)]}
        self.sessions_log = self.root / "sessions.jsonl"

    def run_hook(self, client, data):
        out = io.StringIO()
        with redirect_stdout(out):
            code = hook.run(client, io.StringIO(json.dumps(data)), log_path=self.log,
                            notes_dir=self.notes, state_dir=self.root / "state", cfg=self.cfg,
                            session_log=self.sessions_log)
        self.assertEqual(code, 0)
        return out.getvalue()

    def claude(self, cwd):
        t = claude_transcript(self.root / "c.jsonl", ["bir", "iki"], ["a", "b"], tools=3)
        return {"session_id": "sess-1", "transcript_path": str(t), "cwd": str(cwd),
                "hook_event_name": "Stop"}

    def antigravity(self, cwd):
        t = self.root / "brain" / "cid-1" / ".system_generated" / "logs" / "transcript.jsonl"
        antigravity_transcript(t, ["bir", "iki"], ["a", "b"], tools=3)
        return {"conversationId": "cid-1", "transcriptPath": str(t), "workspacePaths": [str(cwd)],
                "fullyIdle": True, "terminationReason": "model_stop", "error": ""}

    def test_out_of_scope_is_silent(self):
        for client, data in (("claude", self.claude(self.outside)),
                             ("antigravity", self.antigravity(self.outside))):
            self.assertEqual(self.run_hook(client, data), "")  # no reminder either
        # Out of scope leaves no trace at all: no note, no session record, not even a log line.
        self.assertFalse(self.log.exists())
        self.assertFalse(self.sessions_log.exists())
        self.assertFalse(self.notes.exists())

    def test_missing_cwd_is_out_of_scope(self):
        data = self.claude(self.inside)
        del data["cwd"]
        self.run_hook("claude", data)
        self.assertEqual(sessionlog.read(self.sessions_log), {})

    def test_in_scope_works(self):
        self.run_hook("claude", self.claude(self.inside / "alt"))
        self.run_hook("antigravity", self.antigravity(self.inside))
        self.assertEqual(len(sessionlog.read(self.sessions_log)), 2)
        self.assertFalse((self.notes / "sessions").exists())


class ScopeCommandTest(VaultCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def stored(self):
        return json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))

    def test_add_list_remove(self):
        target = self.notes.parent / "proje"
        target.mkdir()
        config.CONFIG_PATH.write_text(json.dumps({"remind_min_messages": 7}), encoding="utf-8")
        self.assertEqual(self.run_cli("scope", "add", str(target))[0], 0)
        self.assertEqual(self.run_cli("scope", "add", str(target / "."))[0], 0)  # no duplicate
        data = self.stored()
        self.assertEqual(len(data["allowed_roots"]), 1)
        self.assertEqual(data["remind_min_messages"], 7)  # other settings kept
        code, out = self.run_cli("scope", "list")
        self.assertEqual(code, 0)
        self.assertIn("proje", out)
        self.assertIn(vault.REPO.as_posix(), out)
        self.assertEqual(self.run_cli("scope", "remove", str(target))[0], 0)
        self.assertEqual(self.stored()["allowed_roots"], [])
        self.assertNotEqual(self.run_cli("scope", "remove", str(target))[0], 0)

    def test_broken_config_is_not_overwritten(self):
        config.CONFIG_PATH.write_text("{bozuk", encoding="utf-8")
        code, out = self.run_cli("scope", "add", str(self.notes.parent))
        self.assertNotEqual(code, 0)
        self.assertEqual(config.CONFIG_PATH.read_text(encoding="utf-8"), "{bozuk")

    def test_missing_folder_is_refused(self):
        code, _ = self.run_cli("scope", "add", str(self.notes.parent / "yok"))
        self.assertNotEqual(code, 0)
        self.assertFalse(config.CONFIG_PATH.exists())


if __name__ == "__main__":
    unittest.main()
