"""Update downloads must finish before the installer can run."""
import io
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
from PySide6.QtWidgets import QApplication
import bbport_launcher_backend as module


class BackgroundUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'updates'
        replacements = [
            patch.object(module.core, 'UPDATE_DIR', self.folder),
            patch.object(module.core, 'load_all_saved_settings', return_value={}),
            patch.object(module.core, 'load_ini', return_value=(dict(module.core.INI_DEFAULTS), [])),
            patch.object(module.core, 'remembered_update', return_value=None),
            patch.object(module.LauncherBackend, 'refresh_profile_data'),
            patch.object(module.LauncherBackend, 'refresh_addons'),
            patch.object(module.LauncherBackend, '_write'),
        ]
        for item in replacements:
            item.start(); self.addCleanup(item.stop)
        self.backend = module.LauncherBackend(route={'mode':'direct'})
        self.backend._offer_update('9.0.0', 'https://example.invalid/update.zip', 'https://example.invalid/page')

    def download(self, content, length=None):
        response = io.BytesIO(content)
        response.headers = {'Content-Length': str(len(content) if length is None else length)}
        class ImmediateThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with patch.object(module.urllib.request, 'urlopen', return_value=response), \
             patch.object(module.threading, 'Thread', ImmediateThread):
            self.backend.downloadUpdate()
        self.app.processEvents()

    def package(self, executable=True):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('release/Bloodborne.exe' if executable else 'release/readme.txt', b'fixture')
        return data.getvalue()

    def test_install_cannot_download_or_start_before_ready(self):
        with patch.object(module.subprocess, 'Popen') as popen, patch.object(module.urllib.request, 'urlopen') as network:
            self.backend.installUpdate()
        popen.assert_not_called(); network.assert_not_called()
        self.assertFalse(self.backend.updateReady)

    def test_complete_download_becomes_ready_and_survives_reopen(self):
        self.download(self.package())
        self.assertTrue(self.backend.updateReady)
        self.assertFalse(self.backend.updateBusy)
        self.backend._update_ready = None
        self.backend._restore_update_download()
        self.assertTrue(self.backend.updateReady)
        self.backend._offer_update('10.0.0', 'https://example.invalid/new.zip', '')
        self.assertFalse(self.backend.updateReady)

    def test_failed_or_incomplete_download_never_enables_install(self):
        for content, length in [(b'bad zip', None), (self.package(False), None), (self.package(), 999999)]:
            self.download(content, length)
            self.assertFalse(self.backend.updateReady)
            self.assertFalse(self.backend.updateBusy)
            self.assertIn('failed', self.backend.updateStatus)

    def check_now(self, **latest):
        """Check now with latest_release patched; returns the card's status lines in order."""
        seen = []
        self.backend.updateStateChanged.connect(lambda: seen.append(self.backend.updateStatus))
        class ImmediateThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with patch.object(module.core, 'latest_release', **latest), \
             patch.object(module.threading, 'Thread', ImmediateThread), \
             patch.object(self.backend, 'downloadUpdate'):
            self.backend.checkForUpdates(True)
        self.app.processEvents()
        return seen

    def test_check_now_answers_in_the_updates_card(self):
        # Check now sits on Settings > Updates; its answer used to go only to the Home notice.
        current = module.core.VERSION
        seen = self.check_now(return_value=(f'v{current}', None, 'https://example.invalid/page'))
        self.assertIn('Checking for updates…', seen)
        self.assertEqual(self.backend.updateStatus, f'You have the latest version ({current}).')
        self.assertEqual(self.backend.notice, f'You have the latest version ({current}).')
        missing = module.urllib.request.HTTPError('https://example.invalid', 404, 'Not Found', {}, None)
        self.check_now(side_effect=missing)
        self.assertIn('Could not find a published release', self.backend.updateStatus)
        self.check_now(side_effect=OSError('offline'))
        self.assertEqual(self.backend.updateStatus, 'Could not check for updates: offline')
        self.check_now(return_value=('v99.0.0', 'https://example.invalid/u.zip', 'https://example.invalid/page'))
        self.assertTrue(self.backend.updateStatus.startswith('Version 99.0.0 is available'))

    def test_toggle_is_opt_in_and_starts_available_download(self):
        self.assertFalse(self.backend.app['download_updates'])
        with patch.object(self.backend, 'downloadUpdate') as download:
            self.backend.setValue('download_updates', True)
            download.assert_called_once()
        with patch.object(self.backend, 'downloadUpdate') as download:
            self.backend.setValue('download_updates', False)
            download.assert_not_called()

    def test_successful_install_uses_only_the_prepared_package(self):
        self.download(self.package())
        with patch.object(module.core, 'FROZEN', True), \
             patch.object(module.QMessageBox, 'question', return_value=module.QMessageBox.StandardButton.Yes), \
             patch.object(module.subprocess, 'Popen') as popen, \
             patch.object(module.urllib.request, 'urlopen') as network:
            self.backend.installUpdate()
        self.assertEqual(popen.call_args.args[0][1], '--install-update')
        network.assert_not_called()

    def test_background_download_offers_to_install_on_next_launch(self):
        self.download(self.package())
        self.assertTrue(self.backend.updateReady)
        with patch.object(module.core, 'load_all_saved_settings', return_value={'download_updates': True}), \
             patch.object(module.LauncherBackend, '_detect_gpu'), \
             patch.object(module.LauncherBackend, 'checkForUpdates'), \
             patch.object(module.LauncherBackend, 'installUpdate') as install_mock:
            next_launch = module.LauncherBackend()
            self.assertTrue(next_launch.updateReady)
            self.assertEqual(next_launch.updateVersion, '9.0.0')
            self.app.processEvents()
            # The window offers it with its notes when it opens; no dialog before the window.
            self.assertTrue(next_launch.installOffer)
            install_mock.assert_not_called()
            next_launch.dismissInstallOffer()
            self.assertFalse(next_launch.installOffer)

    def test_install_now_from_the_sheet_does_not_ask_again(self):
        self.download(self.package())
        with patch.object(module.core, 'FROZEN', True), \
             patch.object(module.QMessageBox, 'question') as ask, \
             patch.object(module.subprocess, 'Popen') as start:
            self.backend.installUpdate(True)
        ask.assert_not_called()
        start.assert_called_once()

    def test_tag_reads_as_a_version(self):
        self.backend._offer_update('v9.1.0', 'https://example.invalid/update.zip', 'https://example.invalid/page')
        self.assertEqual(self.backend.updateVersion, '9.1.0')
        self.assertIn('Version 9.1.0', self.backend.notice)

    def test_release_notes_render_with_readable_links(self):
        html = self.backend.releaseNotesHtml('### Title\r\n\r\n- **Bold** [notes](docs/x.md)')
        self.assertIn('Bold', html)
        self.assertIn('#8cc8ff', html)
        self.assertNotIn('#0000ff', html)
        self.assertNotIn('font-size:9pt', html.replace(' ', ''))
        with patch.object(module.webbrowser, 'open') as browser:
            self.backend.openReleaseLink('docs/x.md')
            self.backend.openReleaseLink('https://example.invalid/a')
            self.backend.openReleaseLink('../../outside')
        self.assertEqual([c.args[0] for c in browser.call_args_list],
                         ['https://github.com/wanderabyss/sunbros_bblauncher/blob/main/docs/x.md', 'https://example.invalid/a'])

    def test_whats_new_once_after_an_update_and_never_on_a_first_install(self):
        with patch.object(module.core, 'release_notes_section', return_value='### This version'):
            with patch.object(module.core, 'load_all_saved_settings', return_value={'last_seen_version': '1.0.0'}):
                updated = module.LauncherBackend(route={'mode': 'direct'})
            self.assertEqual(updated.whatsNew, '### This version')
            updated.dismissWhatsNew()
            self.assertEqual(updated.whatsNew, '')
            self.assertEqual(updated.app['last_seen_version'], module.core.VERSION)
            with patch.object(module.core, 'load_all_saved_settings', return_value={}):
                fresh = module.LauncherBackend(route={'mode': 'direct'})
            self.assertEqual(fresh.whatsNew, '')
            self.assertEqual(fresh.app['last_seen_version'], module.core.VERSION)

    def test_releases_always_opens_sunbros(self):
        self.assertEqual(module.core.RELEASES_API,
                         'https://api.github.com/repos/wanderabyss/sunbros_bblauncher/releases/latest')
        self.assertFalse(module.core.release_is_newer('qml-launcher-preview-24'))
        with patch.object(module.webbrowser, 'open') as browser:
            self.backend.viewRelease()
            self.backend.action('releases')
        self.assertEqual(browser.call_count, 2)
        for call in browser.call_args_list:
            self.assertEqual(call.args[0], 'https://github.com/wanderabyss/sunbros_bblauncher/releases')

    def test_updates_view_exposes_background_toggle_and_download_status(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuick import QQuickView
        view = QQuickView()
        view.rootContext().setContextProperty('launcher', self.backend)
        view.setSource(QUrl.fromLocalFile(str(Path(module.__file__).parent / 'qml/SettingsWorkspace.qml')))
        self.assertEqual(view.status(), QQuickView.Ready)
        root = view.rootObject()
        root.setProperty('embedded', True)
        root.setProperty('category', 'System')
        root.setProperty('section', 'Updates')
        pending = [root]; retained = []
        while pending:
            item = pending.pop(); retained.append(item); pending.extend(item.childItems())
        toggle = next(item for item in retained if item.property('label') == 'Download updates in the background')
        self.assertTrue(toggle.isVisible())
        self.assertFalse(toggle.property('checked'))
        self.backend.setValue('download_updates', False)
        self.backend._set_update_status('Fixture download progress')
        self.app.processEvents()
        self.assertTrue(any(item.property('text') == 'Fixture download progress' for item in retained))
        view.setSource(QUrl())
