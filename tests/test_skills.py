import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from lorelib import cli, frontmatter, skills, vault

NAMES = {"lore-memory", "lore-check", "lore-setup"}
DESCRIPTION_MAX = 200
FILE_MAX = 1500


class SourceTest(unittest.TestCase):
    """The single source of the skills, as committed in the repository."""

    def sources(self):
        return {p.parent.name: p for p in skills.SOURCE_DIR.glob("*/SKILL.md")}

    def test_three_grouped_skills(self):
        self.assertEqual(set(self.sources()), NAMES)

    def test_system_commands_are_not_skills(self):
        for path in self.sources().values():
            meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
            self.assertNotIn("flush", meta["name"])
            self.assertNotIn("hook", meta["name"])

    def test_short_and_pointing_to_agents_md(self):
        for name, path in self.sources().items():
            text = path.read_text(encoding="utf-8")
            meta, body = frontmatter.parse(text)
            self.assertEqual(meta["name"], name)
            self.assertTrue(meta["description"])
            self.assertLessEqual(len(meta["description"]), DESCRIPTION_MAX, name)
            self.assertLessEqual(len(text), FILE_MAX, name)
            self.assertIn("AGENTS.md", body, name)

    def test_trigger_phrases(self):
        desc = {n: frontmatter.parse(p.read_text(encoding="utf-8"))[0]["description"]
                for n, p in self.sources().items()}
        for phrase in ("save", "wrap up", "write this to memory", "note this", "do you remember"):
            self.assertIn(phrase, desc["lore-memory"])
        self.assertIn("check the memory", desc["lore-check"])
        self.assertIn("organize the memory", desc["lore-check"])
        for phrase in ("set up the folders", "the hooks"):
            self.assertIn(phrase, desc["lore-setup"])
        for d in desc.values():
            self.assertIn("in any language", d)

    def test_wire_skill_says_dry_run_first(self):
        body = (skills.SOURCE_DIR / "lore-setup" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("dry run", body)


class CommittedCopiesTest(unittest.TestCase):
    def test_client_folders_match_source(self):
        changes = skills.sync(vault.REPO, dry_run=True)
        stale = [c for c in changes if c.action != "unchanged"]
        self.assertEqual(stale, [], "sync with: python lore.py seed")
        for target in skills.TARGETS:
            names = {p.parent.name for p in (vault.REPO / target).glob("*/SKILL.md")}
            self.assertEqual(names, NAMES, target)


class SyncTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        src = self.repo / "skills" / "lore-x"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("---\nname: lore-x\ndescription: d\n---\nbody\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def copies(self):
        return [self.repo / t / "lore-x" / "SKILL.md" for t in skills.TARGETS]

    def test_creates_identical_copies(self):
        actions = {c.action for c in skills.sync(self.repo)}
        self.assertEqual(actions, {"created"})
        source = (self.repo / "skills" / "lore-x" / "SKILL.md").read_bytes()
        for copy in self.copies():
            self.assertEqual(copy.read_bytes(), source)

    def test_idempotent(self):
        skills.sync(self.repo)
        self.assertEqual({c.action for c in skills.sync(self.repo)}, {"unchanged"})

    def test_updates_drifted_copy(self):
        skills.sync(self.repo)
        self.copies()[0].write_text("elle değişti", encoding="utf-8")
        changes = {c.path: c.action for c in skills.sync(self.repo)}
        self.assertEqual(changes[self.copies()[0]], "updated")
        self.assertEqual(changes[self.copies()[1]], "unchanged")

    def test_dry_run_writes_nothing(self):
        changes = skills.sync(self.repo, dry_run=True)
        self.assertEqual({c.action for c in changes}, {"created"})
        self.assertFalse(any(c.exists() for c in self.copies()))

    def test_stale_copy_reported_not_deleted(self):
        old = self.repo / ".agents" / "skills" / "lore-eski" / "SKILL.md"
        old.parent.mkdir(parents=True)
        old.write_text("eski", encoding="utf-8")
        changes = skills.sync(self.repo)
        self.assertIn((old, "stale"), [(c.path, c.action) for c in changes])
        self.assertTrue(old.exists())

    def test_foreign_skills_ignored(self):
        other = self.repo / ".claude" / "skills" / "baska-skill" / "SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("x", encoding="utf-8")
        self.assertNotIn(other, [c.path for c in skills.sync(self.repo)])


class WireDefaultTest(unittest.TestCase):
    def test_wire_without_apply_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(Path, "home", return_value=Path(tmp)), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["wire"]), 0)
            self.assertEqual(list(Path(tmp).rglob("*")), [])
        self.assertIn("Dry run", out.getvalue())


if __name__ == "__main__":
    unittest.main()
