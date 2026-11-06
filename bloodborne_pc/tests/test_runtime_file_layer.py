"""Builds and runs test_runtime_file_layer.c with MSYS2's clang (Windows; skipped without it)."""
from paths import ROOT
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

MSYS2 = Path(os.environ.get('MSYS2_ROOT', r'C:\msys64')) / 'clang64' / 'bin'
CLANG = MSYS2 / 'clang.exe'


@unittest.skipUnless(os.name == 'nt' and CLANG.is_file(), 'needs MSYS2 CLANG64')
class FileLayerTests(unittest.TestCase):
    def test_files_over_the_game(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'file-layer-test.exe'
            work = Path(folder) / 'work'
            work.mkdir()
            env = {**os.environ, 'PATH': f'{MSYS2}{os.pathsep}{os.environ.get("PATH", "")}'}
            built = subprocess.run([str(CLANG), '-std=gnu11', '-O1', '-pthread', '-I', str(ROOT / 'src'),
                                    str(ROOT / 'tests' / 'test_runtime_file_layer.c'), '-o', str(exe)],
                                   capture_output=True, text=True, env=env)
            self.assertEqual(built.returncode, 0, built.stderr)
            done = subprocess.run([str(exe), work.as_posix()], capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn('PASS', done.stdout)


if __name__ == '__main__':
    unittest.main()
