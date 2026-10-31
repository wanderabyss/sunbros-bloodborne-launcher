"""The top bar's rig pill: bbport_rig's names and sizes, and HomePage.qml showing them."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module
import bbport_rig as rig


class RigNameTests(unittest.TestCase):
    def test_short_names(self):
        self.assertEqual(rig.short_gpu('NVIDIA GeForce RTX 4090'), 'RTX 4090')
        self.assertEqual(rig.short_gpu('AMD Radeon RX 7900 XTX'), 'RX 7900 XTX')
        self.assertEqual(rig.short_gpu('Intel(R) Arc(TM) A770 Graphics'), 'A770')
        self.assertEqual(rig.short_cpu('AMD Ryzen 9 7950X3D 16-Core Processor'), '7950X3D')
        self.assertEqual(rig.short_cpu('13th Gen Intel(R) Core(TM) i9-13900K'), 'i9-13900K')
        self.assertEqual(rig.short_cpu('Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz'), 'i7-8700K')
        self.assertEqual(rig.long_cpu('AMD Ryzen 9 7950X3D 16-Core Processor'), 'Ryzen 9 7950X3D')

    def test_vram_is_the_size_the_card_is_sold_as(self):
        # Windows reports an RTX 4090 as 24,146,608,128 bytes (22.5 GiB).
        self.assertEqual(rig.vram_label_gb(24146608128), 24)
        self.assertEqual(rig.vram_label_gb(8 * 2 ** 30), 8)
        self.assertEqual(rig.vram_label_gb(11 * 2 ** 30), 11)
        self.assertEqual(rig.vram_label_gb(0), 0)

    def test_driver_and_resolution(self):
        self.assertEqual(rig.driver_label('NVIDIA GeForce RTX 4090', '32.0.16.2101'), '621.01')
        self.assertEqual(rig.driver_label('AMD Radeon RX 7900 XTX', '31.0.24027.1012'), '31.0.24027.1012')
        self.assertEqual(rig.resolution_label(3840, 2160), '4K')
        self.assertEqual(rig.resolution_label(2560, 1440), '1440p')
        self.assertEqual(rig.resolution_label(1680, 1050), '1680 × 1050')


class RigPillTests(unittest.TestCase):
    RIG = {'gpu': 'RTX 4090', 'gpuFull': 'NVIDIA GeForce RTX 4090', 'vramGb': 24, 'driver': '621.01',
           'cpu': '7950X3D', 'cpuFull': 'Ryzen 9 7950X3D', 'cores': 16, 'threads': 32, 'memoryGb': 32}

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['rig-pill-test'])

    def setUp(self):
        for patch in (mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value={}),
                      mock.patch.object(backend_module.core, 'load_ini',
                                        return_value=(dict(backend_module.core.INI_DEFAULTS), [])),
                      mock.patch.object(backend_module.core, 'remembered_update', return_value=None),
                      mock.patch.object(backend_module.LauncherBackend, 'refresh_profile_data'),
                      mock.patch.object(backend_module.LauncherBackend, 'refresh_addons'),
                      mock.patch.object(backend_module.LauncherBackend, 'start_background_checks'),
                      mock.patch.object(backend_module.LauncherBackend, '_write')):
            patch.start()
            self.addCleanup(patch.stop)
        self.backend = backend_module.LauncherBackend(route={'mode': 'direct'})

    def show(self, width, height=830):
        view = QQuickView()
        self.addCleanup(view.close)
        view.rootContext().setContextProperty('launcher', self.backend)
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.resize(width, height)
        view.setSource(QUrl.fromLocalFile(str(Path(backend_module.__file__).parent / 'qml/HomePage.qml')))
        self.assertEqual(view.status(), QQuickView.Ready, view.errors())
        view.show()
        QTest.qWait(80)
        pending = [view.rootObject()]
        while pending:
            item = pending.pop()
            if item.objectName() == 'rigPill':
                return item
            pending.extend(item.childItems())
        self.fail('no rigPill')

    def test_hidden_until_the_gpu_check_reports(self):
        self.assertFalse(self.show(1470).property('visible'))

    def test_every_segment_fits_a_wide_window(self):
        self.backend._set_rig(self.RIG)
        pill = self.show(1470)
        self.assertTrue(pill.property('visible'))
        self.assertEqual(pill.property('shown'), 4)  # card, processor, memory, display

    def test_segments_drop_from_the_right_when_narrow(self):
        self.backend._set_rig(self.RIG)
        pills = [self.show(width) for width in (1470, 1000, 500)]
        shown = [pill.property('shown') for pill in pills]
        self.assertEqual(shown, sorted(shown, reverse=True))
        self.assertLess(shown[1], shown[0])
        for pill in pills[:2]:  # never wider than the room between the badge and the controls
            self.assertLessEqual(pill.property('width'), pill.property('room') + 0.5)
        self.assertEqual(shown[2], 0)
        self.assertFalse(pills[2].property('visible'))  # no room at all: hidden, not overlapping

    def test_display_comes_from_the_screen(self):
        self.backend._set_rig(self.RIG)
        values = self.backend.rig
        self.assertEqual(values['gpu'], 'RTX 4090')
        self.assertGreater(values['width'], 0)
        self.assertIn('resolution', values)


if __name__ == '__main__':
    unittest.main()
