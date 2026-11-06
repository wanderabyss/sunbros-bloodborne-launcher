# SPDX-License-Identifier: GPL-2.0-or-later
"""Setting rows show their whole label: a long one wraps, a switch's row doesn't save room for a dropdown."""
import os

from PySide6.QtTest import QTest
import test_workspace_navigation_qml as navigation


class FieldRowTests(navigation.WorkspaceNavigationTests):
    def visible_labels(self):
        return {item.property('text'): item for item in self.items()
                if item.metaObject().className().startswith('QQuickText')
                and item.isVisible() and item.property('text')}

    def test_built_in_enhancements_show_whole_labels(self):
        import bbport_launcher_win as core
        self.window.resize(1280, 800)
        self.click('primary_Mods')
        self.click('workshop_Built_in_enhancements')
        QTest.qWait(100)
        labels = self.visible_labels()
        for _key, (english, _russian), _on in core.ENHANCEMENTS:
            shown = labels.get(english)
            self.assertIsNotNone(shown, english)
            self.assertFalse(shown.property('truncated'), english)
            self.assertGreaterEqual(shown.height(), shown.property('contentHeight'), english)
        # A short label stays on one line.
        self.assertEqual(labels[core.ENHANCEMENTS[0][1][0]].property('lineCount'), 1)
        path = os.environ.get('BB_TEST_FIELD_ROW_PNG')
        if path:
            self.window.grabWindow().save(path)
