import unittest

from lorelib import frontmatter, jot, mesh, outcome, seal, vault
from tests.helpers import NOW, VaultCase

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
BODY = "Yapılan: staj takip notu açıldı\nKarar: şirket başına bir not, çünkü arama kolay\nSonraki: Acme'ye CV gönder"


class SealCase(VaultCase):
    def setUp(self):
        super().setUp()
        self.state = self.notes.parent / "state"
        vault.seed(self.notes, now=NOW, machine="M")
        self.put("career/acme.md", "---\ntitle: Acme\n---\nAcme notu")

    def cfg(self, **kw):
        return dict({"remind_min_messages": 10, "private_dirs": []}, **kw)

    def seal(self, body=BODY, links=("career/acme",), **kw):
        args = dict(client="claude", session_id="sess-1", topic="Staj takibi", cwd="/p/proje",
                    now=NOW, machine="M", state_dir=self.state, cfg=self.cfg(), env={})
        args.update(kw)
        return seal.seal(self.notes, body=body, links=list(links), **args)

    def existing_note(self, sid="sess-1", extra=""):
        """A session note that is already there, e.g. written by hand."""
        return self.put("sessions/2026-10-16-claude-elle.md",
                        f"---\ntitle: Elle\ntype: session\nsession: {sid}\nstatus: active\n{extra}"
                        "---\nElle yazılmış önceki metin.\n")

    def parse(self, path):
        return frontmatter.parse(path.read_text(encoding="utf-8"))


class SealTest(SealCase):
    def test_creates_note_from_scratch(self):
        result = self.seal(session_id=None, env={"CLAUDE_CODE_SESSION_ID": "claude-sid-1"})
        self.assertEqual(result.action, "created")
        self.assertEqual(result.path.name, "2026-10-17-claude-staj-takibi.md")
        meta, body = self.parse(result.path)
        self.assertEqual((meta["client"], meta["session"], meta["machine"], meta["status"],
                          meta["summarizer"], meta["type"]),
                         ("claude", "claude-sid-1", "M", "summarized", "agent", "session"))
        self.assertEqual(frontmatter.missing_fields(meta), [])
        found = outcome.extract(body)
        self.assertIn("- Karar: şirket başına bir not, çünkü arama kolay", found.block)
        self.assertIn("[[career/acme]]", found.block)

    def test_same_id_updates_in_place(self):
        env = {"CLAUDE_CODE_SESSION_ID": "claude-sid-2"}
        first = self.seal(session_id=None, env=env)
        second = self.seal(session_id=None, env=env, body="Yapılan: X\nKarar: Y çünkü Z\nAçık: W")
        self.assertEqual((second.action, second.path), ("updated", first.path))
        body = self.parse(first.path)[1]
        self.assertEqual(body.count("## Outcome"), 1)
        self.assertIn("- Açık: W", body)
        self.assertNotIn("Acme'ye CV gönder", body)
        self.assertEqual(len(list((self.notes / "sessions").glob("2*.md"))), 1)

    def test_existing_note_keeps_its_text(self):
        path = self.existing_note()
        result = self.seal()
        self.assertEqual((result.action, result.path), ("updated", path))
        meta, body = self.parse(path)
        self.assertEqual((meta["status"], meta["summarizer"]), ("summarized", "agent"))
        self.assertEqual(outcome.extract(body).raw, "Elle yazılmış önceki metin.")

    def test_codex_uses_reminder_session(self):
        result = self.seal(client="codex", session_id="019a-codex-thread", env={})
        self.assertEqual(self.parse(result.path)[0]["session"], "019a-codex-thread")

    def test_hookless_client_creates_note(self):
        result = self.seal(client="antigravity", session_id=None, topic="Ödev planı")
        self.assertEqual(result.action, "created")
        self.assertEqual(result.path.name, "2026-10-17-antigravity-odev-plani.md")
        meta, body = self.parse(result.path)
        self.assertEqual((meta["type"], meta["status"], meta["client"]),
                         ("session", "summarized", "antigravity"))
        self.assertIn("## Outcome", body)
        again = self.seal(client="antigravity", session_id=None, topic="Ödev planı",
                          body="Yapılan: a\nKarar: b\nSonraki: c")
        self.assertEqual((again.action, again.path), ("updated", result.path))

    def test_session_from_environment(self):
        path = self.existing_note(sid="env-sid-9")
        result = self.seal(session_id=None, env={"CLAUDE_CODE_SESSION_ID": "env-sid-9"})
        self.assertEqual(result.path, path)

    def test_secret_rejected_without_echo(self):
        path = self.existing_note()
        before = path.read_text(encoding="utf-8")
        with self.assertRaises(jot.SecretRejected) as ctx:
            self.seal(body="Yapılan: a\nAnahtar " + AWS + "\nSonraki: c")
        self.assertNotIn(AWS, str(ctx.exception))
        self.assertEqual([f.line for f in ctx.exception.findings], [2])
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_line_count_enforced(self):
        with self.assertRaises(ValueError):
            self.seal(body="tek satır")
        with self.assertRaises(ValueError):
            self.seal(body="\n".join(f"satır {i}" for i in range(9)))

    def test_links_required_and_must_resolve(self):
        with self.assertRaises(ValueError):
            self.seal(links=())
        with self.assertRaises(ValueError) as ctx:
            self.seal(links=("career/acme", "uydurma-not"))
        self.assertIn("uydurma-not", str(ctx.exception))
        self.assertFalse(list((self.notes / "sessions").glob("2*.md")))

    def test_links_build_graph_without_breaks(self):
        self.seal(links=("career/acme", "career/README"))
        report = mesh.check(self.notes)
        self.assertEqual(report.broken, [])
        self.assertNotIn("career/acme.md", report.orphans)


class PrivateTest(SealCase):
    def test_private_flag_blocks_seal(self):
        path = self.existing_note()
        before = path.read_text(encoding="utf-8")
        seal.mark_private(self.state, "sess-1")
        with self.assertRaises(seal.PrivateSession):
            self.seal()
        self.assertEqual(path.read_text(encoding="utf-8"), before)  # kept, not deleted

    def test_private_dir(self):
        cfg = self.cfg(private_dirs=[str(self.notes.parent / "gizli")])
        with self.assertRaises(seal.PrivateSession):
            self.seal(cwd=str(self.notes.parent / "gizli" / "alt"), cfg=cfg)
        self.assertFalse(list((self.notes / "sessions").glob("2*.md")))

    def test_private_note_meta(self):
        self.existing_note(extra="private: true\n")
        with self.assertRaises(seal.PrivateSession):
            self.seal()


if __name__ == "__main__":
    unittest.main()
