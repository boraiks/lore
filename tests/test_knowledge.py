"""Knowledge: what we know about a project grows in its main note, one sourced line at a
time; and every area note lists its notes, so an area never looks empty."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import timedelta

from lorelib import cli, frontmatter, jot, knowledge, mesh, organize, recall, seal, vault
from tests.helpers import NOW, VaultCase

LATER = NOW + timedelta(hours=2)


class KnowCase(VaultCase):
    def setUp(self):
        super().setUp()
        vault.seed(self.notes, now=NOW, machine="M")
        vault.add_area(self.notes, "work", now=NOW, machine="M")
        self.main = jot.jot(self.notes, "work", "LayerCraft", "3D modelleri levhalara bölen araç.",
                            tags=["layercraft"], client="claude", now=NOW, machine="M")[0]
        self.session = seal.seal(self.notes, "claude", "a\nb\nc", ["work/layercraft"],
                                 session_id="s1", topic="LayerCraft testleri", now=NOW,
                                 machine="M").path
        self.source = vault.rel(self.session, self.notes)[:-3]

    def body(self, path=None):
        return frontmatter.parse((path or self.main).read_text(encoding="utf-8"))[1]


class KnowTest(KnowCase):
    def test_line_goes_into_a_knowledge_section_with_its_source(self):
        self.assertTrue(knowledge.add(self.notes, "work/layercraft", "Kesit için çift-tek kuralı kullanılıyor.",
                                      self.source, now=LATER))
        body = self.body()
        self.assertIn(f"## Knowledge\n- Kesit için çift-tek kuralı kullanılıyor. ([[{self.source}]])", body)
        self.assertLess(body.index("## Knowledge"), body.index("Related:"))
        meta = frontmatter.parse(self.main.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["updated"], "2026-10-17T12:30")
        self.assertEqual(mesh.check(self.notes).broken, [])

    def test_lines_add_up_and_repeats_are_ignored(self):
        knowledge.add(self.notes, "work/layercraft", "Bir.", self.source)
        knowledge.add(self.notes, "work/layercraft", "İki.", self.source)
        self.assertFalse(knowledge.add(self.notes, "work/layercraft", "- bir.", self.source))
        body = self.body()
        self.assertEqual(body.count("## Knowledge"), 1)
        self.assertLess(body.index("Bir."), body.index("İki."))

    def test_outdated_line_is_struck_not_deleted(self):
        knowledge.add(self.notes, "work/layercraft", "Delik 3 mm.", self.source)
        knowledge.outdate(self.notes, "work/layercraft", "Delik 3", now=LATER)
        self.assertIn("- ~~Delik 3 mm.", self.body())
        self.assertIn("(outdated 2026-10-17)", self.body())

    def test_refusals(self):
        with self.assertRaises(ValueError):                     # source must exist
            knowledge.add(self.notes, "work/layercraft", "x", "sessions/yok")
        with self.assertRaises(ValueError):                     # not into session notes
            knowledge.add(self.notes, self.source, "x", self.source)
        with self.assertRaises(ValueError):                     # nor me.md
            knowledge.add(self.notes, "me", "x", self.source)
        with self.assertRaises(Exception):                      # secrets
            knowledge.add(self.notes, "work/layercraft", "anahtar sk-ant-api03-" + "A" * 30,
                          self.source)
        with self.assertRaises(ValueError):                     # outdated needs one match
            knowledge.outdate(self.notes, "work/layercraft", "yok böyle bir şey")

    def test_undo_takes_the_lines_back(self):
        organize.start_run(self.notes, now=NOW)
        knowledge.add(self.notes, "work/layercraft", "Kalıcı.", self.source, now=NOW)
        knowledge.add(self.notes, "work/layercraft", "Eski bilgi.", self.source, now=NOW)
        knowledge.outdate(self.notes, "work/layercraft", "Kalıcı", now=NOW)
        organize.undo(self.notes, now=NOW)
        body = self.body()
        self.assertNotIn("Eski bilgi.", body)
        self.assertNotIn("Kalıcı", body)

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["know", "work/layercraft", "Rust ile yazıldı.", "--source", self.source],
                            notes_dir=self.notes)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("ADDED", out.getvalue())
        self.assertIn("Rust ile yazıldı.", self.body())


class IndexTest(KnowCase):
    def hub(self, area="work"):
        return self.notes / area / f"{area}.md"

    def test_area_note_lists_its_notes(self):
        changed = knowledge.refresh_index(self.notes, "work")
        self.assertTrue(changed)
        body = self.body(self.hub())
        self.assertIn("[[work/layercraft|LayerCraft]]: 3D modelleri levhalara bölen araç.", body)
        self.assertIn("Home: [[home]]", body)                   # the rest stays
        self.assertFalse(knowledge.refresh_index(self.notes, "work"))   # nothing new
        self.assertEqual(mesh.check(self.notes).broken, [])

    def test_text_the_user_wrote_is_kept(self):
        text = self.hub().read_text(encoding="utf-8").replace("Home: [[home]]", "Benim notum.\n\nHome: [[home]]")
        self.hub().write_text(text, encoding="utf-8")
        knowledge.refresh_index(self.notes, "work")
        jot.jot(self.notes, "work", "Staj takibi", "Başvurular.", client="claude", now=LATER)
        knowledge.refresh_index(self.notes, "work")
        body = self.body(self.hub())
        self.assertIn("Benim notum.", body)
        self.assertEqual(body.count(knowledge.INDEX_BEGIN), 1)
        self.assertLess(body.index("Staj takibi"), body.index("LayerCraft"))  # newest first

    def test_jot_through_the_cli_refreshes_the_index(self):
        with redirect_stdout(io.StringIO()):
            cli.main(["jot", "--area", "work", "--title", "Ön yazı", "--tags", "kariyer",
                      "--client", "claude", "--body", "Şablon."], notes_dir=self.notes)
        self.assertIn("Ön yazı", self.body(self.hub()))

    def test_search_does_not_rank_the_area_note_by_its_index(self):
        knowledge.refresh_index(self.notes, "work")
        hits = recall.recall(self.notes, "levhalara")
        self.assertEqual([h.rel for h in hits], ["work/layercraft.md"])


if __name__ == "__main__":
    unittest.main()
