import unittest

from lorelib import turkish


class LowerFoldTest(unittest.TestCase):
    def test_dotted_and_dotless_i(self):
        self.assertEqual(turkish.lower("İSTANBUL"), "istanbul")
        self.assertEqual(turkish.lower("ISPARTA"), "ısparta")

    def test_fold_removes_turkish_marks(self):
        self.assertEqual(turkish.fold("Şirket Görüşmesi ÇAĞRI"), "sirket gorusmesi cagri")

    def test_tokens(self):
        self.assertEqual(turkish.tokens("Staj: başvuru-2026!"), ["staj", "basvuru", "2026"])


class StemTest(unittest.TestCase):
    def test_plural_and_case(self):
        self.assertEqual(turkish.stem("şirketlerde"), "sirket")
        self.assertEqual(turkish.stem("başvurularım"), "basvuru")
        self.assertEqual(turkish.stem("notlarından"), "not")

    def test_short_words_untouched(self):
        self.assertEqual(turkish.stem("ev"), "ev")
        self.assertEqual(turkish.stem("masa"), "masa")


class MatchTest(unittest.TestCase):
    def test_suffix_tolerance(self):
        self.assertTrue(turkish.matches("mülakatı", "mulakat"))
        self.assertTrue(turkish.matches("başvuru", "basvurusu"))
        self.assertTrue(turkish.matches("şirketlerde", "sirketi"))

    def test_consonant_softening(self):
        self.assertTrue(turkish.matches("kitap", "kitabi"))
        self.assertTrue(turkish.matches("kitabı", "kitap"))

    def test_no_match(self):
        self.assertFalse(turkish.matches("staj", "proje"))

    def test_exact_flag(self):
        self.assertEqual(turkish.match_kind("staj", "staj"), "exact")
        self.assertEqual(turkish.match_kind("staj", "stajlar"), "stem")
        self.assertIsNone(turkish.match_kind("staj", "ders"))


if __name__ == "__main__":
    unittest.main()
