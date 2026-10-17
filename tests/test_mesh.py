import unittest

from lorelib import mesh
from tests.helpers import VaultCase


class ExtractTest(unittest.TestCase):
    def test_forms(self):
        text = "a [[x]] b [[y|takma]] c [[z#başlık]] ![[r.png]]"
        self.assertEqual([t for _, t in mesh.extract_links(text)], ["x", "y", "z", "r.png"])

    def test_ignores_code(self):
        text = "`[[kod]]`\n```\n[[blok]]\n```\n[[gercek]]"
        self.assertEqual(mesh.extract_links(text), [(5, "gercek")])


class CheckTest(VaultCase):
    def test_broken_and_orphan(self):
        self.put("ideas/a.md", "bkz [[ideas/b]] ve [[kayip]]")
        self.put("ideas/b.md", "geri [[A]]")
        self.put("research/yalniz.md", "kimse bağlamadı")
        self.put("research/img.png", "")
        self.put("research/foto.md", "![[img.png]]")
        report = mesh.check(self.notes)
        self.assertEqual(report.broken, [("ideas/a.md", 1, "kayip")])
        self.assertEqual(report.orphans, ["research/yalniz.md"])
        self.assertEqual(report.total, 4)

    def test_self_link_is_orphan(self):
        self.put("ideas/self.md", "[[self]] [[#bolum]]")
        self.assertEqual(mesh.check(self.notes).orphans, ["ideas/self.md"])

    def test_report_text(self):
        self.put("ideas/a.md", "[[kayip]]")
        out = mesh.format_report(mesh.check(self.notes))
        self.assertIn("ideas/a.md:1 -> [[kayip]]", out)
        self.assertTrue(out.startswith(mesh.DATA_WARNING))

    def test_index_resolve(self):
        self.put("career/README.md", "")
        index = mesh.LinkIndex(self.notes)
        self.assertTrue(index.resolve("career/README"))
        self.assertTrue(index.resolve("readme"))
        self.assertIsNone(index.resolve("reer/README"))


class OutcomeCheckTest(VaultCase):
    def session(self, rel, messages, extra="", body="ham"):
        self.put(rel, f"---\ntitle: S\ntype: session\nstatus: raw\nmessages: {messages}\n{extra}---\n"
                      f"{body}\n\n[[x]]")

    def test_lists_logged_sessions_without_outcome(self):
        from lorelib import outcome, seal, sessionlog
        log, state = self.notes.parent / "sessions.jsonl", self.notes.parent / "state"
        sessionlog.record("claude", "uzun-oturum-1", 40, "Stop", path=log)
        sessionlog.record("claude", "kisa-oturum-1", 2, "Stop", path=log)
        sessionlog.record("codex", "bitmis-oturum-1", 40, "Stop", path=log)
        sessionlog.record("antigravity", "gizli-oturum-1", 40, "Stop", path=log)
        seal.mark_private(state, "gizli-oturum-1")
        self.put("x.md", "[[sessions/s]]")
        self.put("sessions/s.md", "---\ntitle: S\ntype: session\nsession: bitmis-oturum-1\n"
                                  "summarizer: agent\n---\n" + outcome.render(["a", "b", "c"], ["x"]))
        self.session("sessions/eski-ham.md", 40)  # an old raw note is no longer the source
        report = mesh.check(self.notes, min_messages=10, session_log=log, state_dir=state)
        self.assertEqual([(m[0], m[1]) for m in report.missing_outcome], [("claude", "uzun-oturum-1")])
        text = mesh.format_report(report)
        self.assertIn("claude uzun-otu", text)
        self.assertIn("40 messages", text)
        self.assertEqual(report.outcome_problems, [])  # information only, not a problem

    def test_outcome_problems(self):
        from lorelib import outcome
        self.put("x.md", "x")
        self.session("sessions/yarim.md", 40, body=outcome.BEGIN + "\n## Outcome\n- a")
        self.session("sessions/linksiz.md", 40, body=outcome.render(["a", "b", "c"], []))
        self.session("sessions/eksik.md", 40, extra="summarizer: agent\n")
        problems = dict(mesh.check(self.notes).outcome_problems)
        self.assertEqual(set(problems), {"sessions/yarim.md", "sessions/linksiz.md", "sessions/eksik.md"})


if __name__ == "__main__":
    unittest.main()
