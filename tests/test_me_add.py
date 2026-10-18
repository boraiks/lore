"""Standing preferences the user states go into me.md at once, one line each, so every
client sees them at the start of a session."""

import io
import unittest
from contextlib import redirect_stdout

from lorelib import cli, frontmatter, guard, vault
from tests.helpers import NOW, VaultCase

ME = """---
title: About me
created: 2026-10-18T07:44
updated: 2026-10-18T07:46
tags:
  - me
---

## What I use this memory for
İş ve dersler.

## How I like answers
Kısa, Türkçe.

## Language for notes
Türkçe.

Home: [[home]]
"""


class AddLineTest(VaultCase):
    def setUp(self):
        super().setUp()
        self.put("me.md", ME)

    def body(self):
        return frontmatter.parse((self.notes / "me.md").read_text(encoding="utf-8"))[1]

    def test_line_goes_under_its_section(self):
        self.assertTrue(vault.add_me_line(self.notes, "Uzun tire yerine - kullan.", now=NOW))
        body = self.body()
        self.assertIn("## How I like answers\nKısa, Türkçe.\n- Uzun tire yerine - kullan.\n\n## Language",
                      body)
        meta = frontmatter.parse((self.notes / "me.md").read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["updated"], "2026-10-17T10:30")
        self.assertEqual(meta["created"], "2026-10-18T07:44")

    def test_other_section_is_created_before_the_home_link(self):
        vault.add_me_line(self.notes, "Pazartesi spor.", section="Routines")
        body = self.body()
        self.assertIn("## Routines\n- Pazartesi spor.\n\nHome: [[home]]", body)

    def test_same_line_twice_is_kept_once(self):
        vault.add_me_line(self.notes, "Uzun tire yerine - kullan.")
        self.assertFalse(vault.add_me_line(self.notes, "- uzun tire yerine - kullan."))
        self.assertEqual(self.body().count("Uzun tire"), 1)

    def test_secret_is_refused_and_nothing_changes(self):
        before = (self.notes / "me.md").read_text(encoding="utf-8")
        with self.assertRaises(guard.SecretRejected):
            vault.add_me_line(self.notes, "Telefonum 0532 123 45 67")
        self.assertEqual((self.notes / "me.md").read_text(encoding="utf-8"), before)

    def test_missing_me_md_is_created(self):
        (self.notes / "me.md").unlink()
        vault.add_me_line(self.notes, "Kısa cevap.")
        self.assertIn("## How I like answers", self.body())
        self.assertIn("- Kısa cevap.", self.body())

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["me", "--add", "Uzun tire yerine - kullan."], notes_dir=self.notes)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("SAVED", out.getvalue())
        with redirect_stdout(io.StringIO()) as again:
            cli.main(["me", "--add", "Uzun tire yerine - kullan."], notes_dir=self.notes)
        self.assertIn("ALREADY", again.getvalue())


if __name__ == "__main__":
    unittest.main()
