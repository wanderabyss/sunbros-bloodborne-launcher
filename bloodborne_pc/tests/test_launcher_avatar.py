from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core
from bbport_launcher_backend import LauncherBackend


class LauncherAvatarTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.user_dir = self.root / 'user'
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self._orig_config_file = core.CONFIG_FILE
        self._orig_config_dir = core.CONFIG_DIR
        core.CONFIG_DIR = self.root
        core.CONFIG_FILE = self.root / 'settings.json'

    def tearDown(self):
        core.CONFIG_FILE = self._orig_config_file
        core.CONFIG_DIR = self._orig_config_dir
        self.temp_dir.cleanup()

    def test_default_avatar_fallback(self):
        backend = LauncherBackend(route=None)
        backend.app = {'custom_avatar_path': ''}
        backend.app['user_dir'] = str(self.user_dir)
        # Should be empty string when no custom avatar is placed
        self.assertEqual(backend.userAvatar, '')

    def test_custom_avatar_path_resolution(self):
        avatar_file = self.user_dir / 'my_hunter.png'
        avatar_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        backend = LauncherBackend(route=None)
        backend.app = {'custom_avatar_path': str(avatar_file)}
        backend.app['user_dir'] = str(self.user_dir)

        self.assertEqual(backend.userAvatar, avatar_file.as_uri())

    def test_user_dir_avatar_png_auto_detection(self):
        avatar_file = self.user_dir / 'avatar.png'
        avatar_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        backend = LauncherBackend(route=None)
        backend.app = {'custom_avatar_path': ''}
        backend.app['user_dir'] = str(self.user_dir)

        self.assertEqual(backend.userAvatar, avatar_file.as_uri())

    def test_reset_custom_avatar(self):
        avatar_file = self.user_dir / 'avatar.png'
        avatar_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        backend = LauncherBackend(route=None)
        backend.app = {'custom_avatar_path': str(avatar_file)}
        backend.app['user_dir'] = str(self.user_dir)

        backend.resetCustomAvatar()
        self.assertFalse(avatar_file.exists())
        self.assertEqual(backend.app.get('custom_avatar_path'), '')
        self.assertEqual(backend.userAvatar, '')


if __name__ == '__main__':
    unittest.main()
