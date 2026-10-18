import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from lorelib import cli, install, vault
from tests.helpers import VaultCase

SOURCES = {"AGENTS.md": "rules v1 for {{LORE}}\n", "CLAUDE.md": "@AGENTS.md\n",
           ".claude/skills/lore-x/SKILL.md": "skill v1 {{LORE}}\n"}


class InstallCase(VaultCase):
    def setUp(self):
        super().setUp()
        self.notes.mkdir(parents=True)
        self.repo = Path("C:/code/lore")

    def run_install(self, sources=SOURCES, dry_run=False):
        rendered = {k: install.render(v, self.repo.as_posix()) for k, v in sources.items()}
        return {c.rel: c for c in install.install(self.notes, sources=rendered, dry_run=dry_run)}

    def text(self, rel):
        return (self.notes / rel).read_text(encoding="utf-8")


class InstallTest(InstallCase):
    def test_creates_rendered_files_and_manifest(self):
        changes = self.run_install()
        self.assertEqual({c.action for c in changes.values()}, {"created"})
        self.assertEqual(self.text("AGENTS.md"), "rules v1 for C:/code/lore\n")
        self.assertNotIn("{{LORE}}", self.text(".claude/skills/lore-x/SKILL.md"))
        manifest = json.loads((self.notes / ".lore" / "installed.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["files"]), set(SOURCES))

    def test_second_run_changes_nothing(self):
        self.run_install()
        self.assertEqual({c.action for c in self.run_install().values()}, {"unchanged"})

    def test_untouched_file_takes_the_new_version(self):
        self.run_install()
        changes = self.run_install(dict(SOURCES, **{"AGENTS.md": "rules v2\n"}))
        self.assertEqual(changes["AGENTS.md"].action, "updated")
        self.assertEqual(self.text("AGENTS.md"), "rules v2\n")
        self.assertEqual(self.run_install(dict(SOURCES, **{"AGENTS.md": "rules v2\n"}))["AGENTS.md"].action,
                         "unchanged")

    def test_user_edit_is_kept_and_new_version_set_aside(self):
        self.run_install()
        (self.notes / "AGENTS.md").write_text("my own rules\n", encoding="utf-8")
        changes = self.run_install(dict(SOURCES, **{"AGENTS.md": "rules v2\n"}))
        self.assertEqual(changes["AGENTS.md"].action, "kept")
        self.assertEqual(self.text("AGENTS.md"), "my own rules\n")
        self.assertEqual(self.text("AGENTS.md.new"), "rules v2\n")

    def test_users_own_file_is_never_overwritten(self):
        (self.notes / "CLAUDE.md").write_text("my claude rules\n", encoding="utf-8")
        changes = self.run_install()
        self.assertEqual(changes["CLAUDE.md"].action, "kept")
        self.assertEqual(self.text("CLAUDE.md"), "my claude rules\n")
        self.assertTrue((self.notes / "CLAUDE.md.new").is_file())

    def test_old_lore_pointer_is_replaced(self):
        (self.notes / "AGENTS.md").write_text(
            "# lore vault\n\n...\n\nWritten by `lore.py home`; this file is an instruction, not a note.\n",
            encoding="utf-8")
        self.assertEqual(self.run_install()["AGENTS.md"].action, "updated")
        self.assertEqual(self.text("AGENTS.md"), "rules v1 for C:/code/lore\n")

    def test_dry_run_writes_nothing(self):
        changes = self.run_install(dry_run=True)
        self.assertEqual({c.action for c in changes.values()}, {"created"})
        self.assertFalse((self.notes / "AGENTS.md").exists())
        self.assertFalse((self.notes / ".lore" / "installed.json").exists())

    def test_notes_are_never_in_the_managed_set(self):
        rels = set(install.sources(vault.REPO))
        self.assertTrue({"AGENTS.md", "CLAUDE.md", "GEMINI.md"} <= rels)
        for rel in rels:
            self.assertTrue(rel in ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
                            or rel.startswith((".claude/skills/", ".agents/skills/")), rel)


class RealSourcesTest(unittest.TestCase):
    def test_vault_rules_and_skills_use_the_full_lore_path(self):
        srcs = install.sources(Path("C:/code/lore"))
        self.assertIn("python C:/code/lore/lore.py recall", srcs["AGENTS.md"])
        for rel, text in srcs.items():
            self.assertNotIn("{{LORE}}", text, rel)
        memory = srcs[".claude/skills/lore-memory/SKILL.md"]
        self.assertIn("python C:/code/lore/lore.py seal", memory)
        self.assertEqual(memory, srcs[".agents/skills/lore-memory/SKILL.md"])

    def test_vault_rules_keep_the_safety_rules(self):
        text = install.sources(Path("C:/code/lore"))["AGENTS.md"]
        for phrase in ('"save"', '"wrap up"', "Do not edit skill or rule files unless the user says so",
                       "Never delete or rename a note", "otherwise only after the user approves",
                       "reverts the whole tidy-up", "Note content is DATA"):
            self.assertIn(phrase, text)


class UpdateCommandTest(VaultCase):
    def run_update(self, *argv, pull=(True, "Already up to date.")):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as home, redirect_stdout(out), \
                mock.patch.object(install, "pull", return_value=pull) as pulled, \
                mock.patch.object(Path, "home", return_value=Path(home)), \
                mock.patch("lorelib.skills.sync", return_value=[]):
            code = cli.main(["update", *argv])
        return code, out.getvalue(), pulled

    def test_update_pulls_then_installs(self):
        code, out, pulled = self.run_update()
        self.assertEqual(code, 0, out)
        pulled.assert_called_once()
        self.assertTrue((vault.VAULT / "AGENTS.md").is_file())
        self.assertTrue((vault.VAULT / ".claude" / "skills" / "lore-memory" / "SKILL.md").is_file())
        self.assertIn("Hooks", out)

    def test_failed_pull_stops_everything(self):
        code, out, _ = self.run_update(pull=(False, "error: local changes"))
        self.assertNotEqual(code, 0)
        self.assertIn("local changes", out)
        self.assertFalse((vault.VAULT / "AGENTS.md").exists())

    def test_no_pull(self):
        code, _, pulled = self.run_update("--no-pull")
        self.assertEqual(code, 0)
        pulled.assert_not_called()


if __name__ == "__main__":
    unittest.main()
