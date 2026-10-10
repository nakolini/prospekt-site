import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import build  # noqa: E402

I18N = os.path.join(HERE, "..", "..", "i18n")
PLACEHOLDER = re.compile(r"\{[a-z_0-9]+\}")


def load(code):
    with open(os.path.join(I18N, "%s.json" % code), encoding="utf-8") as f:
        return json.load(f)


class I18nTest(unittest.TestCase):
    def test_every_language_is_present(self):
        for code, _, _ in build.LANGUAGES:
            self.assertTrue(os.path.exists(os.path.join(I18N, "%s.json" % code)), code)

    def test_translations_match_english_keys_and_placeholders(self):
        english = load("en")
        for code, _, _ in build.LANGUAGES[1:]:
            path = os.path.join(I18N, "%s.json" % code)
            if not os.path.exists(path):
                continue
            strings = load(code)
            with self.subTest(language=code):
                self.assertEqual(sorted(strings), sorted(english))
                for key, text in english.items():
                    self.assertEqual(sorted(PLACEHOLDER.findall(strings[key])), sorted(PLACEHOLDER.findall(text)), key)
                    if not key.startswith("_meta"):
                        self.assertTrue(strings[key].strip(), key)

    def test_brand_names_survive_translation(self):
        english = load("en")
        for code, _, _ in build.LANGUAGES[1:]:
            path = os.path.join(I18N, "%s.json" % code)
            if not os.path.exists(path):
                continue
            strings = load(code)
            for key, text in english.items():
                for word in ["Prospekt", "nakolini", "iPhone"]:
                    if word in text:
                        self.assertIn(word, strings[key], "%s %s" % (code, key))


if __name__ == "__main__":
    unittest.main()
