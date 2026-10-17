import unittest

from lorelib import frontmatter, vault
from tests.helpers import NOW, VaultCase


class SlugifyTest(unittest.TestCase):
    def test_turkish_title(self):
        self.assertEqual(vault.slugify("Şirket Görüşmesi: Çağrı & İş"), "sirket-gorusmesi-cagri-is")

    def test_length_limit(self):
        self.assertLessEqual(len(vault.slugify("a" * 200)), 60)

    def test_empty(self):
        self.assertEqual(vault.slugify("!!!"), "")


class SeedTest(VaultCase):
    def test_creates_skeleton(self):
        created = vault.seed(self.notes, now=NOW, machine="M")
        for area in vault.REQUIRED_AREAS:
            self.assertTrue((self.notes / area / f"{area}.md").is_file())
        self.assertTrue((self.notes / "home.md").is_file())
        self.assertEqual(len(created), len(vault.REQUIRED_AREAS) + 2)  # + home.md and me.md
        meta, _ = frontmatter.parse((self.notes / "inbox" / "inbox.md").read_text(encoding="utf-8"))
        self.assertEqual(frontmatter.missing_fields(meta), [])

    def test_never_overwrites(self):
        self.put("inbox/inbox.md", "benim metnim")
        vault.seed(self.notes, now=NOW, machine="M")
        self.assertEqual((self.notes / "inbox" / "inbox.md").read_text(encoding="utf-8"), "benim metnim")
        self.assertEqual(vault.seed(self.notes, now=NOW, machine="M"), [])

    def test_iter_notes_skips_hidden(self):
        self.put("ideas/a.md", "x")
        self.put(".obsidian/b.md", "x")
        self.put("ideas/.trash/c.md", "x")
        names = [p.name for p in vault.iter_notes(self.notes)]
        self.assertEqual(names, ["a.md"])


if __name__ == "__main__":
    unittest.main()
