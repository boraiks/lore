"""Undo for organizing: every applied tag merge and move is journaled (paths and tags only,
never note text), and `undo` reverts the latest organize run."""

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import timedelta

from lorelib import cli, frontmatter, jot, mesh, organize, vault
from tests.helpers import NOW, VaultCase

LATER = NOW + timedelta(minutes=5)


class UndoCase(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")
        vault.add_area(self.notes, "spor", now=NOW, machine="M")
        self.a = self.note("Koşu", ["antrenman", "kas"], body="gizli olmayan ama özel metin")
        self.b = self.note("Salon", ["fitness"])
        self.ref = self.put("spor/liste.md", "---\ntitle: Liste\n---\n[[inbox/kosu|Koşu]] [[spor/spor]]\n")

    def note(self, title, tags, body="metin"):
        return jot.jot(self.notes, "inbox", title, body, tags=tags, client="claude",
                       now=NOW, machine="M")[0]

    def tags(self, path):
        return frontmatter.parse(path.read_text(encoding="utf-8"))[0]["tags"]

    def tidy(self):
        organize.start_run(self.notes, now=NOW)
        organize.merge_tags(self.notes, ["fitness"], "spor", apply=True, now=NOW)
        organize.merge_tags(self.notes, ["antrenman"], "spor", apply=True, keep=True, now=NOW)
        organize.move_notes(self.notes, [self.a, self.b], "spor", apply=True, now=NOW)


class UndoTest(UndoCase):
    def test_undo_reverts_the_whole_run(self):
        before = {p: p.read_text(encoding="utf-8") for p in (self.a, self.b)}
        self.tidy()
        self.assertFalse(self.a.exists())
        result = organize.undo(self.notes, now=LATER)
        self.assertEqual(result.skipped, [])
        self.assertTrue(self.a.exists() and self.b.exists())
        self.assertFalse((self.notes / "spor" / "kosu.md").exists())
        self.assertEqual(self.tags(self.a), ["antrenman", "kas", "client/claude"])
        self.assertEqual(self.tags(self.b), ["fitness", "client/claude"])
        self.assertIn("[[inbox/inbox]]", self.a.read_text(encoding="utf-8"))  # area link back
        self.assertIn("[[inbox/kosu|Koşu]]", self.ref.read_text(encoding="utf-8"))
        self.assertIn("[[spor/spor]]", self.ref.read_text(encoding="utf-8"))   # untouched link
        self.assertEqual(mesh.check(self.notes).broken, [])
        for path, text in before.items():   # only `updated` may differ
            self.assertEqual(frontmatter.split(path.read_text(encoding="utf-8"))[1],
                             frontmatter.split(text)[1])

    def test_second_undo_has_nothing_left(self):
        self.tidy()
        organize.undo(self.notes, now=LATER)
        with self.assertRaises(ValueError):
            organize.undo(self.notes, now=LATER)

    def test_runs_are_undone_one_at_a_time(self):
        organize.start_run(self.notes, now=NOW)
        organize.merge_tags(self.notes, ["fitness"], "spor", apply=True, now=NOW)
        organize.start_run(self.notes, now=LATER)
        organize.merge_tags(self.notes, ["antrenman"], "spor", apply=True, now=LATER)
        organize.undo(self.notes, now=LATER)
        self.assertEqual(self.tags(self.a), ["antrenman", "kas", "client/claude"])
        self.assertEqual(self.tags(self.b), ["spor", "client/claude"])      # older run stays
        organize.undo(self.notes, now=LATER)
        self.assertEqual(self.tags(self.b), ["fitness", "client/claude"])

    def test_a_note_changed_since_is_skipped(self):
        organize.start_run(self.notes, now=NOW)
        organize.merge_tags(self.notes, ["fitness"], "spor", apply=True, now=NOW)
        text = self.b.read_text(encoding="utf-8").replace("  - spor", "  - benim")
        self.b.write_text(text, encoding="utf-8")
        result = organize.undo(self.notes, now=LATER)
        self.assertEqual(result.skipped, ["inbox/salon.md"])
        self.assertEqual(self.tags(self.b), ["benim", "client/claude"])

    def test_a_move_whose_old_place_is_taken_is_skipped(self):
        organize.start_run(self.notes, now=NOW)
        organize.move_notes(self.notes, [self.b], "spor", apply=True, now=NOW)
        self.put("inbox/salon.md", "yeni not")
        result = organize.undo(self.notes, now=LATER)
        self.assertEqual(result.skipped, ["spor/salon.md"])
        self.assertTrue((self.notes / "spor" / "salon.md").exists())
        self.assertEqual((self.notes / "inbox" / "salon.md").read_text(encoding="utf-8"), "yeni not")

    def test_dry_runs_are_not_journaled(self):
        organize.merge_tags(self.notes, ["fitness"], "spor")
        organize.move_notes(self.notes, [self.a], "spor")
        with self.assertRaises(ValueError):
            organize.undo(self.notes)

    def test_journal_holds_paths_and_tags_only(self):
        self.tidy()
        journal = (self.notes / ".lore" / "logs" / "organize.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("özel metin", journal)
        for line in journal.splitlines():
            json.loads(line)

    def test_applies_without_organize_form_their_own_run(self):
        organize.merge_tags(self.notes, ["fitness"], "spor", apply=True, now=NOW)
        organize.merge_tags(self.notes, ["antrenman"], "spor", apply=True, now=NOW + timedelta(hours=3))
        organize.undo(self.notes, now=LATER)
        self.assertEqual(self.tags(self.b), ["spor", "client/claude"])


class UndoCommandTest(UndoCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def test_organize_apply_and_undo(self):
        self.run_cli("organize")
        code, out = self.run_cli("tag", "merge", "fitness", "--into", "spor", "--apply")
        self.assertIn("lore.py undo", out)
        code, out = self.run_cli("move", "inbox/salon.md", "--to", "spor", "--apply")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("undo")
        self.assertEqual(code, 0, out)
        self.assertIn("UNDONE", out)
        self.assertEqual(self.tags(self.b), ["fitness", "client/claude"])
        code, out = self.run_cli("undo")
        self.assertNotEqual(code, 0)
        self.assertIn("Nothing to undo", out)


if __name__ == "__main__":
    unittest.main()
