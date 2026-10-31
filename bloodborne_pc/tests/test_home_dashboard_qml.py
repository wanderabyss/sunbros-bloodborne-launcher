"""Exercise the live dashboard, routing and launch guards without starting a game."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PySide6.QtCore import QObject, QPoint, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_backend as backend_module


class HomeDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['home-dashboard-test'])
        fonts = [Path(backend_module.__file__).parent / 'assets/ui/bloodborne-font.ttf']
        for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
            fonts.append(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name)
        for path in fonts:
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))

    def setUp(self):
        patches = [
            mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value={}),
            mock.patch.object(backend_module.core, 'load_ini',
                              return_value=(dict(backend_module.core.INI_DEFAULTS), [])),
            mock.patch.object(backend_module.core, 'remembered_update', return_value=None),
            mock.patch.object(backend_module.LauncherBackend, 'refresh_profile_data'),
            mock.patch.object(backend_module.LauncherBackend, 'refresh_addons'),
            mock.patch.object(backend_module.LauncherBackend, 'start_background_checks'),
            mock.patch.object(backend_module.LauncherBackend, '_write'),
            mock.patch.object(backend_module.core, 'save_ini'),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.backend = backend_module.LauncherBackend(route={'mode': 'direct'})
        # A checkout may have no bbport.ini: no first-start settings unless a test asks.
        self.backend._first_start = False
        self.backend.app.update(play_mode='offline', coop_name='', coop_password='',
                                coop_invite='', thd_token='', thd_online_id='')
        self.backend._profile_data = dict(valid=True, name='Test Hunter', level=40,
                                         play_time='50h 12m', trophies_earned=4,
                                         vitality=25, endurance=20, strength=30, skill=18)
        self.view = QQuickView()
        self.view.rootContext().setContextProperty('launcher', self.backend)
        self.view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self.view.resize(1290, 830)
        source = Path(backend_module.__file__).parent / 'qml/HomePage.qml'
        self.view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(self.view.status(), QQuickView.Ready, self.view.errors())
        self.view.show()
        QTest.qWait(80)
        self.root = self.view.rootObject()

    def tearDown(self):
        self.view.close()
        self.view.setSource(QUrl())

    def item(self, name):
        # Repeater delegates may exist only in the visual tree.
        pending = [self.root]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail('Missing dashboard control: ' + name)

    def click(self, name):
        item = self.item(name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.view, Qt.LeftButton, Qt.NoModifier, point)
        self.app.processEvents()

    def test_profile_and_navigation_are_live(self):
        self.assertEqual(self.item('hunterName').property('text'), 'Test Hunter')
        dossier = QSignalSpy(self.root.characterInfoRequested)
        self.click('openDossier')
        self.assertEqual(dossier.count(), 1)
        self.backend._profile_data = {}
        self.backend.profileDataChanged.emit()
        self.assertEqual(self.item('hunterName').property('text'), 'A new hunt awaits')

    def test_modes_and_launch_guards(self):
        launch = QSignalSpy(self.root.primaryRequested)
        route = QSignalSpy(self.root.workspaceRequested)
        self.click('mode_coop')
        self.assertEqual(self.backend.playMode, 'coop')
        self.assertEqual(self.item('launchHunt').property('text'), 'Set up co-op')
        self.click('launchHunt')
        self.assertEqual(launch.count(), 0)
        self.assertEqual(route.at(0), ['Co-op', ''])
        self.click('mode_offline')
        self.assertEqual(self.item('launchHunt').property('text'), 'Play')
        self.click('launchHunt')
        self.click('launchHunt')
        self.assertEqual(launch.count(), 1, 'Repeated clicks launched twice')
        self.backend.gameFinished.emit(1, False)
        self.assertFalse(self.root.property('startingGame'))

    def test_compact_layout_keeps_actions_in_view(self):
        self.view.resize(800, 700)
        QTest.qWait(50)
        self.assertTrue(self.root.property('compact'))
        launch_y = self.item('launchHunt').mapToScene(QPoint(0, 0)).y()
        self.assertGreaterEqual(launch_y, 0)
        self.assertLessEqual(launch_y + self.item('launchHunt').height(), 700)
        # Home does not scroll: Play stays where it is and works.
        launch = QSignalSpy(self.root.primaryRequested)
        self.click('launchHunt')
        self.assertEqual(launch.count(), 1, 'Launch action is unreachable after scrolling')
        self.assertLessEqual(self.item('mode_coop').mapToScene(QPoint(0, 0)).x()
                             + self.item('mode_coop').width(), 800)

    def test_setup_status_is_separate_from_update_notices(self):
        self.click('mode_coop')
        self.backend._notice = 'Version preview-24 is available.'
        self.backend.noticeChanged.emit()
        self.assertEqual(self.item('launchStatus').property('text'), 'Co-op setup required')
        self.assertIn('Add your co-op account', self.item('launchGuidance').property('text'))
        self.assertNotIn('Version', self.item('launchGuidance').property('text'))
        self.assertEqual(self.item('launcherNotice').property('text'), self.backend._notice)
        self.backend.app.update(coop_name='Hunter', coop_password='test', coop_server='public')
        self.backend.coopChanged.emit()
        self.assertEqual(self.item('launchStatus').property('text'), 'Ready for the hunt')
        self.assertEqual(self.item('launchHunt').property('text'), 'Play co-op')

    def test_launch_failure_stays_visible_and_allows_retry(self):
        self.click('launchHunt')
        self.backend._notice = 'Choose the game folder containing eboot.bin first.'
        self.backend.noticeChanged.emit()
        self.assertFalse(self.root.property('startingGame'))
        self.assertEqual(self.item('launchStatus').property('text'), 'Launch needs attention')
        self.assertEqual(self.item('launchGuidance').property('text'), self.backend._notice)
        self.assertTrue(self.item('launchHunt').property('enabled'))

    def test_hd_pack_badge_shows_non_zero_width_and_routes_to_visuals(self):
        badge = self.item('hdPackBadge')
        label = self.item('hdPackBadgeText')
        with mock.patch.object(self.backend, '_hd_pack_info', return_value=None):
            self.backend.changed.emit()
            self.app.processEvents()
            QTest.qWait(40)
            self.assertFalse(badge.isVisible())
        self.backend.app['hd_textures'] = True
        with mock.patch.object(self.backend, '_hd_pack_info', return_value={'pack_version': '1', 'files': 1}):
            self.backend.changed.emit()
            self.app.processEvents()
            QTest.qWait(40)
            self.assertTrue(badge.isVisible())
            self.assertGreater(badge.width(), 40)
            self.assertEqual(label.property('text'), 'HD textures')
            route = QSignalSpy(self.root.workspaceRequested)
            self.click('hdPackBadge')
            self.assertEqual(route.count(), 1)
            self.assertEqual(route.at(0), ['Visuals', 'High-resolution textures'])

    def test_quick_settings_and_system_profile_cards_are_interactive(self):
        self.assertTrue(self.item('homeQuickSettingsCard').isVisible())
        self.backend.applyGraphicsPreset('remastered')
        self.app.processEvents()
        self.assertEqual(self.backend.graphicsPreset, 'remastered')
        self.assertEqual(self.item('quickToggle_fps_mode').property('currentText'), '60 base → 120 FPS')
        self.assertEqual(self.item('quickToggle_frame_gen').property('currentText'), 'DLSS 2×')
        before_hdr = self.backend.value('hdr')
        before_text = self.item('quickToggle_hdr').property('currentText')
        self.click('quickToggle_hdr')
        self.assertNotEqual(self.backend.value('hdr'), before_hdr)
        self.assertNotEqual(self.item('quickToggle_hdr').property('currentText'), before_text)

    def test_fps_target_distinguishes_base_and_generated_frames(self):
        self.backend.applyGraphicsPreset('remastered')
        for fps, provider, multiplier, expected in [
            ('60', 'dlss', '3', '60 base → 180 FPS'),
            ('90', 'fsr3', '4', '90 base → 180 FPS'),
            ('120', 'off', '2', '120 FPS (no FG)'),
            ('30', 'off', '2', '30 FPS (no FG)'),
            ('uncap', 'dlss', '2', 'Unlocked base FPS'),
        ]:
            with self.subTest(fps=fps, provider=provider):
                self.backend.app['fps_mode'] = fps
                self.backend.ini.update(frame_gen=provider, frame_gen_multiplier=multiplier)
                self.backend.changed.emit()
                self.app.processEvents()
                self.assertEqual(self.item('quickToggle_fps_mode').property('currentText'), expected)

    def test_fps_target_exposes_an_advanced_override_until_remastered_is_reapplied(self):
        self.backend.applyGraphicsPreset('remastered')
        self.backend.app['extra_env'] = 'BB_FPS=uncap'
        self.backend.changed.emit()
        self.app.processEvents()
        self.assertEqual(self.item('quickToggle_fps_mode').property('currentText'), 'Unlocked (override)')
        self.assertEqual(self.backend.graphicsPreset, 'custom')
        self.backend.applyGraphicsPreset('remastered')
        self.backend.changed.emit()
        self.app.processEvents()
        self.assertEqual(self.item('quickToggle_fps_mode').property('currentText'), '60 base → 120 FPS')

    def test_dlss5_is_the_neural_rendering_switch(self):
        # The community route's on/off (run.py dlss5_environment), at the top of its own section;
        # Upscaling keeps no DLSS 5 rows (the built-in route's detail / tone have no backend).
        upscaling = {field['key'] for field in self.backend.sectionFields('Visuals', 'Upscaling')}
        self.assertFalse(upscaling & {'dlss5', 'dlss5_detail', 'dlss5_tone'})
        self.backend.ini['dlss5'] = 'on'
        row = self.backend.sectionFields('Visuals', 'Neural rendering (DLSS 5)')[0]
        self.assertEqual(row['key'], 'dlss5')
        self.assertFalse(row['disabled'])
        self.assertEqual([option['value'] for option in row['options']], ['off', 'on'])
        self.assertIn('Neural runtime:', row['hint'])
        self.assertNotIn('not offered', row['hint'])

    def test_dlss5_hint_names_the_gpu_check_reason(self):
        self.backend._dlss5_not_offered = 'needs a GeForce RTX 4080, 4090 or newer; NVIDIA GeForce RTX 3080'
        row = next(field for field in self.backend.sectionFields('Visuals', 'Neural rendering (DLSS 5)')
                   if field['key'] == 'dlss5')
        self.assertIn('not offered DLSS 5: needs a GeForce RTX 4080', row['hint'])

    def test_dlss5_detail_and_tone_keep_d6_defaults_without_rows(self):
        # The built-in route's look (vk_dlss5.h, no backend yet): stored in bbport.ini, no row.
        self.assertEqual(backend_module.core.INI_DEFAULTS['dlss5_detail'], '0.50')
        self.assertEqual(backend_module.core.INI_DEFAULTS['dlss5_tone'], '0.00')
        self.assertNotIn('dlss5_detail', backend_module.SETTING_FIELDS)
        self.backend.setValue('dlss5_tone', '0.30')
        self.assertEqual(self.backend.ini['dlss5_tone'], '0.30')

    def test_present_upscale_rows_follow_output_resolution(self):
        rows = {field['key']: field
                for field in self.backend.sectionFields('Visuals', 'Resolution')}
        keys = list(rows)
        self.assertEqual(keys[keys.index('output_res'):keys.index('output_res') + 3],
                         ['output_res', 'present_upscale', 'present_rcas'])
        upscale, rcas = rows['present_upscale'], rows['present_rcas']
        self.assertEqual(upscale['label'], 'Upscale to the display')
        self.assertEqual(rcas['label'], 'Extra sharpening after upscale')
        self.assertFalse(upscale['disabled'])
        self.assertFalse(rcas['disabled'])
        self.assertEqual([option['value'] for option in upscale['options']], ['easu', 'linear'])
        self.assertIn('recommended', upscale['options'][0]['text'])
        self.assertEqual(rcas['options'][0], {'value': '0', 'text': 'Off (default)'})
        self.assertIn('below your display', upscale['hint'])
        self.assertIn('0.2 ms', upscale['hint'])
        self.assertIn("upscaler's own sharpening", rcas['hint'])
        found = [result['key'] for result in self.backend.searchSettings('easu')]
        self.assertIn('present_upscale', found)
        found = [result['key'] for result in self.backend.searchSettings('rcas')]
        self.assertIn('present_rcas', found)
        self.backend.setValue('present_rcas', '0.5')
        self.assertEqual(self.backend.ini['present_rcas'], '0.5')

    def test_dlss5_ready_preset_only_on_offered_cards(self):
        self.backend._dlss5_offered = False
        self.assertNotIn('dlss5_ready', self.backend.graphicsPresets)
        self.backend.applyGraphicsPreset('dlss5_ready')
        self.assertNotEqual(self.backend.graphicsPreset, 'dlss5_ready')
        self.backend._dlss5_offered = True
        self.assertEqual(self.backend.graphicsPresets[-1], 'dlss5_ready')
        self.assertEqual(self.backend.presetLabel('dlss5_ready'), 'DLSS 5 ready')

    def test_dlss5_request_away_from_60_warns_on_both_rows(self):
        self.backend.ini['dlss5'] = 'on'
        self.backend.app['fps_mode'] = '120'
        fields = {field['key']: field for section in ('Neural rendering (DLSS 5)', 'Resolution', 'Frame rate')
                  for field in self.backend.sectionFields('Visuals', section)}
        self.assertIn('fixed 60 FPS', fields['dlss5']['hint'])
        self.assertIn('fixed 60 FPS', fields['fps_mode']['hint'])

    def test_dlss5_at_4k_output_warns_on_its_rows(self):
        self.backend.ini.update(dlss5='on', output_res='3840x2160')
        self.backend.app.update(fps_mode='60', extra_env='', nr_upscaling='addon')
        fields = {field['key']: field for section in ('Neural rendering (DLSS 5)', 'Resolution', 'Frame rate')
                  for field in self.backend.sectionFields('Visuals', section)}
        for key in ('dlss5', 'nr_upscaling', 'output_res'):
            with self.subTest(key=key):
                self.assertIn('misses 60 FPS', fields[key]['hint'])

    def test_unimplemented_ray_tracing_controls_are_hidden_but_kept_in_the_ini(self):
        for key in ('rt_secondary_lights', 'rt_reflections'):
            with self.subTest(key=key):
                self.backend.ini[key] = '1'
                keys = [f['key'] for f in self.backend.sectionFields('Visuals', 'Ray tracing')]
                self.assertNotIn(key, keys)
                self.assertEqual(self.backend.ini[key], '1')

    def test_bottom_update_notification_banner_shows_and_routes(self):
        banner = self.item('updateNotificationBanner')
        self.assertFalse(banner.isVisible())
        self.backend._offer_update('3.4.0', 'https://example.invalid/bbport-3.4.0.zip', 'https://example.invalid/releases')
        self.app.processEvents()
        QTest.qWait(40)
        self.assertTrue(banner.isVisible())
        self.assertEqual(self.item('updateBannerText').property('text'), 'New release available: 3.4.0')
        self.assertEqual(self.item('updateBannerAction').property('text'), 'Download')
        with mock.patch.object(self.backend, 'downloadUpdate') as download:
            self.click('updateBannerAction')
            download.assert_called_once()
        # "What's new" opens the release notes over the page (UpdateSheet in Main.qml).
        details = self.item('updateBannerDetails')
        self.assertEqual(details.property('text'), "What's new")
        route = QSignalSpy(self.root.workspaceRequested)
        self.click('updateBannerDetails')
        self.assertEqual(route.count(), 0)


if __name__ == '__main__':
    unittest.main()
