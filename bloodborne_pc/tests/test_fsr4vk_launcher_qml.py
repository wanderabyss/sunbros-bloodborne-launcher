"""The QML launcher's FSR 4.1.1 (fsr4vk) download row under Visuals > Upscaling."""
from unittest import mock

from PySide6.QtCore import QMetaObject
from PySide6.QtTest import QTest
import test_workspace_navigation_qml as navigation


class Fsr4VkLauncherTests(navigation.WorkspaceNavigationTests):
    def upscaling_editor(self):
        self.click('primary_Visuals')
        self.click('openGraphicsAdvanced')
        editor = self.item('visualsAdvanced')
        self.assertTrue(editor.isVisible())
        editor.setProperty('section', 'Upscaling')
        QTest.qWait(50)
        return editor

    def visible_button(self):
        """The Visuals editor's button: other workspaces hold their own, hidden, SettingsWorkspace."""
        buttons = [item for item in self.items()
                   if item.objectName() == 'fsr4vkDownload' and item.isVisible()]
        self.assertEqual(len(buttons), 1)
        return buttons[0]

    def test_upscaling_shows_fsr4vk_download_and_status(self):
        backend = self.fixture.backend
        self.upscaling_editor()
        self.assertEqual(self.visible_button().property('text'), 'Download FSR 4.1.1')
        self.assertIn('FSR 4.1.1', backend.fsr4vkStatus)
        self.assertIn('1920×1080', backend.fsr4vkStatus)

    def test_download_button_fetches_into_the_provider_folder(self):
        import bbport_launcher_win as core
        self.upscaling_editor()
        with mock.patch.object(core.bbport_fsr4vk, 'files_ok', return_value=False), \
                mock.patch.object(core.bbport_fsr4vk, 'fetch') as fetch:
            # The row may sit below the editor's scrolled area: emit the button's click.
            QMetaObject.invokeMethod(self.visible_button(), 'clicked')
            for _ in range(50):
                if fetch.called:
                    break
                QTest.qWait(20)
        fetch.assert_called_once_with(core.fsr4vk_dir())
