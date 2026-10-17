import json
import unittest

from lorelib import install, mesh, recall, vault
from tests.helpers import VaultCase


class ObsidianStarterTest(VaultCase):
    def test_template_and_settings(self):
        created = {p.relative_to(self.notes).as_posix() for p in vault.obsidian_starter(self.notes)}
        self.assertEqual(created, {"_templates/lore-note.md", ".obsidian/templates.json",
                                   ".obsidian/graph.json", ".obsidian/app.json"})
        app = json.loads((self.notes / ".obsidian" / "app.json").read_text(encoding="utf-8"))
        self.assertEqual(set(app["userIgnoreFilters"]),
                         {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "_templates/"})
        templates = json.loads((self.notes / ".obsidian" / "templates.json").read_text(encoding="utf-8"))
        self.assertEqual(templates["folder"], "_templates")
        graph = json.loads((self.notes / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
        self.assertTrue(graph["showTags"])  # client tags show as nodes
        queries = {g["query"] for g in graph["colorGroups"]}
        self.assertTrue({f"path:{a}" for a in ("career", "courses", "ideas", "research")} <= queries)
        template = (self.notes / "_templates" / "lore-note.md").read_text(encoding="utf-8")
        for field in ("title:", "created:", "updated:", "tags:", "status:", "type:", "client: manual"):
            self.assertIn(field, template)

    def test_existing_obsidian_settings_are_kept(self):
        self.put(".obsidian/graph.json", '{"mine": true}')
        created = vault.obsidian_starter(self.notes)
        self.assertNotIn(".obsidian/graph.json",
                         {p.relative_to(self.notes).as_posix() for p in created})
        self.assertEqual((self.notes / ".obsidian" / "graph.json").read_text(encoding="utf-8"),
                         '{"mine": true}')


class NotNotesTest(VaultCase):
    def test_templates_and_pointers_are_not_notes(self):
        vault.seed(self.notes)
        install.install(self.notes)
        vault.obsidian_starter(self.notes)
        names = {vault.rel(p, self.notes) for p in vault.iter_notes(self.notes)}
        self.assertNotIn("AGENTS.md", names)
        self.assertFalse(any(n.startswith(".claude") for n in names))
        self.assertNotIn("_templates/lore-note.md", names)
        self.assertIn("home.md", names)
        report = mesh.check(self.notes)
        self.assertEqual((report.broken, report.orphans), ([], []))
        self.assertEqual(recall.recall(self.notes, "conversationId"), [])  # only in AGENTS.md

    def test_a_users_own_agents_md_in_a_subfolder_is_a_note(self):
        self.put("research/AGENTS.md", "[[home]]")
        self.put("home.md", "[[research/AGENTS]]")
        names = {vault.rel(p, self.notes) for p in vault.iter_notes(self.notes)}
        self.assertIn("research/AGENTS.md", names)


if __name__ == "__main__":
    unittest.main()
