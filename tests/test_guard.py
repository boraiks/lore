import unittest

from lorelib import guard

# Fake values are assembled at runtime so the repository itself never holds
# anything that looks like a real credential.
GITHUB = "ghp_" + "a1B2" * 9
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
OPENAI = "sk-" + "x9" * 15
CARD = "4111 1111 1111 1111"  # public test number, passes Luhn
TCKN = "10000000146"  # checksum-valid test number
IBAN = "TR33 0006 1005 1978 6457 8413 26"


class ScanTest(unittest.TestCase):
    def kinds(self, text):
        return [f.kind for f in guard.scan(text)]

    def test_detects_tokens(self):
        self.assertIn("github-token", self.kinds("tok " + GITHUB))
        self.assertIn("aws-key", self.kinds(AWS))
        self.assertIn("api-key", self.kinds("key=" + OPENAI))

    def test_detects_private_key(self):
        self.assertIn("private-key", self.kinds("-----BEGIN RSA PRIVATE KEY-----"))

    def test_detects_assignment(self):
        self.assertIn("password", self.kinds("parola: Kedi1234"))
        self.assertIn("password", self.kinds("password = hunter2"))

    def test_detects_ids_and_finance(self):
        self.assertIn("card-number", self.kinds("kart " + CARD))
        self.assertIn("national-id", self.kinds("TC " + TCKN))
        self.assertIn("iban", self.kinds("IBAN " + IBAN))
        self.assertIn("phone", self.kinds("tel 0532 123 45 67"))

    def test_detects_url_credentials(self):
        self.assertIn("url-credentials", self.kinds("postgres://user:pa55@db.local/x"))

    def test_line_numbers(self):
        found = guard.scan("ilk satır\nikinci " + AWS + "\n")
        self.assertEqual([f.line for f in found], [2])

    def test_finding_does_not_carry_value(self):
        finding = guard.scan(AWS)[0]
        self.assertNotIn(AWS, repr(finding))

    def test_clean_turkish_text(self):
        text = (
            "Şifre değiştirildi, token: lexer'ın ürettiği birim.\n"
            "2026-10-17 tarihinde mülakat var. Ders kodu BLM3021.\n"
            "Rastgele sayı 12345678901 checksum tutmaz."
        )
        self.assertEqual(guard.scan(text), [])


class RedactTest(unittest.TestCase):
    def test_redact_hides_values(self):
        text, count = guard.redact("a " + AWS + " b parola: Kedi1234")
        self.assertEqual(count, 2)
        self.assertNotIn(AWS, text)
        self.assertNotIn("Kedi1234", text)
        self.assertIn("parola:", text)


if __name__ == "__main__":
    unittest.main()
