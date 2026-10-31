# SPDX-License-Identifier: GPL-2.0-or-later
"""launcher/bbport_fsr4vk.py: where the provider goes and what counts as installed (no network)."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'launcher'))
import bbport_fsr4vk  # noqa: E402


class Fsr4VkFetchTest(unittest.TestCase):
    def test_default_dir_follows_env_then_package_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('BB_FSR4VK_DIR', None)
                self.assertEqual(bbport_fsr4vk.default_dir(port), port / 'out' / 'fsr4vk')
                (port / 'bin').mkdir()
                (port / 'bin' / 'bb-probe.exe').write_bytes(b'')
                self.assertEqual(bbport_fsr4vk.default_dir(port), port / 'bin' / 'fsr4vk')
                os.environ['BB_FSR4VK_DIR'] = str(port / 'elsewhere')
                self.assertEqual(bbport_fsr4vk.default_dir(port), port / 'elsewhere')

    def test_files_ok_needs_every_pinned_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self.assertFalse(bbport_fsr4vk.files_ok(target))
            data = b'not the provider'
            pinned = [(m, n, len(data), hashlib.sha256(data).hexdigest()) for m, n, _, _ in bbport_fsr4vk.FILES]
            with mock.patch.object(bbport_fsr4vk, 'FILES', tuple(pinned)):
                for _, name, _, _ in pinned:
                    (target / name).parent.mkdir(parents=True, exist_ok=True)
                    (target / name).write_bytes(data)
                self.assertTrue(bbport_fsr4vk.files_ok(target))
                (target / pinned[0][1]).write_bytes(data + b'!')
                self.assertFalse(bbport_fsr4vk.files_ok(target))

    def test_fetch_skips_download_when_installed(self):
        with mock.patch.object(bbport_fsr4vk, 'files_ok', return_value=True), \
                mock.patch.object(bbport_fsr4vk, '_download') as download:
            bbport_fsr4vk.fetch(Path('unused'))
        download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
