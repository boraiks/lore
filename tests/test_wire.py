import json
import unittest
from pathlib import Path

from lorelib import wire
from tests.helpers import VaultCase

PY = Path("C:/Python/python.exe")
LORE = Path("C:/Brain/lore.py")


class WireTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.home = self.notes.parent / "home"
        self.claude = self.home / ".claude" / "settings.json"
        self.codex = self.home / ".codex" / "hooks.json"

    def plan(self):
        return wire.plan(self.home, python=PY, lore=LORE)

    def lore_commands(self, path, event):
        data = json.loads(path.read_text(encoding="utf-8"))
        return [h["command"] for g in data["hooks"].get(event, []) for h in g["hooks"]
                if wire.MARKER in h["command"]]

    def test_dry_run_writes_nothing(self):
        changes = self.plan()
        self.assertEqual({c.client for c in changes}, {"claude", "codex", "antigravity"})
        self.assertFalse(self.home.exists())

    def test_apply_creates_both(self):
        wire.apply(self.plan())
        cmd = self.lore_commands(self.claude, "Stop")
        self.assertEqual(cmd, ["C:/Python/python.exe C:/Brain/lore.py hook claude"])
        self.assertEqual(len(self.lore_commands(self.claude, "SessionEnd")), 1)
        self.assertEqual(len(self.lore_commands(self.codex, "Stop")), 1)
        self.assertEqual(len(self.lore_commands(self.codex, "SessionEnd")), 1)
        timeouts = [h["timeout"] for g in json.loads(self.codex.read_text(encoding="utf-8"))
                    ["hooks"]["SessionEnd"] for h in g["hooks"]]
        self.assertLessEqual(max(timeouts), 3)

    def test_preserves_other_settings_and_is_idempotent(self):
        self.claude.parent.mkdir(parents=True)
        other = {"type": "command", "command": "echo baska"}
        self.claude.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [other]}]}}),
                               encoding="utf-8")
        wire.apply(self.plan())
        wire.apply(self.plan())
        data = json.loads(self.claude.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "x")
        self.assertIn(other, [h for g in data["hooks"]["Stop"] for h in g["hooks"]])
        self.assertEqual(len(self.lore_commands(self.claude, "Stop")), 1)
        self.assertTrue(list(self.claude.parent.glob("settings.json.lore-backup-*")))

    def test_second_run_has_no_changes(self):
        wire.apply(self.plan())
        self.assertTrue(all(not c.changed for c in self.plan()))

    def test_stale_path_is_replaced(self):
        wire.apply(wire.plan(self.home, python=PY, lore=Path("D:/eski/lore.py")))
        wire.apply(self.plan())
        self.assertEqual(self.lore_commands(self.claude, "Stop"),
                         ["C:/Python/python.exe C:/Brain/lore.py hook claude"])

    def test_invalid_json_is_not_touched(self):
        self.claude.parent.mkdir(parents=True)
        self.claude.write_text("{bozuk", encoding="utf-8")
        changes = {c.client: c for c in self.plan()}
        self.assertTrue(changes["claude"].error)
        wire.apply(changes.values())
        self.assertEqual(self.claude.read_text(encoding="utf-8"), "{bozuk")

    def test_paths_with_spaces_are_quoted(self):
        changes = wire.plan(self.home, python=Path("C:/Program Files/Py/python.exe"), lore=LORE)
        wire.apply(changes)
        self.assertEqual(self.lore_commands(self.claude, "Stop"),
                         ['"C:/Program Files/Py/python.exe" C:/Brain/lore.py hook claude'])


class AntigravityWireTest(VaultCase):
    OTHER = {"Stop": [{"type": "command", "command": "other Stop", "timeout": 10}]}

    def setUp(self):
        super().setUp()
        self.home = self.notes.parent / "home"
        self.file = self.home / ".gemini" / "config" / "hooks.json"

    def plan(self, lore=LORE):
        return wire.plan(self.home, python=PY, lore=lore, only="antigravity")

    def data(self):
        return json.loads(self.file.read_text(encoding="utf-8"))

    def test_dry_run_default(self):
        (change,) = self.plan()
        self.assertTrue(change.changed)
        self.assertFalse(self.home.exists())

    def test_writes_lore_set_with_flat_stop_list(self):
        wire.apply(self.plan())
        self.assertEqual(self.data(), {"lore": {"Stop": [
            {"type": "command", "command": "C:/Python/python.exe C:/Brain/lore.py hook antigravity Stop",
             "timeout": 10}]}})

    def test_other_sets_untouched_and_idempotent(self):
        self.file.parent.mkdir(parents=True)
        other = {"PreInvocation": [{"type": "command", "command": "x", "timeout": 5}]}
        self.file.write_text(json.dumps({"baska-set": self.OTHER, "baska": other}), encoding="utf-8")
        wire.apply(self.plan())
        data = self.data()
        self.assertEqual(data["baska-set"], self.OTHER)
        self.assertEqual(data["baska"], other)
        self.assertIn("lore", data)
        self.assertTrue(list(self.file.parent.glob("hooks.json.lore-backup-*")))
        (again,) = self.plan()
        self.assertFalse(again.changed)

    def test_stale_lore_set_replaced(self):
        wire.apply(self.plan(lore=Path("D:/eski/lore.py")))
        wire.apply(self.plan())
        self.assertIn("C:/Brain/lore.py", self.data()["lore"]["Stop"][0]["command"])
        self.assertEqual(len(self.data()["lore"]["Stop"]), 1)

    def test_invalid_file_untouched(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text('{"lore": 5', encoding="utf-8")
        (change,) = self.plan()
        self.assertTrue(change.error)
        wire.apply([change])
        self.assertEqual(self.file.read_text(encoding="utf-8"), '{"lore": 5')


if __name__ == "__main__":
    unittest.main()
