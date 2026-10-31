"""Save backups in the launcher: the backend's guards and worker, and the Settings section."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PySide6.QtCore import Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

import test_home_dashboard_qml as home_tests
from test_save_backups import read_saves, write_saves

backend_module = home_tests.backend_module
backups = backend_module.save_backups


class BackendFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home_tests.HomeDashboardTests.setUpClass()

    def setUp(self):
        dialog = mock.patch.object(QMessageBox, 'information')
        dialog.start()
        self.addCleanup(dialog.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        write_saves(self.root)
        self.fixture = home_tests.HomeDashboardTests()
        self.fixture.setUp()
        self.fixture.view.hide()
        self.backend = self.fixture.backend
        self.backend.app['user_dir'] = str(self.root)
        summary = mock.patch.object(backend_module.LauncherBackend, '_save_summary', return_value='Hunter Lv 40')
        summary.start()
        self.addCleanup(summary.stop)

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()
        self.fixture.app.processEvents()

    def wait_idle(self, timeout=10):
        end = time.monotonic() + timeout
        while self.backend.saveBackupBusy and time.monotonic() < end:
            # time.sleep lets the worker run (QTest.qWait keeps Python's lock and starves it).
            time.sleep(0.01)
            self.fixture.app.processEvents()
        self.assertFalse(self.backend.saveBackupBusy, 'the save backup worker never finished: ' + self.backend.saveBackupStatus)


class SaveBackupBackendTests(BackendFixture):
    def test_backup_now_runs_in_a_worker_and_lists_the_result(self):
        self.backend.backupSavesNow('first')
        self.wait_idle()
        self.assertTrue(self.backend.saveBackupStatus.startswith('Backed up 4 files'))
        listed = self.backend.saveBackups
        self.assertEqual(len(listed), 1)
        self.assertEqual((listed[0]['label'], listed[0]['kind'], listed[0]['summary']),
                         ('first', 'manual', 'Hunter Lv 40'))

    def test_saves_are_not_touched_while_the_game_runs(self):
        info = backups.create_backup(self.root)
        self.backend.process = object()  # a running game
        try:
            before = read_saves(self.root)
            self.backend.backupSavesNow('')
            self.assertFalse(self.backend.saveBackupBusy)
            self.assertIn('Close the game', self.backend.saveBackupStatus)
            self.backend.restoreSaveBackup(info['name'])
            self.assertFalse(self.backend.saveBackupBusy)
            self.assertEqual(read_saves(self.root), before)
            self.assertEqual(len(backups.list_backups(self.root)), 1)
            # Deleting a backup does not touch the live saves, so it is allowed.
            self.backend.deleteSaveBackup(info['name'])
            self.assertEqual(backups.list_backups(self.root), [])
        finally:
            self.backend.process = None

    def test_restore_makes_a_safety_backup_and_reloads_the_profile(self):
        info = backups.create_backup(self.root, 'good')
        original = read_saves(self.root)
        write_saves(self.root, 'later')
        with mock.patch.object(backend_module.LauncherBackend, 'refresh_profile_data') as reload:
            self.backend.restoreSaveBackup(info['name'])
            self.wait_idle()
            reload.assert_called_once()
        self.assertEqual(read_saves(self.root), original)
        self.assertIn('before restore', self.backend.saveBackupStatus)
        kinds = sorted(item['kind'] for item in self.backend.saveBackups)
        self.assertEqual(kinds, ['manual', 'safety'])

    def test_game_exit_backs_up_in_the_background_and_prunes(self):
        for _ in range(backups.KEEP_AUTO):
            backups.create_backup(self.root, kind='auto')
        self.backend._game_started = True
        started = time.monotonic()
        self.backend._receive_exit(0)
        self.assertLess(time.monotonic() - started, 2)
        self.assertTrue(self.backend.saveBackupBusy)  # the zip is the worker's job
        self.wait_idle()
        self.assertIn('after playing', self.backend.saveBackupStatus)
        autos = [b for b in backups.list_backups(self.root) if b['kind'] == 'auto']
        self.assertEqual(len(autos), backups.KEEP_AUTO)

    def test_game_exit_respects_the_setting_and_a_failed_start(self):
        self.backend.app['backup_after_play'] = False
        self.backend._game_started = True
        self.backend._receive_exit(0)
        self.backend.app['backup_after_play'] = True
        self.backend._game_started = False
        self.backend._receive_exit(1)
        self.assertFalse(self.backend.saveBackupBusy)
        self.assertEqual(backups.list_backups(self.root), [])

    def test_play_waits_for_a_running_backup(self):
        self.backend._save_backup_busy = True
        try:
            with mock.patch.object(backend_module.subprocess, 'Popen') as popen, \
                    mock.patch.object(backend_module.core, 'game_info', return_value=('x', '01.09')):
                self.backend.play()
            popen.assert_not_called()
            self.assertIn('save backup', self.backend.notice)
        finally:
            self.backend._save_backup_busy = False

    def test_setting_row_is_in_the_save_backups_section(self):
        self.assertTrue(backend_module.core.APP_DEFAULTS['backup_after_play'])
        keys = [field['key'] for field in self.backend.sectionFields('Game & Saves', 'Save backups')]
        self.assertEqual(keys, ['backup_after_play'])


class SaveBackupSectionTests(BackendFixture):
    def setUp(self):
        super().setUp()
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('launcher', self.backend)
        path = Path(backend_module.__file__).parent / 'qml/Main.qml'
        self.engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.engine.rootObjects(), 'Main.qml did not load')
        self.window = self.engine.rootObjects()[0]
        QTest.qWait(50)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        super().tearDown()

    def items(self):
        pending, result = [self.window.contentItem()], []
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(item.childItems())
        self._retained = result
        return result

    def item(self, name):
        for item in self.items():
            if item.objectName() == name and item.isVisible():
                return item
        self.fail('Missing visible item: ' + name)

    def click(self, name):
        item = self.item(name)
        self.assertTrue(item.isEnabled(), name + ' is disabled')
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        self.fixture.app.processEvents()
        QTest.qWait(20)

    def open_section(self):
        self.click('primary_Settings')
        editor = next(item for item in self.items() if item.objectName() == 'settingsWorkspace'
                      and item.isVisible())
        self.assertIn('Save backups', [str(s) for s in self.backend.categorySections('Game & Saves')])
        self.click('section_Save_backups')
        QTest.qWait(50)
        return editor

    def test_section_lists_backups_and_wires_its_buttons(self):
        backups.create_backup(self.root, 'existing')
        self.open_section()
        self.assertTrue(self.item('saveBackupsSection').isVisible())
        self.assertEqual(len(self.backend.saveBackups), 1)  # listed when the section opened
        self.item('saveBackupRow_0')

        self.item('saveBackupLabel').setProperty('text', 'from the test')
        self.click('saveBackupNow')
        self.wait_idle()
        QTest.qWait(50)
        labels = [b['label'] for b in self.backend.saveBackups]
        self.assertIn('from the test', labels)

        with mock.patch.object(backend_module.os, 'startfile', create=True) as startfile:
            self.click('saveBackupOpenFolder')
        startfile.assert_called_once_with(str(self.root / 'save-backups'))

        # Delete asks in the row first; Cancel keeps the backup.
        self.click('saveBackupDelete_0')
        self.click('saveBackupCancel_0')
        self.assertEqual(len(self.backend.saveBackups), 2)
        self.click('saveBackupDelete_0')
        self.click('saveBackupConfirm_0')
        self.assertEqual(len(self.backend.saveBackups), 1)

        # Restore also asks first, then backs up the current saves.
        write_saves(self.root, 'changed')
        self.click('saveBackupRestore_0')
        self.click('saveBackupConfirm_0')
        self.wait_idle()
        self.assertTrue(self.backend.saveBackupStatus.startswith('Restored'), self.backend.saveBackupStatus)
        self.assertIn('safety', [b['kind'] for b in self.backend.saveBackups])

    def test_buttons_are_blocked_with_a_notice_while_the_game_runs(self):
        backups.create_backup(self.root)
        self.open_section()
        self.backend.process = object()
        try:
            self.backend.runningChanged.emit()
            QTest.qWait(30)
            self.assertTrue(self.item('saveBackupsRunningNotice').isVisible())
            self.assertFalse(self.item('saveBackupNow').isEnabled())
            self.assertFalse(self.item('saveBackupRestore_0').isEnabled())
            self.assertTrue(self.item('saveBackupDelete_0').isEnabled())
        finally:
            self.backend.process = None
            self.backend.runningChanged.emit()


if __name__ == '__main__':
    unittest.main()
