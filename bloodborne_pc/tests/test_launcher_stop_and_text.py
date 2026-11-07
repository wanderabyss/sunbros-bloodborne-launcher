"""The launcher's Stop, and its sharp text."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module
import bbport_launcher_qml as qml_front_end

QML = Path(backend_module.__file__).resolve().parent / 'qml'


class StopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = [mock.patch.object(backend_module.LauncherBackend, name)
                   for name in ('refresh_profile_data', 'refresh_addons', 'start_background_checks',
                                '_write', '_sync_from_disk', '_remember_written')]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.backend = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.backend.process = mock.Mock()

    def test_stop_is_not_reported_as_a_failed_start(self):
        finished = []
        self.backend.gameFinished.connect(lambda code, started: finished.append((code, started)))
        self.backend.job = mock.Mock()
        self.backend.stop()
        self.backend.job.terminate.assert_called_once()
        self.backend._receive_exit(1)
        self.assertEqual(self.backend.notice, 'The game was stopped.')
        self.assertEqual(finished, [(0, False)])

    def test_a_failed_start_still_says_so(self):
        self.backend._receive_exit(3)
        self.assertIn('could not start', self.backend.notice)


class TextSharpnessTests(unittest.TestCase):
    def test_the_launcher_does_not_put_its_font_engine_in_the_games_environment(self):
        source = Path(qml_front_end.__file__).read_text(encoding='utf-8')
        self.assertNotIn("environ['QT_QPA_PLATFORM']", source)
        environ = {}
        self.assertEqual(qml_front_end.qt_arguments(['bloodborne'], environ, 'win32'),
                         ['bloodborne', '-platform', 'windows:fontengine=freetype'])
        self.assertEqual(environ, {})

    def test_a_platform_already_chosen_is_kept(self):
        offscreen = {'QT_QPA_PLATFORM': 'offscreen'}
        self.assertEqual(qml_front_end.qt_arguments(['bloodborne'], offscreen, 'win32'), ['bloodborne'])
        chosen = ['bloodborne', '-platform', 'minimal']
        self.assertEqual(qml_front_end.qt_arguments(chosen, {}, 'win32'), chosen)

    def test_other_systems_get_no_windows_platform(self):
        self.assertEqual(qml_front_end.qt_arguments(['bloodborne'], {}, 'linux'), ['bloodborne'])

    def test_the_bundled_font_is_the_one_the_theme_names(self):
        fonts = Path(backend_module.__file__).resolve().parent / 'assets' / 'fonts'
        self.assertTrue(list(fonts.glob('IBMPlexSans-*.ttf')))
        self.assertTrue((fonts / 'IBMPlexSans-LICENSE.txt').is_file())
        self.assertIn('"IBM Plex Sans"', (QML / 'Theme.qml').read_text(encoding='utf-8'))

    QML = b'''import QtQuick
    Window {
        property real zoom: 1
        readonly property var renderTypes: [label.renderType, field.renderType]
        Item { Text { id: label; text: "Upscaler" } TextInput { id: field } }
    }'''

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.addCleanup(QQuickWindow.setTextRenderType, QQuickWindow.textRenderType())
        QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
        self.engine = QQmlEngine()
        self.component = component = QQmlComponent(self.engine)
        component.setData(self.QML, QUrl())
        self.window = component.create()
        self.assertIsNotNone(self.window, component.errorString())
        self.addCleanup(self.window.deleteLater)
        qml_front_end.follow_zoom_with_text(self.window)

    def render_types(self):
        return self.window.property('renderTypes').toVariant()

    def test_native_at_1_and_curve_when_the_stage_is_scaled(self):
        self.assertEqual(self.render_types(), [1, 1])
        self.window.setProperty('zoom', 1.4)
        self.assertEqual(self.render_types(), [2, 2])
        self.assertEqual(QQuickWindow.textRenderType(), QQuickWindow.TextRenderType.CurveTextRendering)
        self.window.setProperty('zoom', 1.0)
        self.assertEqual(self.render_types(), [1, 1])
        self.assertEqual(QQuickWindow.textRenderType(), QQuickWindow.TextRenderType.NativeTextRendering)


if __name__ == '__main__':
    unittest.main()
