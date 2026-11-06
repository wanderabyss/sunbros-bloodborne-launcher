from paths import ROOT
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('run', ROOT / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class ShaderPrebuildTests(unittest.TestCase):
    def test_the_code_is_extracted_once_while_its_sources_stay_as_they_are(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game, out = root / 'game', root / 'out'
            (game / 'dvdroot_ps4' / 'shader').mkdir(parents=True)
            (game / 'dvdroot_ps4' / 'shader' / 'a.shaderbnd.dcx').write_bytes(b'shaders')
            out.mkdir()
            (out / 'eboot.elf').write_bytes(b'elf')

            def extract(_name, _game, _elf, code, optional):
                Path(code).mkdir(parents=True, exist_ok=True)
                (Path(code) / 'a.bin').write_bytes(b'code')
                return ''
            with mock.patch.object(run, 'run_script', side_effect=extract) as script:
                run.shader_prebuild(game, out, {})
                self.assertEqual(script.call_count, 1)
                run.shader_prebuild(game, out, {})
                self.assertEqual(script.call_count, 1)
                # A new eboot.elf is a new stamp: prepare.py must not rewrite it without cause.
                os.utime(out / 'eboot.elf', (1, 1))
                run.shader_prebuild(game, out, {})
                self.assertEqual(script.call_count, 2)


class RunScriptTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        port = Path(folder.name)
        (port / 'scripts').mkdir()
        (port / 'scripts' / 'ok.py').write_text("print('made')\n")
        (port / 'scripts' / 'fails.py').write_text("raise SystemExit(3)\n")
        for patch in (mock.patch.object(run, 'PORT', port), mock.patch.object(run, 'no_console', lambda: 0)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_success_gives_the_output_or_an_empty_string(self):
        self.assertEqual(run.run_script('ok.py', capture=True), 'made\n')
        self.assertEqual(run.run_script('ok.py', capture=True, optional=True), 'made\n')

    def test_a_failure_stops_the_start_unless_the_script_is_optional(self):
        # Issue #8: the PC enhancements' failure stopped the game.
        with self.assertRaises(SystemExit) as stop:
            run.run_script('fails.py', capture=True)
        self.assertEqual(stop.exception.code, 3)
        self.assertIsNone(run.run_script('fails.py', capture=True, optional=True))

    def test_an_incomplete_port_says_what_is_missing(self):
        # Issue #118: a repack without scripts/game_check.py stopped with a traceback.
        self.assertEqual(run.missing_port_files(ROOT), [])
        missing = run.missing_port_files()
        self.assertIn('scripts\\game_check.py', missing)
        text = run.explain_missing_port_files(missing)
        self.assertIn('scripts\\game_check.py', text)
        self.assertIn(f'{len(missing) - 1} more', text)
        self.assertIn(run.RELEASES, text)


if __name__ == '__main__':
    unittest.main()
