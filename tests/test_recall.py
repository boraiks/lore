import unittest

from lorelib import recall
from tests.helpers import VaultCase

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


def note(title, body, tags="x", updated="2026-10-01T09:00"):
    return (
        f'---\ntitle: "{title}"\ncreated: 2026-10-01T09:00\nupdated: {updated}\n'
        f"tags:\n  - {tags}\nstatus: active\ntype: note\nmachine: M\nclient: manual\n---\n{body}\n"
    )


class RecallTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.put("career/acme.md", note("Acme başvurusu", "Mülakatı 20 Ekim'de.", tags="staj"))
        self.put("courses/algo.md", note("Algoritmalar", "Graf dersleri ve ödevler."))
        self.put("ideas/app.md", note("Uygulama fikri", "Staj ilanlarını toplayan araç."))

    def test_suffix_tolerant_hit(self):
        hits = recall.recall(self.notes, "mülakatlar")
        self.assertEqual([h.rel for h in hits], ["career/acme.md"])

    def test_title_and_tag_rank_first(self):
        hits = recall.recall(self.notes, "staj")
        self.assertEqual(hits[0].rel, "career/acme.md")
        self.assertIn("ideas/app.md", [h.rel for h in hits])

    def test_limit(self):
        for i in range(recall.MAX_LIMIT + 5):
            self.put(f"research/r{i}.md", note(f"Not {i}", "ortak kelime"))
        self.assertEqual(len(recall.recall(self.notes, "ortak", limit=3)), 3)
        self.assertEqual(len(recall.recall(self.notes, "ortak", limit=999)), recall.MAX_LIMIT)

    def test_no_hits(self):
        self.assertEqual(recall.recall(self.notes, "kuantum"), [])

    def test_output_starts_with_data_warning(self):
        out = recall.format_hits(recall.recall(self.notes, "staj"), "staj")
        self.assertTrue(out.startswith(recall.DATA_WARNING))
        self.assertIn("career/acme.md", out)

    def test_empty_output_still_warns(self):
        out = recall.format_hits([], "yok")
        self.assertTrue(out.startswith(recall.DATA_WARNING))

    def test_snippets_are_redacted(self):
        self.put("research/leak.md", note("Sızıntı", "anahtar " + AWS + " burada"))
        out = recall.format_hits(recall.recall(self.notes, "anahtar"), "anahtar")
        self.assertNotIn(AWS, out)
        self.assertIn("anahtar", out)

    def test_note_without_frontmatter(self):
        self.put("research/plain.md", "kuantum bilgisayar")
        hits = recall.recall(self.notes, "kuantum")
        self.assertEqual(hits[0].title, "plain")


if __name__ == "__main__":
    unittest.main()
