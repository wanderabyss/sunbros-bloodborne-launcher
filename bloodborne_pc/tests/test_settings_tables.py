from pathlib import Path
import importlib.util
import re
import sys
import unittest

PORT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gen_settings_tables', PORT / 'scripts' / 'gen_settings_tables.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
sys.path.insert(0, str(PORT / 'launcher'))
import bbport_launcher_win as core


class DlssModelTableTests(unittest.TestCase):
    """scripts/dlss_models.tsv is the one copy of the DLSS model choices."""

    def test_generated_files_match_the_table(self):
        for path, text in gen.outputs().items():
            with self.subTest(path=path.name):
                self.assertEqual(path.read_text(encoding='utf-8').replace('\r\n', '\n'), text,
                                 'out of date: run python bloodborne_pc/scripts/gen_settings_tables.py')

    def test_saved_indices_keep_their_model(self):
        # bbport.ini and the in-game menu store the index: a model never moves.
        rows, _ = gen.read_table()
        self.assertEqual({row['ini']: row['index'] for row in rows},
                         {'default': 0, 'K': 1, 'J': 2, 'M': 3, 'L': 4, 'auto': 5})

    def test_launcher_uses_the_table(self):
        rows, directives = gen.read_table()
        self.assertEqual([value for value, _ in core.DLSS_MODELS], [row['ini'] for row in rows])
        self.assertEqual(core.DLSS_MODELS[0][0], 'auto')
        self.assertEqual(core.DLSS_MODEL_HELP, directives['help'])

    def test_no_copies_left_in_the_sources(self):
        rows, directives = gen.read_table()
        for name in ('launcher/bbport_launcher_win.py', 'launcher/bbport_launcher_backend.py',
                     'gpu/shim/bbport_overlay.cpp', 'gpu/shim/bbport_settings.cpp',
                     'gpu/shim/bbport_settings.h', 'gpu/shim/bbport_nvidia_gpu.h'):
            source = (PORT / name).read_text(encoding='utf-8')
            with self.subTest(source=name):
                for row in rows:
                    for label in (f"{row['name']}: {row['summary']}", f"{row['name']} - {row['summary']}"):
                        self.assertNotIn(label, source)
                self.assertNotIn(directives['help'][:60], source)
                self.assertIsNone(re.search(r'enum DlssModel\s*:', source))


if __name__ == '__main__':
    unittest.main()
