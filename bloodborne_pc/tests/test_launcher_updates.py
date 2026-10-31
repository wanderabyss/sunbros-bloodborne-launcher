import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core


class QuietUpdateCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        cache = Path(self.directory.name) / 'update-check.json'
        for name, value in {'CONFIG_DIR': cache.parent, 'UPDATE_CACHE': cache,
                            'CURRENT_RELEASE_TAG': 'qml-launcher-preview-8', 'VERSION': '1.6.12',
                            'CUSTOM_BUILD': ''}.items():
            patcher = patch.object(core, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.cache = cache

    def reply(self, tag):
        release = {'tag_name': tag, 'html_url': 'https://example.invalid/page',
                   'assets': [{'name': 'bbport-windows.zip', 'browser_download_url': 'https://example.invalid/zip'}]}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, *args): return json.dumps(release).encode()
        return patch.object(core.urllib.request, 'urlopen', return_value=Response())

    def test_newer_release_is_remembered_for_the_launcher(self):
        with self.reply('qml-launcher-preview-9'):
            self.assertTrue(core.quiet_update_check({'check_updates': True}, now=1000))
        self.assertEqual(core.remembered_update(), ('qml-launcher-preview-9', 'https://example.invalid/zip',
                                                    'https://example.invalid/page'))

    def test_a_custom_build_is_not_offered_official_releases(self):
        with patch.object(core, 'CUSTOM_BUILD', 'BBSC 0.0.2'), self.reply('qml-launcher-preview-9'):
            core.quiet_update_check({'check_updates': True}, now=1000)
            self.assertFalse(core.release_is_newer('qml-launcher-preview-9'))
            self.assertIsNone(core.remembered_update())

    def test_current_or_older_release_is_not_offered(self):
        with self.reply('qml-launcher-preview-8'):
            core.quiet_update_check({'check_updates': True})
        self.assertIsNone(core.remembered_update())

    def test_release_notes_are_kept_with_the_check(self):
        release = {'tag_name': 'v2.0.0', 'html_url': 'https://example.invalid/page', 'published_at': '2026-10-30T10:00:00Z',
                   'body': '### New\r\n\r\n- one', 'assets': []}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, *args): return json.dumps(release).encode()
        with patch.object(core.urllib.request, 'urlopen', return_value=Response()):
            core.latest_release()
        self.assertEqual(core.cached_release_notes('v2.0.0'), ('### New\n\n- one', '2026-10-30'))
        self.assertEqual(core.cached_release_notes('v3.0.0'), ('', ''))

    def test_this_versions_section_comes_from_release_notes(self):
        folder = Path(self.directory.name) / 'port'
        folder.mkdir()
        (folder / 'Release_Notes.md').write_text(
            '# Release Notes\n\n## [1.6.12+build1] — 2026-10-29\n### Title\n\n- change\n\n'
            '## [1.6.11+build0] — 2026-10-28\n- older\n', encoding='utf-8')
        with patch.object(core, 'PORT_DIR', folder):
            self.assertEqual(core.release_notes_section('1.6.12'), '### Title\n\n- change')
            self.assertEqual(core.release_notes_section('1.6.11'), '- older')
            self.assertEqual(core.release_notes_section('9.9.9'), '')

    def test_launcher_shows_the_short_changelog(self):
        written = '### Title\n<!-- launcher:\n- **One:** short.\n-->\n\n- **Long:** details. More.\n'
        self.assertEqual(core.concise_release_notes(written), '- **One:** short.')
        plain = '### Big release\r\n\r\n- **Backups:** a. b.\r\n- **HDR controls.** c\r\n- [changelog](x.md)\r\n'
        self.assertEqual(core.concise_release_notes(plain), '### Big release\n\n- Backups\n- HDR controls')
        many = '\n'.join(f'- **Item {n}:** x' for n in range(9))
        self.assertEqual(core.concise_release_notes(many, limit=3).count('\n- '), 2)

    def test_switched_off_and_throttled(self):
        with self.reply('qml-launcher-preview-9') as urlopen:
            self.assertFalse(core.quiet_update_check({'check_updates': False}))
            self.assertTrue(core.quiet_update_check({'check_updates': True}, now=core.time.time()))
            self.assertFalse(core.quiet_update_check({'check_updates': True}, now=core.time.time() + 60))
            self.assertTrue(core.quiet_update_check({'check_updates': True},
                                                    now=core.time.time() + core.QUIET_CHECK_INTERVAL + 1))
        self.assertEqual(urlopen.call_count, 2)

    def test_network_failure_is_silent_and_corrupt_cache_ignored(self):
        self.cache.write_text('not json', encoding='utf-8')
        self.assertIsNone(core.remembered_update())
        with patch.object(core.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertFalse(core.quiet_update_check({'check_updates': True}))


class InstallUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_backslash_zip_unpacks_into_folders(self):
        archive = self.root / 'update.zip'
        with core.zipfile.ZipFile(archive, 'w') as package:
            for name, data in (('bbport-windows\\_internal\\_ssl.pyd', b'ssl'),
                               ('bbport-windows/scripts/game_check.py', b'check'),
                               ('bbport-windows\\..\\..\\outside.txt', b'no')):
                entry = core.zipfile.ZipInfo('x')
                entry.filename = name  # as written, without zipfile's separator clean-up
                package.writestr(entry, data)
        core.extract_update(archive, self.root / 'new')
        self.assertEqual((self.root / 'new/bbport-windows/_internal/_ssl.pyd').read_bytes(), b'ssl')
        self.assertEqual((self.root / 'new/bbport-windows/scripts/game_check.py').read_bytes(), b'check')
        self.assertFalse((self.root / 'outside.txt').exists())

    def test_new_files_arrive_and_player_files_stay(self):
        new, old = self.root / 'new', self.root / 'old'
        for path, text in (('run.py', 'new'), ('scripts/game_check.py', 'new'), ('user/save', 'packaged')):
            (new / path).parent.mkdir(parents=True, exist_ok=True)
            (new / path).write_text(text)
        for path, text in (('run.py', 'old'), ('user/save', 'mine'), ('bbport.ini', 'mine')):
            (old / path).parent.mkdir(parents=True, exist_ok=True)
            (old / path).write_text(text)
        self.assertEqual(core.copy_release(new, old), [])
        self.assertEqual((old / 'run.py').read_text(), 'new')
        self.assertEqual((old / 'scripts/game_check.py').read_text(), 'new')
        self.assertEqual((old / 'user/save').read_text(), 'mine')
        self.assertEqual((old / 'bbport.ini').read_text(), 'mine')

    @unittest.skipUnless(sys.platform == 'win32', 'an open file blocks deleting it only on Windows')
    def test_update_folder_kept_while_installing(self):
        folder = self.root / 'bbport-update'
        (folder / 'new/bbport-windows/scripts').mkdir(parents=True)
        with patch.object(core, 'UPDATE_DIR', folder):
            with open(core.update_installing_mark(), 'w'):
                self.assertFalse(core.remove_update_folder())
                self.assertTrue((folder / 'new/bbport-windows/scripts').is_dir())
            self.assertTrue(core.remove_update_folder())
            self.assertFalse(folder.exists())


if __name__ == '__main__':
    unittest.main()
