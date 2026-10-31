"""Exercise the actual guided Co-op page, including generic-row duplication."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module


class CoopSettingsQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['coop-settings-test'])
        # Main.qml normally loads the title face. Headless Windows platforms
        # also need the UI face registered explicitly for readable previews.
        fonts = [Path(backend_module.__file__).parent / 'assets' / 'ui' / 'bloodborne-font.ttf']
        if os.name == 'nt':
            fonts.append(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf')
        for font in fonts:
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        # Isolate the real QObject backend from user files, network and startup jobs.
        patches = [
            mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value={}),
            mock.patch.object(backend_module.core, 'load_ini',
                              return_value=(dict(backend_module.core.INI_DEFAULTS), [])),
            mock.patch.object(backend_module.core, 'remembered_update', return_value=None),
            mock.patch.object(backend_module.LauncherBackend, 'refresh_profile_data'),
            mock.patch.object(backend_module.LauncherBackend, 'refresh_addons'),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.backend = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.backend.app.update(coop_name='RegressionHunter', coop_password='dummy-password',
                                coop_server='public')
        self.view = QQuickView()
        self.view.rootContext().setContextProperty('launcher', self.backend)
        self.view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self.view.resize(1700, 1500)
        self.view.setInitialProperties({'category': 'Co-op', 'section': 'Seamless co-op'})
        source = Path(backend_module.__file__).parent / 'qml' / 'SettingsWorkspace.qml'
        self.view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(self.view.status(), QQuickView.Status.Ready,
                         '\n'.join(e.toString() for e in self.view.errors()))
        self.view.show()
        QTest.qWait(80)
        self.root = self.view.rootObject()

    def tearDown(self):
        self.view.close()
        self.view.setSource(QUrl())
        self.app.processEvents()

    def editor(self, name):
        item = self.root.findChild(QObject, name)
        self.assertIsNotNone(item, name)
        return item

    def click(self, name):
        item = self.editor(name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        from PySide6.QtCore import Qt
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, point)
        self.app.processEvents()

    def page_items(self):
        # Repeater delegates have a visual parent but need not be QObject
        # children of that parent. Traverse both trees to catch duplicate rows.
        pending, seen, result = [self.root], set(), []
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            result.append(item)
            pending.extend(item.children())
            if hasattr(item, 'childItems'):
                pending.extend(item.childItems())
        return result

    def test_account_and_server_have_one_visible_editor(self):
        items = self.page_items()
        for key, value in [('coop_name', 'RegressionHunter'), ('coop_password', 'dummy-password')]:
            with self.subTest(key=key):
                editors = [item for item in items if item.inherits('QQuickTextInput')
                           and item.property('visible') and item.property('text') == value]
                self.assertEqual(len(editors), 1, f'{key} rendered more than once')
        self.editor('coopSetupPanel').setProperty('step', 1)
        self.app.processEvents()
        items = self.page_items()
        servers = [item for item in items if item.inherits('QQuickComboBox')
                   and item.property('visible') and 'play.seamlesshunt.com' in
                   str(item.property('currentText') or '')]
        self.assertEqual(len(servers), 1, 'Server selector rendered more than once')

    def test_search_focus_and_external_changes_reach_guided_editors(self):
        self.assertEqual(self.backend.sectionFields('Co-op', 'Seamless co-op'), [])
        result = self.backend.searchSettings('co-op password')[0]
        self.assertEqual((result['category'], result['section'], result['key']),
                         ('Co-op', 'Seamless co-op', 'coop_password'))
        self.root.setProperty('targetKey', result['key'])
        self.assertTrue(QMetaObject.invokeMethod(self.root, 'focusTarget'))
        QTest.qWait(10)
        self.assertTrue(self.editor('coopPasswordEditor').property('activeFocus'))
        # Updating inactive controls from a settings load must not create a second owner.
        self.backend.app.update(coop_name='ReloadedHunter', coop_server='tailscale')
        self.backend.changed.emit()
        self.app.processEvents()
        self.assertEqual(self.editor('coopNameEditor').property('text'), 'ReloadedHunter')
        self.assertEqual(self.editor('coopServerEditor').property('currentIndex'), 0)

    def test_guided_steps_require_account_and_connection(self):
        setup = self.editor('coopSetupPanel')
        self.backend.app.update(coop_name='', coop_password='')
        self.backend.changed.emit()
        self.assertFalse(self.editor('coopAccountNext').property('enabled'))
        self.backend.app.update(coop_name='Hunter', coop_password='test-password',
                                coop_server='tailscale', coop_invite='')
        self.backend.changed.emit()
        self.assertTrue(self.editor('coopAccountNext').property('enabled'))
        self.click('coopAccountNext')
        self.assertEqual(setup.property('step'), 1)
        # Play co-op is on the Connection step itself (no separate Launch step since 4.2.7).
        self.assertFalse(self.editor('coopGuidedPlay').property('enabled'))
        self.backend.app['coop_server'] = 'public'
        self.backend.changed.emit()
        self.assertTrue(self.editor('coopGuidedPlay').property('enabled'))
        self.assertFalse(self.editor('coopDownload').isVisible())  # on the Account step only
        self.backend._coop_busy = True
        self.backend.coopChanged.emit()
        self.assertFalse(self.editor('coopGuidedPlay').property('enabled'))

    def test_invite_search_reveals_private_connection_step(self):
        self.backend.app.update(coop_server='tailscale', coop_invite='')
        self.backend.changed.emit()
        self.root.setProperty('targetKey', 'coop_invite')
        self.assertTrue(QMetaObject.invokeMethod(self.root, 'focusTarget'))
        QTest.qWait(10)
        self.assertEqual(self.editor('coopSetupPanel').property('step'), 1)
        self.assertTrue(self.editor('coopInviteEditor').property('activeFocus'))

    def test_join_requires_stopping_an_existing_host(self):
        self.backend.app.update(coop_server='tailscale', coop_invite='fixture-invite')
        self.backend.changed.emit()
        setup = self.editor('coopSetupPanel')
        setup.setProperty('step', 1)
        setup.setProperty('privateRole', 'join')
        self.assertTrue(self.editor('coopGuidedPlay').property('enabled'))
        self.backend._coop_host = mock.Mock(running=True)
        self.backend.coopChanged.emit()
        self.assertFalse(self.editor('coopGuidedPlay').property('enabled'))


if __name__ == '__main__':
    unittest.main()
