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

    def test_home_stops_at_a_vault_inside_the_folder(self):
        # Obsidian's "Create new vault" in an existing folder makes <folder>/<name>/.obsidian
        outer = self.notes.parent / "kasa"
        (outer / "kasa" / ".obsidian").mkdir(parents=True)
        code, out = self.run_cli("home", str(outer))
        self.assertNotEqual(code, 0)
        self.assertIn("STOP", out)
        self.assertIn((outer / "kasa").as_posix(), out)
        self.assertFalse((outer / "home.md").exists())  # nothing was set up
        code, out = self.run_cli("home", str(outer), "--this-folder")
        self.assertEqual(code, 0, out)
        self.assertTrue((outer / "home.md").exists())

    def test_home_stops_inside_another_vault(self):
        outer = self.notes.parent / "buyuk"
        (outer / ".obsidian").mkdir(parents=True)
        code, out = self.run_cli("home", str(outer / "alt"))
        self.assertNotEqual(code, 0)
        self.assertIn(outer.as_posix(), out)

    def graph_vault(self, graph_tab=True):
        """A vault Obsidian made: blank colour groups, and maybe a graph tab in its workspace."""
        target = self.notes.parent / "kasa"
        (target / ".obsidian").mkdir(parents=True)
        (target / ".obsidian" / "graph.json").write_text('{"colorGroups": []}', encoding="utf-8")
        leaf = "graph" if graph_tab else "markdown"
        (target / ".obsidian" / "workspace.json").write_text(
            '{"main": {"children": [{"type": "leaf", "state": {"type": "%s", "state": {}}}]}}'
            % leaf, encoding="utf-8")
        return target

    def test_colours_held_while_obsidian_shows_a_graph_tab(self):
        # The open tab keeps its own copy of the settings and writes it over graph.json on the
        # next zoom or change, so colours written now would vanish (seen in Obsidian 1.15).
        target = self.graph_vault()
        self.obsidian_running.return_value = True
        code, out = self.run_cli("home", str(target))
        self.assertEqual(code, 0, out)
        self.assertIn("HELD: .obsidian/graph.json", out)
        self.assertIn("close Obsidian", out)
        self.assertNotIn("FILLED: .obsidian/graph.json", out)
        self.assertEqual(read_json(target / ".obsidian" / "graph.json"), {"colorGroups": []})
        self.assertTrue((target / ".obsidian" / "app.json").exists())  # the rest is set up

    def test_colours_filled_when_obsidian_is_closed(self):
        # A graph tab restored on the next start reads graph.json afresh: safe to fill.
        target = self.graph_vault()
        self.assertTrue(vault.graph_tab_open(target))
        code, out = self.run_cli("home", str(target))
        self.assertIn("FILLED: .obsidian/graph.json", out)
        self.assertNotIn("NOTE: could not tell", out)
        self.assertTrue(read_json(target / ".obsidian" / "graph.json")["colorGroups"])

    def test_colours_filled_while_obsidian_runs_without_a_graph_tab(self):
        # Obsidian reloads graph.json when it changes; a graph opened later gets the colours.
        target = self.graph_vault(graph_tab=False)
        self.obsidian_running.return_value = True
        code, out = self.run_cli("home", str(target))
        self.assertIn("FILLED: .obsidian/graph.json", out)
        self.assertNotIn("HELD", out)

    def test_colours_filled_with_a_note_when_obsidian_cannot_be_checked(self):
        target = self.graph_vault()
        self.obsidian_running.return_value = None
        code, out = self.run_cli("home", str(target))
        self.assertIn("FILLED: .obsidian/graph.json", out)
        self.assertIn("NOTE: could not tell whether Obsidian is open", out)

    def test_no_process_check_once_colours_are_set(self):
        target = self.graph_vault()
        vault.obsidian_starter(target)
        self.obsidian_running.reset_mock()
        self.obsidian_running.return_value = True
        self.assertEqual(vault.obsidian_starter(target), [])
        self.obsidian_running.assert_not_called()

    def test_no_note_without_a_graph_tab(self):
        target = self.notes.parent / "kasa"
        (target / ".obsidian").mkdir(parents=True)
        (target / ".obsidian" / "workspace.json").write_text("{bozuk", encoding="utf-8")
        self.assertFalse(vault.graph_tab_open(target))
        self.obsidian_running.return_value = True
        code, out = self.run_cli("home", str(target))
        self.assertIn("CREATED: .obsidian/graph.json", out)
        self.assertNotIn("NOTE: could not tell", out)
        self.assertNotIn("HELD", out)

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


class ObsidianRunningTest(unittest.TestCase):
    """Telling whether Obsidian runs, from the process list."""

    def check(self, name, returncode=0, stdout="", error=None):
        done = mock.Mock(returncode=returncode, stdout=stdout)
        with mock.patch("lorelib.vault.os.name", name), \
                mock.patch("lorelib.vault.subprocess.run", return_value=done,
                           side_effect=error) as run:
            return vault.obsidian_running(), run.call_args

    def test_windows(self):
        found, call = self.check("nt", stdout="Obsidian.exe   25424 Console   2   107,036 K")
        self.assertTrue(found)
        self.assertEqual(call.args[0][0], "tasklist")
        self.assertFalse(self.check("nt", stdout="INFO: No tasks are running.")[0])
        self.assertIsNone(self.check("nt", returncode=1)[0])

    def test_macos_and_linux(self):
        found, call = self.check("posix", returncode=0)
        self.assertTrue(found)
        self.assertEqual(call.args[0][0], "pgrep")
        self.assertFalse(self.check("posix", returncode=1)[0])
        self.assertIsNone(self.check("posix", returncode=2)[0])

    def test_no_process_tool(self):
        self.assertIsNone(self.check("posix", error=FileNotFoundError())[0])


if __name__ == "__main__":
    unittest.main()
