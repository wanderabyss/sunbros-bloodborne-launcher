"""Interaction checks for Dossier filters, Online and Co-op pages, Visuals shortcuts and System controls."""
from unittest import mock
from pathlib import Path

from PySide6.QtCore import QMetaObject, QPoint, QSize, Qt
from PySide6.QtTest import QTest
import test_home_dashboard_qml as home_tests
import test_workspace_navigation_qml as navigation

backend_module = home_tests.backend_module


class DepthWorkspaceTests(navigation.WorkspaceNavigationTests):
    # Existing navigation tests are deliberately inherited: the richer views must
    # retain all primary routes and preference isolation.
    def open_section(self, page, section):
        item = self.within(page, 'section_' + section)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        self.fixture.app.processEvents()

    def test_motion_can_be_disabled(self):
        self.click('primary_Settings')
        self.open_section('preferencesPage', 'Launch')
        motion = self.item('motionToggle')

        def wait_for(active):
            for _ in range(50):
                if motion.property('motionActive') == active:
                    break
                QTest.qWait(20)
            return motion.property('motionActive')
        self.assertTrue(motion.property('motionActive'))
        # Below the Launch rows, so it may be scrolled out of view: press it directly.
        QMetaObject.invokeMethod(motion, 'click')
        self.assertFalse(wait_for(False))
        QMetaObject.invokeMethod(motion, 'click')
        self.assertTrue(wait_for(True))

    def test_trophy_filters_use_live_profile(self):
        self.fixture.backend._profile_data.update(
            trophies=[dict(id=1, name='First trophy', description='First description',
                           grade='B', grade_name='Bronze', category='Boss',
                           icon='TROP001.PNG', unlocked=True, unlocked_at='Oct 27, 2026'),
                      dict(id=2, name='Second trophy', description='Second description',
                           grade='G', grade_name='Gold', category='Story',
                           icon='TROP002.PNG', unlocked=False, unlocked_at='')],
            bloodtinge=12, arcane=15, trophies_earned=1, trophies_total=2)
        self.fixture.backend.profileDataChanged.emit()
        self.click('primary_Dossier')
        self.assertTrue(self.item('attributes').isVisible())
        self.click('trophyState_Earned')
        self.assertEqual(self.item('trophyStateFilter').property('currentIndex'), 1)
        trophies = self.item('dossierWorkspace').property('filteredTrophies')
        trophies = trophies.toVariant() if hasattr(trophies, 'toVariant') else trophies
        self.assertEqual([t['id'] for t in trophies], [1])
        self.click('trophyState_Locked')
        self.assertEqual(self.item('trophyStateFilter').property('currentIndex'), 2)
        self.item('trophySearch').setProperty('text', 'Second')
        self.click('trophyState_All')
        trophies = self.item('dossierWorkspace').property('filteredTrophies')
        trophies = trophies.toVariant() if hasattr(trophies, 'toVariant') else trophies
        self.assertEqual([t['id'] for t in trophies], [2])

    def test_online_and_coop_are_separate_pages(self):
        self.click('primary_Online')
        self.assertTrue(self.item('onlineWorkspace').isVisible())
        self.assertTrue(self.item('huntersDreamCard').isVisible())
        self.click('openCoopFromOnline')
        self.assertEqual(self.window.property('page'), 'Coop')
        self.assertTrue(self.item('coopWorkspace').isVisible())
        self.assertFalse(self.item('onlineWorkspace').isVisible())
        self.assertTrue(self.item('coopSetupPanel').isVisible())
        # Two steps: Account (with the BBSC download), then Connection with the frame rate and Play.
        panel = self.item('coopSetupPanel')
        self.assertTrue(self.item('coopSideDownload').isVisible())
        panel.setProperty('step', 1)
        QTest.qWait(30)
        self.assertTrue(self.item('coopFrameRate').isVisible())
        self.assertTrue(self.item('coopSidePlay').isVisible())
        self.assertFalse(self.item('coopSideDownload').isVisible())

    def test_visuals_studio_exposes_remastered_preset_and_hd_textures_shortcut(self):
        self.click('primary_Visuals')
        self.assertTrue(self.item('studioPreset_remastered').isVisible())
        self.assertTrue(self.item('openHdTextures').isVisible())
        self.click('studioPreset_remastered')
        self.assertEqual(self.fixture.backend.graphicsPreset, 'remastered')
        self.click('openHdTextures')
        self.assertEqual(self.window.property('page'), 'VisualsAdvanced')
        self.assertEqual(self.item('visualsAdvanced').property('section'), 'High-resolution textures')
        self.click('primary_Home')
        self.assertTrue(self.item('homeQuickSettingsCard').isVisible())

    def test_visuals_studio_marks_a_dlss4_and_a_dlss5_preset_on_an_rtx_4090(self):
        backend = self.fixture.backend
        backend._dlss5_offered = True
        backend._set_gpu_status('NVIDIA GeForce RTX 4090, discrete, 24564 MiB')
        self.fixture.app.processEvents()
        self.click('primary_Visuals')
        self.assertTrue(self.item('studioPreset_remastered').property('text') == '★ Remastered  DLSS 4')
        self.assertTrue(self.item('studioPreset_dlss5_ready').property('text') == '★ DLSS 5')
        # The tuned presets have a row of their own, below the everyday ones.
        row_y = lambda name: self.item('studioPreset_' + name).mapToScene(QPoint(0, 0).toPointF()).y()
        self.assertEqual(row_y('remastered'), row_y('dlss5_ready'))
        self.assertGreater(row_y('remastered'), row_y('ultra') + 30)
        # The card comes first on that line: RTX 4090 chosen, RTX 4080 greyed out (no settings yet).
        card_y = lambda card: self.item('tunedCard_' + card).mapToScene(QPoint(0, 0).toPointF()).y()
        self.assertEqual(card_y('4090'), card_y('4080'))
        self.assertLess(abs(card_y('4090') - row_y('remastered')), 10)
        self.assertTrue(self.item('tunedCard_4090').isEnabled())
        self.assertFalse(self.item('tunedCard_4080').isEnabled())
        self.assertNotIn('★', self.item('studioPreset_ultra').property('text'))
        # Another card: one plain mark, which follows the GPU check.
        backend._dlss5_offered = False
        backend._set_gpu_status('NVIDIA GeForce RTX 3090, discrete, 24576 MiB')
        self.fixture.app.processEvents()
        self.assertTrue(self.item('studioPreset_ultra').property('text').endswith(' ★'))
        self.assertNotIn('★', self.item('studioPreset_remastered').property('text'))
        self.assertTrue(self.item('studioPreset_remastered').property('text') == 'Remastered  DLSS 4')

    def test_visuals_custom_pill_lights_for_own_settings_and_opens_advanced(self):
        backend = self.fixture.backend
        self.click('primary_Visuals')
        backend.applyGraphicsPreset('high')
        self.fixture.app.processEvents()
        self.assertTrue(self.item('studioPreset_custom').isVisible())
        self.assertFalse(self.item('studioPreset_custom').property('selected'))
        self.assertFalse(self.item('saveMySettings').property('highlighted'))
        backend.setValue('model_lod', '-2')  # off every preset
        QTest.qWait(30)
        self.assertEqual(backend.graphicsPreset, 'custom')
        custom = [i for i in self.items() if i.objectName() == 'studioPreset_custom' and i.isVisible()]
        self.assertEqual([i.property('selected') for i in custom], [True])
        self.assertTrue(self.item('saveMySettings').property('highlighted'))  # unsaved: save is lit
        # HDR output sits in the side column with the shortcuts, not in the summary.
        hdr = [i for i in self.items() if i.property('text') == 'HDR output' and i.isVisible()]
        self.assertEqual(len(hdr), 1)
        self.assertGreater(hdr[0].mapToScene(QPoint(0, 0).toPointF()).x(),
                           self.item('studioPreset_ultra').mapToScene(QPoint(0, 0).toPointF()).x() + 200)
        self.click('studioPreset_custom')
        self.assertEqual(self.window.property('page'), 'VisualsAdvanced')
        self.assertEqual(backend.graphicsPreset, 'custom')

    def test_visuals_tuned_presets_each_have_their_own_info_mark(self):
        backend = self.fixture.backend
        backend._dlss5_offered = True
        backend._set_gpu_status('NVIDIA GeForce RTX 4090, discrete, 24564 MiB')
        self.click('primary_Visuals')
        backend.applyGraphicsPreset('remastered')
        QTest.qWait(30)
        self.assertFalse(self.item('presetDescription').isVisible())  # no paragraph for a tuned preset
        for name, other, tag in (('remastered', 'dlss5_ready', 'DLSS 4'), ('dlss5_ready', 'remastered', 'DLSS 5')):
            info = self.item('presetInfo_' + name)
            self.assertTrue(info.isVisible())
            QTest.mouseMove(self.window, info.mapToScene(info.boundingRect().center()).toPoint())
            QTest.qWait(50)
            # The ToolTip is a popup outside the item tree: its mark says when it is open.
            self.assertTrue(info.property('open'))
            self.assertFalse(self.item('presetInfo_' + other).property('open'))
            text = info.property('tip')
            self.assertIn(backend.presetDescription(name), text)
            self.assertIn('(' + tag + ')', text)
        # An everyday preset keeps its paragraph.
        backend.applyGraphicsPreset('high')
        QTest.qWait(30)
        self.assertTrue(self.item('presetDescription').isVisible())
        self.assertEqual(self.item('presetDescription').property('text'), backend.presetDescription('high'))

    def test_coop_page_offers_the_bbsc_download(self):
        # The 4.1.0 launcher lost the button that called coopSetup; the status still named it.
        backend = self.fixture.backend
        with mock.patch.object(backend_module.coop, 'installed', return_value=False), \
                mock.patch.object(backend_module.LauncherBackend, 'coopSetup') as setup:
            backend.coopChanged.emit()
            self.click('primary_Online')
            self.click('openCoopFromOnline')
            button = self.item('coopSideDownload')
            self.assertTrue(button.isVisible())
            self.assertEqual(button.property('text'), 'Download BBSC ' + backend_module.coop.VERSION)
            self.assertIn('Download BBSC', backend.coopStatus)
        with mock.patch.object(backend_module.coop, 'installed', return_value=True):
            backend.coopChanged.emit()
            self.fixture.app.processEvents()
            self.assertTrue(self.item('coopSideDownload').property('text').endswith(' again'))

    def test_coop_connection_details_show_checks_and_events(self):
        backend = self.fixture.backend
        self.click('primary_Online')
        self.click('openCoopFromOnline')
        self.item('coopSetupPanel').setProperty('step', 1)
        QTest.qWait(30)
        self.assertFalse(self.item('coopConnectionDetails').isVisible())
        events = ["16:33:56  SESSION  guest, Cathedral Ward | session state 4 -> 6 (in a host's world)"]
        # Below the Play row, so it may be scrolled out of view: press it directly.
        with mock.patch.object(backend_module.coop, 'connection_events', return_value=events):
            QMetaObject.invokeMethod(self.item('coopDetailsToggle'), 'click')
            QTest.qWait(30)
        self.assertTrue(self.item('coopConnectionDetails').isVisible())
        backend._coop_checks_done([{'label': 'Relay (warps, world sync), port 20444', 'ok': False, 'detail': 'no answer'}])
        QTest.qWait(30)
        texts = [i.property('text') for i in self.items() if i.property('text') and i.isVisible()]
        self.assertIn('Relay (warps, world sync), port 20444', texts)
        self.assertIn(events[0], texts)
        # Open ports: highlighted when the firewall rule is missing; runs the admin setup, checks again.
        open_ports = self.item('coopOpenPorts')
        self.assertFalse(open_ports.property('highlighted'))
        backend._coop_checks_done([{'label': 'Firewall rule for this game', 'ok': False, 'detail': 'missing'}])
        QTest.qWait(30)
        self.assertTrue(backend.coopFirewallMissing)
        self.assertTrue(open_ports.property('highlighted'))
        fixed = [('Firewall rule for this game', True, 'set')]
        with mock.patch.object(backend, '_coop_game_exe', return_value=Path('bb-probe.exe')), \
                mock.patch.object(backend_module.coop, 'run_setup') as setup, \
                mock.patch.object(backend_module.coop, 'connection_checks', return_value=fixed):
            QMetaObject.invokeMethod(open_ports, 'click')
            for _ in range(100):
                QTest.qWait(20)
                if not backend.coopBusy:
                    break
        setup.assert_called_once()
        self.assertFalse(backend.coopFirewallMissing)
        QTest.qWait(30)
        self.assertTrue(self.item('coopPortsResult').isVisible())
        self.assertTrue(self.item('coopPortsResultText').property('text').startswith('Ports opened'))
        # A No on the Windows prompt shows there too.
        with mock.patch.object(backend, '_coop_game_exe', return_value=Path('bb-probe.exe')), \
                mock.patch.object(backend_module.coop, 'run_setup', side_effect=backend_module.coop.CoopError('the answer was No')):
            QMetaObject.invokeMethod(open_ports, 'click')
            for _ in range(100):
                QTest.qWait(20)
                if not backend.coopBusy:
                    break
        self.assertEqual(backend.coopPortsResult['state'], 'failed')
        self.assertIn('answer was No', self.item('coopPortsResultText').property('text'))

    def test_visuals_save_settings_keeps_a_preset_or_saves_custom(self):
        backend = self.fixture.backend
        self.click('primary_Visuals')
        backend.applyGraphicsPreset('ultra')
        self.assertFalse(backend.hasMySettings)
        # Save settings sits at the top of the right column.
        save = self.item('saveMySettings')
        self.assertGreater(save.mapToScene(QPoint(0, 0).toPointF()).x(),
                           self.item('studioPreset_ultra').mapToScene(QPoint(0, 0).toPointF()).x() + 200)
        self.assertEqual(save.property('text'), 'Save settings')
        # Saved on Ultra: still Ultra, not Custom.
        self.click('saveMySettings')
        self.assertTrue(backend.hasMySettings)
        self.assertEqual(backend.graphicsPreset, 'ultra')
        QTest.qWait(30)
        self.assertTrue(self.item('studioPreset_ultra').property('selected'))
        self.assertFalse(self.item('studioPreset_custom').property('selected'))
        # Own changes saved: the Custom pill, which loads them back after another preset.
        backend.setValue('model_lod', '0')
        backend.setValue('output_res', '2560x1440')
        self.click('saveMySettings')
        self.assertEqual(backend.graphicsPreset, 'mine')
        QTest.qWait(30)
        self.assertFalse([i for i in self.items() if i.objectName() == 'studioPreset_mine'])
        self.assertTrue(self.item('studioPreset_custom').property('selected'))
        self.click('studioPreset_low')
        self.assertEqual(backend.graphicsPreset, 'low')
        self.click('studioPreset_custom')
        self.assertEqual((backend.graphicsPreset, backend.ini['model_lod'], backend.ini['output_res']),
                         ('mine', '0', '2560x1440'))
        self.assertEqual(self.window.property('page'), 'Visuals')

    def test_settings_saved_on_ultra_start_on_ultra(self):
        ini, app = dict(backend_module.core.INI_DEFAULTS), dict(backend_module.core.APP_DEFAULTS)
        backend_module.core.apply_graphics_preset('ultra', ini, app)
        saved = {'my_settings': backend_module.core.my_settings_snapshot(ini, app),
                 'ini_settings': {'preset': '3', 'model_lod': '1'}}  # last tried: something else
        with mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value=saved):
            started = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.assertEqual(started.graphicsPreset, 'ultra')

    def test_my_settings_load_when_the_launcher_starts(self):
        ini = dict(backend_module.core.INI_DEFAULTS)
        backend_module.core.apply_graphics_preset('ultra', ini, dict(backend_module.core.APP_DEFAULTS))
        saved = {'my_settings': {'ini': {'preset': '0', 'output_res': '2560x1440'}, 'app': {}},
                 'ini_settings': {'preset': '3', 'output_res': '1920x1080'}}
        with mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value=saved):
            started = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.assertEqual((started.ini['preset'], started.ini['output_res']), ('0', '2560x1440'))
        del saved['my_settings']  # nothing saved: the last settings stay
        with mock.patch.object(backend_module.core, 'load_all_saved_settings', return_value=saved):
            started = backend_module.LauncherBackend(route={'mode': 'direct'})
        self.assertEqual((started.ini['preset'], started.ini['output_res']), ('3', '1920x1080'))

    def test_first_start_takes_this_pcs_display_and_suggested_preset_once(self):
        backend = self.fixture.backend
        backend._first_start = True
        screen = mock.Mock()
        screen.size.return_value = QSize(2560, 1440)
        screen.devicePixelRatio.return_value = 1.0
        with mock.patch.object(backend_module.QGuiApplication, 'primaryScreen', return_value=screen):
            backend._set_gpu_status('NVIDIA GeForce RTX 4090, discrete, 24564 MiB')
        self.assertEqual(backend.ini['output_res'], '2560x1440')
        self.assertEqual(backend.graphicsPreset, 'remastered')
        self.assertIn('Set for your PC: NVIDIA GeForce RTX 4090, 2560 × 1440, Remastered', backend.firstStartSummary)
        # Only the first report: later ones (and the player's own changes) are left alone.
        backend.ini['output_res'] = '1920x1080'
        backend._set_gpu_status('NVIDIA GeForce RTX 4090, discrete, 24564 MiB')
        self.assertEqual(backend.ini['output_res'], '1920x1080')

    def test_visuals_studio_opens_neural_rendering_with_advanced_rows_folded(self):
        self.click('primary_Visuals')
        self.assertTrue(self.item('openNeuralRendering').isVisible())
        self.click('openNeuralRendering')
        editor = self.item('visualsAdvanced')
        self.assertEqual(editor.property('section'), 'Neural rendering (DLSS 5)')

        def keys():
            rows = editor.visibleSectionFields('Visuals', 'Neural rendering (DLSS 5)')
            rows = rows.toVariant() if hasattr(rows, 'toVariant') else rows
            return [row['key'] for row in rows]
        self.assertEqual(keys(), ['dlss5', 'nr_upscaling', 'nr_intensity', 'nr_preset', 'nr_style'])
        editor.setProperty('nrAdvancedOpen', True)
        self.assertIn('nr_skin_structure', keys())
        self.assertEqual(len(keys()), 10)

    def test_save_settings_snapshot_is_in_maintenance(self):
        self.click('primary_Settings')
        self.open_section('preferencesPage', 'Maintenance')
        save_btn = self.item('saveSettingsBtn')
        self.assertFalse(save_btn.property('saved'))
        # Below the section's rows, so it may be scrolled out of view: press it directly.
        QMetaObject.invokeMethod(save_btn, 'click')
        QTest.qWait(100)
        self.assertTrue(save_btn.property('saved'))
