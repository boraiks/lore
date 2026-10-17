import unittest

from lorelib import frontmatter


META = {
    "title": "Acme: staj başvurusu",
    "created": "2026-10-17T10:00",
    "updated": "2026-10-17T10:00",
    "tags": ["staj", "acme"],
    "status": "active",
    "type": "note",
    "machine": "DESK-1",
    "client": "claude",
}


class FrontmatterTest(unittest.TestCase):
    def test_round_trip(self):
        text = frontmatter.render(META) + "\ngövde\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta, META)
        self.assertEqual(body.strip(), "gövde")

    def test_field_order(self):
        lines = frontmatter.render(META).splitlines()
        keys = [l.split(":")[0] for l in lines if l and not l.startswith(("-", " "))]
        self.assertEqual(keys, list(frontmatter.FIELDS))

    def test_inline_tag_list(self):
        meta, _ = frontmatter.parse('---\ntitle: X\ntags: [a, "b c"]\n---\n')
        self.assertEqual(meta["tags"], ["a", "b c"])

    def test_no_frontmatter(self):
        meta, body = frontmatter.parse("düz metin")
        self.assertEqual(meta, {})
        self.assertEqual(body, "düz metin")

    def test_missing_fields(self):
        meta = dict(META, tags=[], client="")
        del meta["machine"]
        self.assertEqual(frontmatter.missing_fields(meta), ["tags", "machine", "client"])


if __name__ == "__main__":
    unittest.main()
