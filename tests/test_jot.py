import unittest

from lorelib import frontmatter, jot, vault
from tests.helpers import NOW, VaultCase

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


class JotTest(VaultCase):
    def setUp(self):
        super().setUp()
        vault.add_area(self.notes, "career", now=NOW, machine="DESK-1")

    def write(self, **kw):
        args = dict(area="career", title="Acme başvurusu", body="İlk görüşme yapıldı.",
                    tags=["staj"], client="claude", now=NOW, machine="DESK-1")
        args.update(kw)
        return jot.jot(self.notes, **args)

    def test_writes_frontmatter(self):
        path, warnings = self.write(links=["career/career"])
        self.assertEqual(path, self.notes / "career" / "acme-basvurusu.md")
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "Acme başvurusu")
        self.assertEqual(meta["created"], "2026-10-17T10:30")
        self.assertEqual(meta["updated"], "2026-10-17T10:30")
        self.assertEqual(meta["machine"], "DESK-1")
        self.assertEqual(meta["client"], "claude")
        self.assertEqual(meta["status"], "active")
        self.assertEqual(meta["type"], "note")
        self.assertIn("İlk görüşme yapıldı.", body)
        self.assertIn("[[career/career]]", body)
        self.assertEqual(warnings, [])

    def test_never_overwrites(self):
        path, _ = self.write()
        path.write_text("kullanıcı düzenledi", encoding="utf-8")
        with self.assertRaises(jot.NoteExists):
            self.write(body="yeni")
        self.assertEqual(path.read_text(encoding="utf-8"), "kullanıcı düzenledi")

    def test_rejects_secret_without_echo(self):
        with self.assertRaises(jot.SecretRejected) as ctx:
            self.write(body="satır bir\nanahtar " + AWS)
        self.assertNotIn(AWS, str(ctx.exception))
        self.assertEqual([(f.field, f.line) for f in ctx.exception.findings], [("body", 2)])
        self.assertFalse((self.notes / "career" / "acme-basvurusu.md").exists())

    def test_rejects_secret_in_title(self):
        with self.assertRaises(jot.SecretRejected):
            self.write(title="not " + AWS)

    def test_auto_links_area_note(self):
        path, warnings = self.write(body="bağlantısız metin")
        self.assertIn("[[career/career]]", path.read_text(encoding="utf-8"))
        self.assertTrue(any("career/career" in w for w in warnings))
        self.assertTrue((self.notes / "career" / "career.md").is_file())

    def test_body_link_counts(self):
        self.write(title="Diğer not")
        path, warnings = self.write(title="Bağlı not", body="bkz. [[diger-not]]")
        self.assertNotIn("Related:", path.read_text(encoding="utf-8"))
        self.assertEqual(warnings, [])

    def test_warns_missing_fields(self):
        _, warnings = self.write(tags=[], client=None, links=["career/career"])
        text = " ".join(warnings)
        self.assertIn("tags", text)
        self.assertIn("client", text)

    def test_warns_unresolved_link(self):
        _, warnings = self.write(links=["yok-boyle-not"])
        self.assertTrue(any("yok-boyle-not" in w for w in warnings))

    def test_tags_normalized(self):
        path, _ = self.write(tags=["#Staj Arama", "İŞ"])
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["tags"], ["staj-arama", "iş", "client/claude"])

    def test_client_tag_for_the_graph(self):
        path, _ = self.write(client="antigravity", tags=["staj", "client/antigravity"])
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["tags"], ["staj", "client/antigravity"])  # added once
        path, _ = self.write(title="El ile", client=None, tags=["staj"])
        meta, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["tags"], ["staj"])  # no client given: no client tag

    def test_session_area_uses_date_client_topic_name(self):
        path, _ = self.write(area="sessions", title="Session: Ödev planı", client="antigravity",
                             type="session", status="raw")
        self.assertEqual(path.name, "2026-10-17-antigravity-session-odev-plani.md")

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            self.write(area="secrets")
        with self.assertRaises(ValueError):
            self.write(title="!!!")
        with self.assertRaises(ValueError):
            self.write(status="weird")


if __name__ == "__main__":
    unittest.main()
