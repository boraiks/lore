import unittest

from lorelib import vault


class AgentsRulesTest(unittest.TestCase):
    def test_repo_agents_md_points_to_the_vault_rules(self):
        text = (vault.REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("vault/AGENTS.md", text)
        self.assertIn("Do not edit skill or rule files unless the user says so", text)

    def test_vault_rules_have_the_short_trigger(self):
        text = (vault.REPO / "vault" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn('"save"', text)
        self.assertIn('"wrap up"', text)
        self.assertIn("{{LORE}}/lore.py", text)

    def test_thin_client_files_point_to_agents_md(self):
        for name in ("CLAUDE.md", "GEMINI.md"):
            self.assertIn("@AGENTS.md", (vault.REPO / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
