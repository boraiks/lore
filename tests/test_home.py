import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from lorelib import cli, mesh, vault
from tests.helpers import VaultCase


class LocateTest(VaultCase):
    def test_env_wins(self):
        vault.POINTER.write_text(json.dumps({"home": str(self.notes.parent / "a")}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"LORE_HOME": str(self.notes.parent / "b")}):
            path, source = vault.locate()
        self.assertEqual((path.name, source), ("b", "LORE_HOME"))

    def test_pointer_file(self):
        vault.POINTER.write_text(json.dumps({"home": str(self.notes.parent / "a")}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"LORE_HOME": ""}):
            self.assertEqual(vault.locate()[0].name, "a")

    def test_default_is_next_to_the_repo(self):
        with mock.patch.dict(os.environ, {"LORE_HOME": ""}):
            path, _ = vault.locate()
        self.assertEqual(path, vault.REPO.parent / "lore-vault")

    def test_broken_pointer_falls_back(self):
        vault.POINTER.write_text("{bozuk", encoding="utf-8")
        with mock.patch.dict(os.environ, {"LORE_HOME": ""}):
            self.assertEqual(vault.locate()[0], vault.DEFAULT_VAULT)

    def test_set_home_keeps_other_keys(self):
        vault.POINTER.write_text(json.dumps({"baska": 1}), encoding="utf-8")
        vault.set_home(self.notes.parent / "kasa")
        data = json.loads(vault.POINTER.read_text(encoding="utf-8"))
        self.assertEqual(data["baska"], 1)
        self.assertTrue(data["home"].endswith("/kasa"))


class HomeCommandTest(VaultCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"LORE_HOME": ""}), \
                mock.patch("lorelib.skills.sync", return_value=[]):  # keep the real repo untouched
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_sets_up_vault_with_areas_at_root(self):
        target = self.notes.parent / "lore-vault"
        code, out = self.run_cli("home", str(target))
        self.assertEqual(code, 0, out)
        self.assertIn(target.as_posix(), out)
        self.assertTrue((target / "home.md").is_file())
        self.assertTrue((target / "career" / "README.md").is_file())
        self.assertFalse((target / "notes").exists())  # no notes/ subfolder any more
        for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "_templates/lore-note.md",
                     ".obsidian/graph.json"):
            self.assertTrue((target / name).is_file(), name)
        with mock.patch.dict(os.environ, {"LORE_HOME": ""}):
            self.assertEqual(vault.locate()[0], target.resolve())

    def test_show(self):
        code, out = self.run_cli("home")
        self.assertEqual(code, 0)
        self.assertIn("Vault:", out)


class VaultRootTest(VaultCase):
    def test_hidden_state_folder_is_not_notes(self):
        self.put("home.md", "[[career/README]]")
        self.put("career/README.md", "[[home]]")
        self.put(".lore/logs/x.md", "[[kayip]]")
        self.put(".obsidian/y.md", "[[kayip]]")
        report = mesh.check(self.notes)
        self.assertEqual((report.total, report.broken), (2, []))


if __name__ == "__main__":
    unittest.main()
