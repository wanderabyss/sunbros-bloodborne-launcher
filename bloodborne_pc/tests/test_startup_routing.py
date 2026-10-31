from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_startup as startup

DONE = {'setupCompleted': True, 'setupSkipped': False, 'setupVersion': startup.SETUP_VERSION,
        'launchDirectly': True}


def choose(settings, args=(), keys=False, game=True, saves=True):
    return startup.choose_route(settings, list(args), keys, game, saves)


class RouteTests(unittest.TestCase):
    def test_fresh_install_opens_wizard_even_with_overrides(self):
        for args in ((), ('--launcher',)):
            self.assertEqual(choose({}, args, game=False)['page'], 'Setup')
        self.assertEqual(choose({}, keys=True)['page'], 'Setup')

    def test_completed_setup_launches_directly(self):
        self.assertEqual(choose(DONE)['mode'], 'launcher')

    def test_skipped_setup_without_game_opens_game_page(self):
        route = choose({**DONE, 'setupCompleted': False, 'setupSkipped': True}, game=False)
        self.assertEqual((route['mode'], route['page'], route['problem'], route['step']),
                         ('launcher', 'Game', 'game', 1))

    def test_missing_game_folder_shows_fix_banner(self):
        self.assertEqual(choose(DONE, game=False)['problem'], 'game')
        route = choose(DONE, saves=False)
        self.assertEqual((route['page'], route['problem'], route['step']), ('Game', 'saves', 2))

    def test_overrides_open_launcher(self):
        self.assertEqual(choose(DONE, keys=True), {'mode': 'launcher', 'page': 'Home', 'step': 0, 'problem': ''})
        self.assertEqual(choose(DONE, ['--launcher'])['page'], 'Home')
        self.assertEqual(choose(DONE, ['--setup'])['page'], 'Setup')
        self.assertEqual(choose({**DONE, 'launchDirectly': False})['page'], 'Home')

    def test_newer_wizard_version_prompts_again(self):
        self.assertEqual(choose({**DONE, 'setupVersion': startup.SETUP_VERSION - 1})['page'], 'Setup')


class MigrationTests(unittest.TestCase):
    def test_existing_user_with_game_is_marked_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'eboot.bin').write_bytes(b'\0')
            saved = {'game_dir': folder, 'setup_seen': True}
            self.assertTrue(startup.migrate(saved, saved))
            self.assertTrue(saved['setupCompleted'])
            self.assertNotIn('setup_seen', saved)
            self.assertEqual(choose(saved)['mode'], 'launcher')
            self.assertFalse(startup.migrate(saved, saved), 'migration must run only once')

    def test_dismissed_old_wizard_without_game_counts_as_skipped(self):
        saved = {'game_dir': '', 'setup_seen': True}
        startup.migrate(saved, saved)
        self.assertTrue(saved['setupSkipped'])
        self.assertFalse(saved.get('setupCompleted'))

    def test_fresh_install_is_not_migrated(self):
        self.assertFalse(startup.migrate({}, {}))


class WritableTests(unittest.TestCase):
    def test_missing_folder_under_writable_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(startup.writable(Path(folder) / 'user' / 'nested'))
            (Path(folder) / 'file').write_text('x')
            self.assertFalse(startup.writable(Path(folder) / 'file'))
            self.assertEqual(list(Path(folder).glob('.bbport-check-*')), [])


if __name__ == '__main__':
    unittest.main()
