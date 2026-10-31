from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'bloodborne_pc' / 'launcher'))
import bbport_launcher_win as core


class VersionSourceTests(unittest.TestCase):
    """bloodborne_pc/version.txt is the only copy of the version in the source tree."""

    def test_launcher_reads_version_txt(self):
        expected = (ROOT / 'bloodborne_pc' / 'version.txt').read_text(encoding='utf-8').strip()
        self.assertEqual(core.VERSION, expected.split('+')[0])

    def test_package_layout_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'version.txt').write_text('9.8.7\n', encoding='utf-8')
            with patch.object(core, 'PORT_DIR', Path(folder)):
                self.assertEqual(core._read_version(), '9.8.7')

    def test_no_hardcoded_version_in_launcher_sources(self):
        version = core.VERSION
        for name in ('launcher/bbport_launcher_win.py', 'launcher/bbport_launcher_backend.py',
                     'launcher/qml/HomePage.qml'):
            source = (ROOT / 'bloodborne_pc' / name).read_text(encoding='utf-8')
            self.assertNotRegex(source, r"(?m)^VERSION\s*=\s*['\"]\d", name)
            self.assertNotIn(f'"{version}"', source, name)
            self.assertNotIn(f"'{version}'", source, name)

    def test_release_notes_pyproject_and_version_txt_agree(self):
        notes = (ROOT / 'Release_Notes.md').read_text(encoding='utf-8')
        header = re.search(r'(?m)^## \[([0-9.]+)', notes).group(1)
        pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        project = re.search(r'(?m)^version = "([0-9.]+)', pyproject).group(1)
        self.assertEqual(header, core.VERSION)
        self.assertEqual(project, core.VERSION)


if __name__ == '__main__':
    unittest.main()
