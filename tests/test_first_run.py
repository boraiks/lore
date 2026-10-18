"""The first run in a vault Obsidian already made: its settings, its Welcome note, the intro."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from lorelib import cli, vault
from tests.helpers import VaultCase

# What Obsidian writes into a vault it has just created.
OBSIDIAN_WELCOME = """This is your new *vault*.

Make a note of something, [[create a link]], or try [the Importer](obsidian://show-plugin?id=obsidian-importer)!

When you're ready, delete this note and make the vault your own.
"""
OBSIDIAN_GRAPH = {"collapse-filter": True, "search": "", "showTags": False,
                  "colorGroups": [], "scale": 1}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ObsidianMadeVaultTest(VaultCase):
    """Obsidian creates app.json ({}) and graph.json before lore runs."""

    def setUp(self):
        super().setUp()
        self.put(".obsidian/app.json", "{}")
        self.put(".obsidian/graph.json", json.dumps(OBSIDIAN_GRAPH))

    def test_blank_settings_are_filled(self):
        changes = dict((p.relative_to(self.notes).as_posix(), a)
                       for p, a in vault.obsidian_starter(self.notes))
        self.assertEqual(changes[".obsidian/app.json"], "filled")
        self.assertEqual(changes[".obsidian/graph.json"], "filled")
        app = read_json(self.notes / ".obsidian" / "app.json")
        self.assertEqual(set(app["userIgnoreFilters"]),
                         {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "_templates/"})
        graph = read_json(self.notes / ".obsidian" / "graph.json")
        self.assertIn("path:inbox", {g["query"] for g in graph["colorGroups"]})
        self.assertEqual(graph["scale"], 1)          # Obsidian's own keys stay
        self.assertFalse(graph["showTags"])          # tags are not needed; left as they were

    def test_second_run_changes_nothing(self):
        vault.obsidian_starter(self.notes)
        before = (self.notes / ".obsidian" / "graph.json").read_text(encoding="utf-8")
        self.assertEqual(vault.obsidian_starter(self.notes), [])
        self.assertEqual((self.notes / ".obsidian" / "graph.json").read_text(encoding="utf-8"),
                         before)

    def test_user_choices_are_kept(self):
        mine = {"userIgnoreFilters": ["drafts/"]}
        self.put(".obsidian/app.json", json.dumps(mine))
        groups = {**OBSIDIAN_GRAPH, "colorGroups": [{"query": "tag:#x", "color": {"a": 1, "rgb": 1}}]}
        self.put(".obsidian/graph.json", json.dumps(groups))
        changed = {p.name for p, _ in vault.obsidian_starter(self.notes)}
        self.assertNotIn("app.json", changed)
        self.assertNotIn("graph.json", changed)
        self.assertEqual(read_json(self.notes / ".obsidian" / "app.json"), mine)
        self.assertEqual(read_json(self.notes / ".obsidian" / "graph.json"), groups)

    def test_broken_json_is_left_alone(self):
        self.put(".obsidian/app.json", "{bozuk")
        vault.obsidian_starter(self.notes)
        self.assertEqual((self.notes / ".obsidian" / "app.json").read_text(encoding="utf-8"),
                         "{bozuk")


class WelcomeTest(VaultCase):
    def test_untouched_welcome_is_found(self):
        self.put("Welcome.md", OBSIDIAN_WELCOME)
        self.assertEqual(vault.obsidian_welcome(self.notes), self.notes / "Welcome.md")

    def test_edited_welcome_is_a_note(self):
        self.put("Welcome.md", OBSIDIAN_WELCOME + "\nMy own line.\n")
        self.assertIsNone(vault.obsidian_welcome(self.notes))

    def test_remove_moves_it_to_obsidian_trash(self):
        self.put("Welcome.md", OBSIDIAN_WELCOME)
        dest = vault.remove_welcome(self.notes)
        self.assertFalse((self.notes / "Welcome.md").exists())
        self.assertEqual(dest, self.notes / ".trash" / "Welcome.md")
        self.assertEqual(dest.read_text(encoding="utf-8"), OBSIDIAN_WELCOME)

    def test_remove_refuses_an_edited_note(self):
        self.put("Welcome.md", "benim notum")
        with self.assertRaises(ValueError):
            vault.remove_welcome(self.notes)
        self.assertTrue((self.notes / "Welcome.md").exists())


class IntroTest(VaultCase):
    def test_seeded_me_is_blank_until_answered(self):
        vault.seed(self.notes)
        self.assertTrue(vault.me_is_blank(self.notes))
        vault.set_me(self.notes, "## What I use this memory for\nDers notları")
        self.assertFalse(vault.me_is_blank(self.notes))

    def test_skip_is_remembered(self):
        vault.seed(self.notes)
        vault.skip_intro(self.notes)
        self.assertFalse(vault.me_is_blank(self.notes))
        self.assertIn("## How I like answers", (self.notes / "me.md").read_text(encoding="utf-8"))


class FirstRunCommandsTest(VaultCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"LORE_HOME": ""}), \
                mock.patch("lorelib.skills.sync", return_value=[]):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_home_lists_the_next_steps(self):
        target = self.notes.parent / "kasa"
        (target / ".obsidian").mkdir(parents=True)
        (target / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
        (target / "Welcome.md").write_text(OBSIDIAN_WELCOME, encoding="utf-8")
        code, out = self.run_cli("home", str(target))
        self.assertEqual(code, 0, out)
        self.assertIn("FILLED: .obsidian/app.json", out)
        self.assertIn("NEXT: ask the intro questions", out)
        self.assertIn("lore.py welcome --remove", out)
        self.assertTrue((target / "Welcome.md").exists())  # only removed after the user's yes

    def test_me_prints_the_questions_while_blank(self):
        vault.seed(self.notes)
        code, out = self.run_cli_vault("me")
        self.assertEqual(code, 0)
        for q in vault.INTRO_QUESTIONS:
            self.assertIn(q, out)
        code, out = self.run_cli_vault("me", "--skip")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli_vault("me")
        self.assertNotIn(vault.INTRO_QUESTIONS[0], out)

    def test_welcome_command(self):
        self.put("Welcome.md", OBSIDIAN_WELCOME)
        code, out = self.run_cli_vault("welcome")
        self.assertIn("untouched", out)
        self.assertTrue((self.notes / "Welcome.md").exists())
        code, out = self.run_cli_vault("welcome", "--remove")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.notes / "Welcome.md").exists())
        code, out = self.run_cli_vault("welcome", "--remove")
        self.assertNotEqual(code, 0)

    def run_cli_vault(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()


if __name__ == "__main__":
    unittest.main()
