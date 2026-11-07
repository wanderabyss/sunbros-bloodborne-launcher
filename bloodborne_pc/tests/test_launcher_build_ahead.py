"""The launcher makes the game files before Play."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module

PORT = Path(__file__).resolve().parents[1]


class RunScriptTests(unittest.TestCase):
    def test_prepare_only_stops_before_saves_online_and_the_game(self):
        source = (PORT / 'run.py').read_text(encoding='utf-8')
        main = source[source.index('def main():'):]
        stop = main.index("env.get('BB_PREPARE_ONLY') == '1'")
        self.assertLess(main.index("run_script('patches.py', '--out'"), stop)
        for later in ('sojin_saves(', 'hunters_dream(env', 'online_overrides(env', 'dlss5_environment(env',
                      'subprocess.Popen(command'):
            self.assertLess(stop, main.index(later), later)


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
