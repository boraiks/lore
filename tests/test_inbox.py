"""Inbox summary: lore shows what piles up in inbox; the agent reads the meaning and the
user decides. The code never decides that two tags are one theme."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import timedelta

from lorelib import cli, inbox, jot, mesh, vault
from tests.helpers import NOW, VaultCase


class InboxCase(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")

    def note(self, title, tags, days_ago=0):
        return jot.jot(self.notes, "inbox", title, "metin", tags=tags, client="claude",
                       now=NOW - timedelta(days=days_ago), machine="M")[0]


class TagSummaryTest(InboxCase):
    def test_tags_are_counted_largest_first(self):
        self.note("Koşu 1", ["antrenman"])
        self.note("Koşu 2", ["antrenman", "koşu"])
        self.note("Maç", ["spor"])
        self.assertEqual(inbox.tag_summary(self.notes), [("antrenman", 2), ("koşu", 1), ("spor", 1)])

    def test_client_tags_are_left_out(self):
        self.note("Not", ["spor"])
        self.assertEqual(inbox.tag_summary(self.notes), [("spor", 1)])  # not client/claude

    def test_turkish_spellings_count_together(self):
        for i, tag in enumerate(["çalışma", "calisma"]):
            self.note(f"Not {i}", [tag])
        self.assertEqual(inbox.tag_summary(self.notes), [("çalışma", 2)])

    def test_notes_outside_inbox_do_not_count(self):
        vault.add_area(self.notes, "ideas", now=NOW, machine="M")
        jot.jot(self.notes, "ideas", "Fikir", "x", tags=["spor"], client="claude",
                now=NOW, machine="M")
        self.assertEqual(inbox.tag_summary(self.notes), [])

    def test_line_is_short_and_lists_declined_areas(self):
        for i in range(20):
            self.note(f"Not {i}", [f"etiket{i:02d}"])
        inbox.decline(self.notes, "fitness")
        line = inbox.summary_line(self.notes)
        self.assertTrue(line.startswith("INBOX: 20 notes; tags: "))
        self.assertIn("(+8 more)", line)          # at most 12 tags are shown
        self.assertIn("declined areas: fitness", line)

    def test_no_line_while_inbox_is_small(self):
        self.note("Bir", ["a"])
        self.note("İki", ["b"])
        self.assertIsNone(inbox.summary_line(self.notes))
        self.note("Üç", ["c"])
        self.assertIsNotNone(inbox.summary_line(self.notes))


class DeclineTest(InboxCase):
    def test_decline_is_remembered(self):
        inbox.decline(self.notes, "spor")
        inbox.decline(self.notes, "spor")
        self.assertEqual(inbox.declined(self.notes), ["spor"])
        self.assertTrue((self.notes / ".lore" / "state" / "declined-areas.json").is_file())

    def test_bad_name(self):
        with self.assertRaises(ValueError):
            inbox.decline(self.notes, "Kötü Ad!")


class ReportTest(InboxCase):
    def test_count_and_age(self):
        self.note("Eski", ["a"], days_ago=21)
        self.note("Yeni", ["b"])
        rep = inbox.report(self.notes, now=NOW)
        self.assertEqual((rep.count, rep.oldest_days), (2, 21))

    def test_empty_inbox(self):
        rep = inbox.report(self.notes, now=NOW)
        self.assertEqual((rep.count, rep.oldest_days, rep.tags), (0, None, []))

    def test_mesh_reports_the_inbox(self):
        self.note("Koşu", ["antrenman"], days_ago=2)
        self.note("Maç", ["spor"])
        report = mesh.check(self.notes, now=NOW)
        text = mesh.format_report(report)
        self.assertIn("Inbox: 2 notes, oldest 2 days", text)
        self.assertIn("antrenman 1", text)
        self.assertFalse(report.failed)  # information, not a problem


class CommandsTest(InboxCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def jot_cli(self, area, title, tags):
        return self.run_cli("jot", "--area", area, "--title", title, "--tags", tags,
                            "--client", "claude", "--body", "metin")

    def test_jot_into_inbox_shows_the_summary_and_suggests_nothing(self):
        self.jot_cli("inbox", "Koşu 1", "antrenman")
        _, out = self.jot_cli("inbox", "Koşu 2", "antrenman")
        self.assertNotIn("INBOX:", out)
        code, out = self.jot_cli("inbox", "Maç", "spor")
        self.assertEqual(code, 0, out)
        self.assertIn("INBOX: 3 notes; tags: antrenman 2, spor 1", out)
        self.assertNotIn("SUGGEST", out)                  # the meaning is the agent's call
        self.assertFalse((self.notes / "spor").exists())  # nothing is created on its own

    def test_jot_into_an_area_prints_no_summary(self):
        for i in range(3):
            self.jot_cli("inbox", f"Not {i}", "spor")
        vault.add_area(self.notes, "ideas", now=NOW, machine="M")
        _, out = self.jot_cli("ideas", "Fikir", "spor")
        self.assertNotIn("INBOX:", out)

    def test_area_decline_and_list(self):
        code, out = self.run_cli("area", "decline", "spor")
        self.assertEqual(code, 0, out)
        _, out = self.run_cli("area", "list")
        self.assertIn("Declined: spor", out)
        code, _ = self.run_cli("area", "decline", "Kötü Ad!")
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
