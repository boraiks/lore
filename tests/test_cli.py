import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from lorelib import cli, recall
from tests.helpers import VaultCase

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


class CliTest(VaultCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv), notes_dir=self.notes)
        return code, out.getvalue(), err.getvalue()

    def test_seed_jot_recall_mesh(self):
        self.assertEqual(self.run_cli("seed")[0], 0)
        code, out, _ = self.run_cli("jot", "--area", "courses", "--title", "Veri Yapıları",
                                    "--tags", "ders,algo", "--client", "codex",
                                    "--body", "Yığın ve kuyruk anlatıldı.")
        self.assertEqual(code, 0, out)
        self.assertIn("/courses/veri-yapilari.md", out)
        code, out, _ = self.run_cli("recall", "kuyruklar")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(recall.DATA_WARNING))
        self.assertIn("courses/veri-yapilari.md", out)
        code, out, _ = self.run_cli("mesh")
        self.assertEqual(code, 0, out)

    def test_jot_secret_exit_code(self):
        code, out, err = self.run_cli("jot", "--area", "ideas", "--title", "x",
                                      "--client", "claude", "--body", AWS)
        self.assertNotEqual(code, 0)
        self.assertNotIn(AWS, out + err)

    def test_jot_exists_exit_code(self):
        args = ("jot", "--area", "ideas", "--title", "Aynı", "--client", "claude")
        self.assertEqual(self.run_cli(*args)[0], 0)
        self.assertNotEqual(self.run_cli(*args)[0], 0)

    def test_seal_cli(self):
        self.run_cli("seed")
        args = ("seal", "--client", "antigravity", "--session", "ag-1", "--topic", "Ders planı",
                "--link", "courses/README")
        code, out, _ = self.run_cli(*args, "--body", "Yapılan: plan\nKarar: haftalık\nSonraki: başla")
        self.assertEqual(code, 0, out)
        self.assertIn("/sessions/2026-", out)
        code, out, _ = self.run_cli(*args, "--body", "Yapılan: a\nAnahtar " + AWS + "\nSonraki: c")
        self.assertEqual(code, 3)
        self.assertNotIn(AWS, out)
        self.assertEqual(self.run_cli("mesh")[0], 0)

    def test_seal_private_cli(self):
        self.run_cli("seed")
        code, out, _ = self.run_cli("seal", "--client", "codex", "--session", "cx-1", "--private")
        self.assertEqual(code, 0, out)
        code, _, _ = self.run_cli("seal", "--client", "codex", "--session", "cx-1", "--link",
                                  "ideas/README", "--body", "a\nb\nc")
        self.assertEqual(code, 6)

    def test_mesh_reports_issue(self):
        self.put("ideas/a.md", "[[kayip]]")
        code, out, _ = self.run_cli("mesh")
        self.assertEqual(code, 1)
        self.assertIn("kayip", out)


if __name__ == "__main__":
    unittest.main()
