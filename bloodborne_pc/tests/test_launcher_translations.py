from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_lang
import bbport_lang_more


class TranslationKeyTests(unittest.TestCase):
    """Every language translates exactly the English texts in KEYS and MORE_KEYS, by name."""

    def check(self, keys, translations):
        self.assertEqual(len(keys), len(set(keys)), 'a key is listed twice')
        for language, texts in translations.items():
            with self.subTest(language=language):
                self.assertEqual(sorted(set(keys) - set(texts)), [], 'missing translations')
                self.assertEqual(sorted(set(texts) - set(keys)), [], 'translations of texts no longer in the keys')
                for key, text in texts.items():
                    self.assertTrue(text.strip(), key)
                    self.assertEqual(sorted(re.findall(r'\{\d*\}', key)), sorted(re.findall(r'\{\d*\}', text)),
                                     f'placeholders differ: {key!r}')

    def test_launcher_texts(self):
        self.check(bbport_lang.KEYS, bbport_lang.TRANSLATIONS)

    def test_online_and_steam_texts(self):
        self.check(bbport_lang_more.MORE_KEYS, bbport_lang_more.MORE)

    def test_partial_translations_name_real_texts(self):
        known = set(bbport_lang.KEYS) | set(bbport_lang_more.MORE_KEYS)
        source = (Path(bbport_lang.__file__).parent / 'bbport_launcher_win.py').read_text(encoding='utf-8')
        for language, texts in bbport_lang.EXTRA_TRANSLATIONS.items():
            for key in texts:
                with self.subTest(language=language, key=key):
                    self.assertTrue(key in known or repr(key)[1:-1] in source, 'not a launcher text')

    def test_table_merges_every_source(self):
        table = bbport_lang.table('pt')
        self.assertEqual(table['Play'], bbport_lang.TRANSLATIONS['pt']['Play'])
        self.assertEqual(table['Online co-op'], bbport_lang_more.MORE['pt']['Online co-op'])
        self.assertIn('Voice language', table)
        self.assertEqual(bbport_lang.table('en'), {})


if __name__ == '__main__':
    unittest.main()
