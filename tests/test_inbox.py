"""Inbox themes: lore notices when notes about one theme pile up; the user decides."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta

from lorelib import cli, inbox, jot, mesh, vault
from tests.helpers import NOW, VaultCase


class InboxCase(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")

    def note(self, title, tags, days_ago=0):
        return jot.jot(self.notes, "inbox", title, "metin", tags=tags, client="claude",
                       now=NOW - timedelta(days=days_ago), machine="M")[0]


class ThemesTest(InboxCase):
    def test_three_notes_with_one_tag_make_a_theme(self):
        self.note("Koşu 1", ["spor"])
        self.note("Koşu 2", ["spor"])
        self.assertEqual(inbox.themes(self.notes), [])          # two are not enough
        self.note("Koşu 3", ["Spor", "koşu"])
        self.assertEqual([(t.name, t.count) for t in inbox.themes(self.notes)], [("spor", 3)])

    def test_turkish_letters_group_and_name_is_a_valid_area(self):
        for i, tag in enumerate(["çalışma", "calisma", "Çalışma"]):
            self.note(f"Not {i}", [tag])
        (theme,) = inbox.themes(self.notes)
        self.assertEqual((theme.name, theme.count), ("calisma", 3))

    def test_client_generic_and_existing_area_tags_are_ignored(self):
        vault.add_area(self.notes, "career", now=NOW, machine="M")
        for i in range(3):
            self.note(f"Not {i}", ["lore", "todo", "career", "proje/alt"])
        self.assertEqual(inbox.themes(self.notes), [])          # client/claude is on every note too

    def test_notes_outside_inbox_do_not_count(self):
        vault.add_area(self.notes, "ideas", now=NOW, machine="M")
        for i in range(3):
            jot.jot(self.notes, "ideas", f"Fikir {i}", "x", tags=["spor"], client="claude",
                    now=NOW, machine="M")
        self.assertEqual(inbox.themes(self.notes), [])

    def test_declined_theme_is_not_suggested_again(self):
        for i in range(3):
            self.note(f"Koşu {i}", ["spor"])
        inbox.decline(self.notes, "spor")
        self.assertEqual(inbox.themes(self.notes), [])
        self.assertIn("spor", inbox.declined(self.notes))
        self.assertTrue((self.notes / ".lore" / "state" / "declined-areas.json").is_file())

    def test_suggestions_for_a_note_only_name_its_own_tags(self):
        for i in range(3):
            self.note(f"Koşu {i}", ["spor"])
            self.note(f"Kitap {i}", ["okuma"])
        self.assertEqual([t.name for t in inbox.themes(self.notes, tags=["okuma"])], ["okuma"])


class ReportTest(InboxCase):
    def test_count_and_age(self):
        self.note("Eski", ["a"], days_ago=21)
        self.note("Yeni", ["b"])
        rep = inbox.report(self.notes, now=NOW)
        self.assertEqual((rep.count, rep.oldest_days), (2, 21))

    def test_empty_inbox(self):
        rep = inbox.report(self.notes, now=NOW)
        self.assertEqual((rep.count, rep.oldest_days, rep.themes), (0, None, []))

    def test_mesh_reports_the_inbox(self):
        for i in range(3):
            self.note(f"Koşu {i}", ["spor"], days_ago=i)
        report = mesh.check(self.notes, now=NOW)
        text = mesh.format_report(report)
        self.assertIn("Inbox: 3 notes, oldest 2 days", text)
        self.assertIn("spor (3)", text)
        self.assertFalse(report.failed)  # information, not a problem


class CommandsTest(InboxCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def jot_cli(self, title, tags):
        return self.run_cli("jot", "--area", "inbox", "--title", title, "--tags", tags,
                            "--client", "claude", "--body", "metin")

    def test_jot_prints_a_suggestion_at_the_threshold(self):
        _, out = self.jot_cli("Koşu 1", "spor")
        _, out = self.jot_cli("Koşu 2", "spor")
        self.assertNotIn("SUGGEST", out)
        code, out = self.jot_cli("Koşu 3", "spor")
        self.assertEqual(code, 0, out)
        self.assertIn("SUGGEST:", out)
        self.assertIn("lore.py area add spor", out)
        self.assertIn("lore.py area decline spor", out)
        self.assertFalse((self.notes / "spor").exists())  # nothing is created on its own

    def test_area_decline_and_list(self):
        code, out = self.run_cli("area", "decline", "spor")
        self.assertEqual(code, 0, out)
        for i in range(3):
            _, out = self.jot_cli(f"Koşu {i}", "spor")
        self.assertNotIn("SUGGEST", out)
        _, out = self.run_cli("area", "list")
        self.assertIn("Declined: spor", out)

    def test_decline_rejects_bad_names(self):
        code, out = self.run_cli("area", "decline", "Kötü Ad!")
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
