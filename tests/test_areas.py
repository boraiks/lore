import io
import unittest
from contextlib import redirect_stdout

from lorelib import cli, frontmatter, jot, vault
from tests.helpers import NOW, VaultCase

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


class AreasTest(VaultCase):
    def test_seed_creates_only_the_required_areas(self):
        vault.seed(self.notes, now=NOW, machine="M")
        self.assertEqual(vault.areas(self.notes), ["inbox", "sessions"])
        for name in ("home.md", "me.md", "inbox/inbox.md", "sessions/sessions.md"):
            self.assertTrue((self.notes / name).is_file(), name)
        self.assertFalse((self.notes / "career").exists())

    def test_an_area_is_a_folder_with_its_own_note(self):
        vault.seed(self.notes)
        self.put("loose/x.md", "x")            # folder without an area note
        self.put("_templates/_templates.md", "x")
        self.put(".hidden/.hidden.md", "x")
        self.put("manual/manual.md", "made in Obsidian")
        self.assertEqual(vault.areas(self.notes), ["inbox", "manual", "sessions"])

    def test_add_area_from_the_catalogue(self):
        path = vault.add_area(self.notes, "career", now=NOW, machine="M")
        self.assertEqual(path, self.notes / "career" / "career.md")
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "Career")
        self.assertIn("internship", body.lower())
        self.assertIn("[[home]]", body)
        self.assertIn("career", vault.areas(self.notes))

    def test_add_custom_area(self):
        path = vault.add_area(self.notes, "fitness", "Antrenman ve beslenme notları.")
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "Fitness")
        self.assertIn("Antrenman ve beslenme notları.", body)

    def test_existing_folder_is_adopted_not_touched(self):
        self.put("hobby/guitar.md", "akorlar")
        vault.add_area(self.notes, "hobby")
        self.assertEqual((self.notes / "hobby" / "guitar.md").read_text(encoding="utf-8"), "akorlar")
        self.assertIn("hobby", vault.areas(self.notes))

    def test_bad_names_and_duplicates(self):
        vault.add_area(self.notes, "career")
        for bad in ("career", "Spor Notları", "../x", "_x", ".x", "", "a" * 41):
            with self.assertRaises(ValueError, msg=bad):
                vault.add_area(self.notes, bad)

    def test_secret_in_description_creates_nothing(self):
        with self.assertRaises(ValueError) as ctx:
            vault.add_area(self.notes, "work", "anahtar " + AWS)
        self.assertNotIn(AWS, str(ctx.exception))
        self.assertFalse((self.notes / "work").exists())


class JotAreaTest(VaultCase):
    def test_unknown_area_is_refused_with_a_hint(self):
        with self.assertRaises(ValueError) as ctx:
            jot.jot(self.notes, "fitness", "Koşu", client="claude", now=NOW, machine="M")
        self.assertIn("area add fitness", str(ctx.exception))

    def test_inbox_always_works(self):
        path, _ = jot.jot(self.notes, "inbox", "Dağınık fikir", client="claude", now=NOW, machine="M")
        self.assertEqual(path.parent, self.notes / "inbox")
        self.assertIn("[[inbox/inbox]]", path.read_text(encoding="utf-8"))


class MeTest(VaultCase):
    def test_template_from_seed(self):
        vault.seed(self.notes)
        meta, body = frontmatter.parse((self.notes / "me.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["title"], "About me")
        for heading in ("## What I use this memory for", "## How I like answers"):
            self.assertIn(heading, body)
        self.assertIn("[[home]]", body)

    def test_set_me_keeps_header_and_links_home(self):
        vault.seed(self.notes, now=NOW, machine="M")
        created = frontmatter.parse((self.notes / "me.md").read_text(encoding="utf-8"))[0]["created"]
        vault.set_me(self.notes, "## Ne için\nStaj arama ve dersler.")
        meta, body = frontmatter.parse((self.notes / "me.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["created"], created)
        self.assertIn("Staj arama ve dersler.", body)
        self.assertIn("[[home]]", body)

    def test_set_me_rejects_secrets_without_echo(self):
        vault.seed(self.notes)
        before = (self.notes / "me.md").read_text(encoding="utf-8")
        with self.assertRaises(jot.SecretRejected) as ctx:
            vault.set_me(self.notes, "TC 10000000146")
        self.assertNotIn("10000000146", str(ctx.exception))
        self.assertEqual((self.notes / "me.md").read_text(encoding="utf-8"), before)


class AreaCommandTest(VaultCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue()

    def test_add_and_list(self):
        self.run_cli("seed")
        code, out = self.run_cli("area", "add", "fitness", "Antrenman notları.")
        self.assertEqual(code, 0, out)
        self.assertIn("fitness", out)
        code, out = self.run_cli("area", "list")
        self.assertEqual(code, 0)
        for name in ("inbox", "sessions", "fitness"):
            self.assertIn(name, out)
        self.assertIn("career", out)  # suggestions not created yet are listed too
        self.assertNotEqual(self.run_cli("area", "add", "fitness")[0], 0)

    def test_me_command(self):
        self.run_cli("seed")
        code, out = self.run_cli("me", "--body", "## Ne için\nDersler.")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("me")
        self.assertIn("Dersler.", out)
        self.assertTrue(out.startswith("WARNING"))  # note content is data
        self.assertEqual(self.run_cli("me", "--body", "parola: Kedi1234")[0], 3)


if __name__ == "__main__":
    unittest.main()
