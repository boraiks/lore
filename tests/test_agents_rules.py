import unittest

from lorelib import vault


class AgentsRulesTest(unittest.TestCase):
    def setUp(self):
        self.text = (vault.REPO / "AGENTS.md").read_text(encoding="utf-8")

    def test_short_trigger(self):
        self.assertIn('"save"', self.text)
        self.assertIn('"wrap up"', self.text)

    def test_rule_files_are_not_self_edited(self):
        self.assertIn("Do not edit skill or rule files unless the user says so", self.text)

    def test_thin_client_files_point_to_agents_md(self):
        for name in ("CLAUDE.md", "GEMINI.md"):
            self.assertIn("@AGENTS.md", (vault.REPO / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
