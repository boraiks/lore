"""Organizing the memory: a short inventory for the agent, then tag merges and note moves
that the user approved. Dry run first; nothing is deleted or overwritten."""

import io
import unittest
from contextlib import redirect_stdout

from lorelib import cli, frontmatter, jot, mesh, organize, vault
from tests.helpers import NOW, VaultCase

LATER = NOW.replace(hour=18)


class OrganizeCase(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")
        vault.add_area(self.notes, "spor", now=NOW, machine="M")

    def note(self, area, title, tags, body="metin", links=()):
        return jot.jot(self.notes, area, title, body, tags=tags, client="claude", links=links,
                       now=NOW, machine="M")[0]

    def meta(self, path):
        return frontmatter.parse(path.read_text(encoding="utf-8"))[0]


class InventoryTest(OrganizeCase):
    def test_lists_areas_tags_and_inbox(self):
        self.note("inbox", "Koşu planı", ["antrenman"])
        self.note("inbox", "Salon", ["fitness", "antrenman"])
        self.note("spor", "Maç", ["spor"])
        text = organize.inventory(self.notes)
        self.assertIn("DATA", text)                      # note content is data
        self.assertIn("inbox 2", text)
        self.assertIn("spor 1", text)
        self.assertIn("antrenman 2", text)
        self.assertIn("Koşu planı", text)
        self.assertIn("inbox/kosu-plani.md", text)
        self.assertNotIn("client/claude", text)
        tags_line = next(l for l in text.splitlines() if l.startswith("Tags"))
        self.assertNotIn("area", tags_line)               # area notes' own tags are not topics

    def test_inbox_list_is_capped(self):
        for i in range(35):
            self.note("inbox", f"Not {i}", ["x"])
        text = organize.inventory(self.notes)
        self.assertIn("(+5 more)", text)


class TagMergeTest(OrganizeCase):
    def test_dry_run_changes_nothing(self):
        path = self.note("inbox", "Salon", ["antrenman"])
        before = path.read_text(encoding="utf-8")
        changed = organize.merge_tags(self.notes, ["antrenman"], "spor", now=LATER)
        self.assertEqual(changed, [path])
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_apply_replaces_dedupes_and_keeps_the_rest(self):
        a = self.note("inbox", "Salon", ["antrenman", "kas"], body="Gövde\n\n[[home]]")
        b = self.note("inbox", "Koşu", ["spor", "fitness"])
        body_before = frontmatter.split(a.read_text(encoding="utf-8"))[1]
        organize.merge_tags(self.notes, ["antrenman", "fitness"], "spor", apply=True, now=LATER)
        self.assertEqual(self.meta(a)["tags"], ["spor", "kas", "client/claude"])
        self.assertEqual(self.meta(b)["tags"], ["spor", "client/claude"])
        self.assertEqual(self.meta(a)["updated"], "2026-10-17T18:30")
        self.assertEqual(self.meta(a)["created"], "2026-10-17T10:30")
        self.assertEqual(frontmatter.split(a.read_text(encoding="utf-8"))[1], body_before)

    def test_handwritten_header_is_edited_in_place(self):
        path = self.put("spor/el.md", "---\ntitle: El yazısı\n# benim yorumum\ntags: [Antrenman, koşu]\n"
                                      "kaynak: defter\n---\nMetin [[home]]\n")
        organize.merge_tags(self.notes, ["antrenman"], "spor", apply=True, now=LATER)
        text = path.read_text(encoding="utf-8")
        self.assertIn("# benim yorumum", text)
        self.assertIn("kaynak: defter", text)
        self.assertIn("tags: [spor, koşu]", text)
        self.assertNotIn("updated", text)                 # not added where it was not
        self.assertTrue(text.endswith("Metin [[home]]\n"))

    def test_turkish_spelling_matches(self):
        path = self.note("inbox", "Not", ["çalışma"])
        organize.merge_tags(self.notes, ["calisma"], "ders", apply=True, now=LATER)
        self.assertEqual(self.meta(path)["tags"], ["ders", "client/claude"])

    def test_bad_targets_are_refused(self):
        for into in ("", "client/x", "spor/alt"):
            with self.assertRaises(ValueError):
                organize.merge_tags(self.notes, ["antrenman"], into)
        with self.assertRaises(ValueError):
            organize.merge_tags(self.notes, ["spor"], "spor")


class MoveTest(OrganizeCase):
    def setUp(self):
        super().setUp()
        self.src = self.note("inbox", "Koşu planı", ["antrenman"])   # links to inbox/inbox
        self.other = self.put("spor/liste.md",
                              "---\ntitle: Liste\nupdated: 2026-01-01T00:00\n---\n"
                              "[[inbox/kosu-plani|Koşu]] ve [[kosu-plani]]\n"
                              "```\n[[inbox/kosu-plani]]\n```\n`[[inbox/kosu-plani]]`\n")

    def test_dry_run_moves_nothing(self):
        plan = organize.move_notes(self.notes, [self.src], "spor", now=LATER)
        self.assertEqual(plan.moves, [(self.src, self.notes / "spor" / "kosu-plani.md")])
        self.assertIn((self.other, 1), plan.link_updates)
        self.assertTrue(self.src.exists())

    def test_apply_moves_and_rewrites_path_links(self):
        organize.move_notes(self.notes, ["inbox/kosu-plani.md"], "spor", apply=True, now=LATER)
        dest = self.notes / "spor" / "kosu-plani.md"
        self.assertFalse(self.src.exists())
        self.assertIn("[[spor/spor]]", dest.read_text(encoding="utf-8"))   # area hub follows
        self.assertNotIn("[[inbox/inbox]]", dest.read_text(encoding="utf-8"))
        text = self.other.read_text(encoding="utf-8")
        self.assertIn("[[spor/kosu-plani|Koşu]] ve [[kosu-plani]]", text)
        self.assertIn("```\n[[inbox/kosu-plani]]\n```", text)              # code is left alone
        self.assertIn("`[[inbox/kosu-plani]]`", text)
        self.assertEqual(self.meta(self.other)["updated"], "2026-10-17T18:30")
        report = mesh.check(self.notes)
        self.assertEqual(report.broken, [])

    def test_full_path_and_no_suffix_are_accepted(self):
        organize.move_notes(self.notes, [str(self.src)], "spor", apply=True)
        self.assertTrue((self.notes / "spor" / "kosu-plani.md").exists())
        self.note("inbox", "İkinci", ["x"])
        organize.move_notes(self.notes, ["inbox/ikinci"], "spor", apply=True)
        self.assertTrue((self.notes / "spor" / "ikinci.md").exists())

    def test_existing_destination_stops_everything(self):
        self.put("spor/kosu-plani.md", "benim")
        second = self.note("inbox", "İkinci", ["x"])
        with self.assertRaises(ValueError):
            organize.move_notes(self.notes, [second, self.src], "spor", apply=True)
        self.assertTrue(self.src.exists() and second.exists())
        self.assertEqual((self.notes / "spor" / "kosu-plani.md").read_text(encoding="utf-8"), "benim")

    def test_refused_notes_and_areas(self):
        session = self.put("sessions/s.md", "---\ntype: session\n---\n[[home]]")
        for bad in ("spor/spor.md", "me.md", "home.md", str(session), "../disari.md", "yok.md"):
            with self.assertRaises(ValueError, msg=bad):
                organize.move_notes(self.notes, [bad], "spor")
        with self.assertRaises(ValueError):
            organize.move_notes(self.notes, [self.src], "olmayan-alan")
        with self.assertRaises(ValueError):
            organize.move_notes(self.notes, [self.src], "sessions")


class CommandsTest(OrganizeCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def test_organize_tag_merge_and_move(self):
        path = self.note("inbox", "Salon", ["antrenman"])
        code, out = self.run_cli("organize")
        self.assertEqual(code, 0, out)
        self.assertIn("antrenman 1", out)

        code, out = self.run_cli("tag", "merge", "antrenman", "--into", "spor")
        self.assertEqual(code, 0, out)
        self.assertIn("Dry run", out)
        self.assertEqual(self.meta(path)["tags"], ["antrenman", "client/claude"])
        code, out = self.run_cli("tag", "merge", "antrenman", "--into", "spor", "--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.meta(path)["tags"], ["spor", "client/claude"])

        code, out = self.run_cli("move", "inbox/salon.md", "--to", "spor")
        self.assertIn("Dry run", out)
        self.assertTrue(path.exists())
        code, out = self.run_cli("move", "inbox/salon.md", "--to", "spor", "--apply")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.notes / "spor" / "salon.md").exists())

    def test_errors_exit_non_zero(self):
        code, out = self.run_cli("move", "yok.md", "--to", "spor")
        self.assertNotEqual(code, 0)
        self.assertIn("ERROR", out)


if __name__ == "__main__":
    unittest.main()
