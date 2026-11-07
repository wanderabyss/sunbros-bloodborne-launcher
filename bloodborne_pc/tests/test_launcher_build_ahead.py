"""The launcher makes the game files before Play."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module

PORT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bbport_run_build_ahead', PORT / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class RunScriptTests(unittest.TestCase):
    """run.py's main() itself, with its scripts and the game replaced by records of the calls."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        root = Path(temp.name)
        self.user = root / 'user'
        self.game = root / 'game'
        self.game.mkdir()
        (self.game / 'eboot.bin').write_bytes(b'')
        probe = root / 'bin' / 'bb-probe.exe'
        probe.parent.mkdir()
        probe.write_bytes(b'')
        (probe.parent / 'SDL3.dll').write_bytes(b'')
        (root / 'bbport.ini').write_text('', encoding='utf-8')
        (root / 'out').mkdir()
        (root / 'out' / 'eboot.elf').write_bytes(b'')
        self.calls = []
        environ = {key: value for key, value in os.environ.items() if not key.startswith('BB_')}
        environ.update(BB_DATA_DIR=str(root), BB_GAME_DIR=str(self.game), BB_PROBE=str(probe),
                       BB_USER_DIR=str(self.user), BB_ONLINE='1', BB_SKIP_GAME_CHECK='1')

        def record(name):
            return mock.Mock(side_effect=lambda *a, **k: self.calls.append(name))

        game_process = mock.Mock()
        game_process.wait.return_value = 0
        game_process.poll.return_value = 0

        def popen(*args, **kwargs):
            self.calls.append('game')
            return game_process

        def script(name, *args, **kwargs):
            self.calls.append(name)
            return str(self.game) if name == 'mods.py' else ''

        sys.path.insert(0, str(PORT / 'scripts'))
        import aspect_ratio
        import game_check
        import patches as game_patches
        patches = [mock.patch.dict(os.environ, environ, clear=True),
                   mock.patch.object(sys, 'argv', ['run.py']),
                   mock.patch.object(run, 'missing_port_files', return_value=[]),
                   mock.patch.object(run, 'run_script', script),
                   mock.patch.object(run, 'shader_prebuild'),
                   mock.patch.object(run, 'low_vram_mb', return_value=0),
                   mock.patch.object(run, 'start_companions', return_value=[]),
                   mock.patch.object(run, 'sojin_saves', record('saves')),
                   mock.patch.object(run, 'online_overrides', record('online')),
                   mock.patch.object(run, 'dlss5_environment', record('dlss5')),
                   mock.patch.object(run.subprocess, 'Popen', popen),
                   mock.patch.object(game_check, 'missing_files', return_value=[]),
                   mock.patch.object(game_patches, 'eboot_matches_patches', return_value=True),
                   mock.patch.object(aspect_ratio, 'segment_fingerprint', return_value='')]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_prepare_only_makes_the_files_and_stops_before_saves_online_and_the_game(self):
        os.environ['BB_PREPARE_ONLY'] = '1'
        self.assertEqual(run.main(), 0)
        self.assertIn('patches.py', self.calls)
        for later in ('saves', 'online', 'dlss5', 'game'):
            self.assertNotIn(later, self.calls)
        self.assertFalse(self.user.exists(), 'the save folder is for a real start')

    def test_a_real_start_converts_saves_before_the_game(self):
        self.assertEqual(run.main(), 0)
        self.assertIn('patches.py', self.calls)
        steps = [call for call in self.calls if call in ('online', 'saves', 'dlss5', 'game')]
        self.assertEqual(steps, ['online', 'saves', 'dlss5', 'game'])


class BuildAheadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = [mock.patch.object(backend_module.LauncherBackend, name)
                   for name in ('refresh_profile_data', 'refresh_addons', 'start_background_checks',
                                '_write', '_sync_from_disk', '_remember_written', '_apply_neural_settings')]
        patches += [mock.patch.object(backend_module.core, 'game_info', return_value={'title': 'x'}),
                    mock.patch.object(backend_module.core, 'game_environment', return_value={'A': '1'}),
                    mock.patch.object(backend_module.core, 'GameJob'),
                    mock.patch.object(backend_module.coop, 'restore_vanilla_bells', return_value=None),
                    mock.patch.object(backend_module.threading, 'Thread')]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        popen = mock.patch.object(backend_module.subprocess, 'Popen')
        self.popen = popen.start()
        self.addCleanup(popen.stop)
        logged = mock.patch('builtins.open', mock.mock_open())
        logged.start()
        self.addCleanup(logged.stop)
        self.backend = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.backend.connect_workers()
        self.backend._build_ahead_enabled = True
        self.backend.app['game_dir'] = 'game'
        self.backend.app['user_dir'] = 'user'
        self.addCleanup(self.backend._build_timer.stop)

    def builds(self):
        return [call for call in self.popen.call_args_list if call.kwargs['env'].get('BB_PREPARE_ONLY') == '1']

    def games(self):
        return [call for call in self.popen.call_args_list if 'BB_PREPARE_ONLY' not in call.kwargs['env']]

    def test_nothing_is_built_until_a_launcher_window_asks(self):
        self.backend._build_ahead_enabled = False
        self.backend._schedule_build()
        self.assertFalse(self.backend._build_timer.isActive())

    def test_a_change_schedules_one_build_at_low_priority(self):
        self.backend._schedule_build()
        self.assertTrue(self.backend._build_timer.isActive())
        self.backend._begin_build()
        self.assertEqual(len(self.builds()), 1)
        self.assertTrue(self.backend.buildingAhead)
        flags = self.builds()[0].kwargs['creationflags']
        below = getattr(backend_module.subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        self.assertEqual(flags & below, below)

    def test_no_build_while_the_game_runs_or_without_a_game(self):
        self.backend.process = mock.Mock()
        self.backend._begin_build()
        self.assertEqual(self.builds(), [])
        self.backend.process = None
        with mock.patch.object(backend_module.core, 'game_info', return_value=None):
            self.backend._begin_build()
        self.assertEqual(self.builds(), [])

    def test_play_during_a_build_keeps_it_and_starts_the_game_after(self):
        self.backend._begin_build()
        self.backend.play()
        self.assertEqual(self.games(), [], 'the game must wait for the build')
        self.assertTrue(self.backend.running)
        self.assertFalse(self.backend.buildingAhead)
        self.assertEqual(self.backend.notice, 'Preparing the game…')
        self.backend._receive_build_finished(0)
        self.assertEqual(len(self.games()), 1)
        self.assertTrue(self.backend.running)
        self.addCleanup(setattr, self.backend, 'process', None)

    def test_a_failed_build_still_starts_the_game_which_reports_it(self):
        self.backend._begin_build()
        self.backend.play()
        self.backend._receive_build_finished(1)
        self.assertEqual(len(self.games()), 1)
        self.addCleanup(setattr, self.backend, 'process', None)

    def test_stop_during_a_queued_play_ends_it_without_a_game_or_an_error(self):
        finished = []
        self.backend.gameFinished.connect(lambda code, started: finished.append((code, started)))
        self.backend._begin_build()
        self.backend.play()
        job = self.backend.job
        self.backend.stop()
        job.terminate.assert_called_once()
        self.backend._receive_build_finished(1)
        self.assertEqual(self.games(), [])
        self.assertFalse(self.backend.running)
        self.assertEqual(self.backend.notice, 'The game was stopped.')
        self.assertEqual(finished, [(0, False)])

    def test_a_change_during_a_build_builds_again_afterwards(self):
        self.backend._begin_build()
        self.backend._begin_build()
        self.assertEqual(len(self.builds()), 1)
        self.backend._receive_build_finished(0)
        self.assertTrue(self.backend._build_timer.isActive())

    def test_closing_the_launcher_ends_a_build(self):
        self.backend._begin_build()
        job = self.backend._build_job
        self.backend.shutdown_build_ahead()
        job.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
