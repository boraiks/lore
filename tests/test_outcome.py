import unittest

from lorelib import outcome


class OutcomeBlockTest(unittest.TestCase):
    def test_render_and_extract(self):
        block = outcome.render(["Yapılan: A", "- Karar: B çünkü C", "Sonraki: D"], ["ideas/x"])
        body = block + "\n\n> ham özüt\n1. istek"
        found = outcome.extract(body)
        self.assertFalse(found.malformed)
        self.assertIn("## Outcome", found.block)
        self.assertIn("- Yapılan: A", found.block)
        self.assertIn("- Karar: B çünkü C", found.block)
        self.assertIn("[[ideas/x]]", found.block)
        self.assertEqual(found.raw, "> ham özüt\n1. istek")

    def test_put_replaces_in_place(self):
        body = outcome.render(["a", "b", "c"], ["x"]) + "\n\nham"
        body = outcome.put(body, outcome.render(["d", "e", "f"], ["y"]))
        self.assertEqual(body.count(outcome.BEGIN), 1)
        self.assertIn("- d", body)
        self.assertNotIn("- a", body)
        self.assertTrue(body.endswith("ham"))

    def test_put_inserts_on_top(self):
        body = outcome.put("ham özüt", outcome.render(["a", "b", "c"], ["x"]))
        self.assertTrue(body.startswith(outcome.BEGIN))
        self.assertTrue(body.endswith("ham özüt"))

    def test_malformed(self):
        self.assertTrue(outcome.extract(outcome.BEGIN + "\n## Outcome\nyarım").malformed)
        self.assertTrue(outcome.extract(outcome.END + "\n" + outcome.BEGIN).malformed)

    def test_absent(self):
        found = outcome.extract("yalnızca ham")
        self.assertIsNone(found.block)
        self.assertEqual(found.raw, "yalnızca ham")


if __name__ == "__main__":
    unittest.main()
