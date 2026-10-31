"""Tab bar routes, on-demand pages, and the advanced pages behind Visuals and Workshop."""
import os
from pathlib import Path
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
import test_home_dashboard_qml as home_tests


class WorkspaceNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home_tests.HomeDashboardTests.setUpClass()

    def setUp(self):
        # saveSettings shows a modal "Settings Saved" box unless PYTEST_CURRENT_TEST is set;
        # under unittest it would block the run forever.
        dialog = mock.patch.object(QMessageBox, 'information')
        self.dialog = dialog.start()
        self.addCleanup(dialog.stop)
        self.fixture = home_tests.HomeDashboardTests()
        self.fixture.setUp()
        self.fixture.view.hide()
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('launcher', self.fixture.backend)
        path = Path(__file__).resolve().parents[1] / 'launcher/qml/Main.qml'
        self.engine.load(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.engine.rootObjects(), 'Main.qml did not load')
        self.window = self.engine.rootObjects()[0]
        QTest.qWait(50)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        self.fixture.tearDown()
        self.fixture.doCleanups()
        self.fixture.app.processEvents()

    def items(self):
        pending = [self.window.contentItem()]
        result = []
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(item.childItems())
        self._retained_items = result
        return result

    def item(self, name):
        for item in self.items():
            if item.objectName() == name:
                return item
        self.fail('Missing item: ' + name)

    def click(self, name):
        item = self.item(name)
        self.scroll_into_view(item)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        self.fixture.app.processEvents()

    def scroll_into_view(self, item):
        """Scrolls the page (a Flickable) as a player would when item is below the window."""
        page = item.parentItem()
        while page is not None and page.property('contentY') is None:
            page = page.parentItem()
        if page is None:
            return
        bottom = item.mapToItem(page, item.boundingRect().bottomLeft()).y()
        if bottom > page.height():
            page.setProperty('contentY', page.property('contentY') + bottom - page.height() + 20)
            self.fixture.app.processEvents()

    def within(self, root_name, name):
        pending = [self.item(root_name)]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail('Missing item %s inside %s' % (name, root_name))

    def test_primary_routes_are_distinct_and_keep_navigation(self):
        pages = [('Visuals', 'visualsWorkspace'), ('Online', 'onlineWorkspace'), ('Coop', 'coopWorkspace'),
                 ('Dossier', 'dossierWorkspace'), ('Mods', 'modsWorkspace'), ('Settings', 'preferencesPage'),
                 ('Home', 'homeDashboard')]
        for page, workspace in pages:
            with self.subTest(page=page):
                self.click('primary_' + page)
                self.assertEqual(self.window.property('page'), page)
                self.assertTrue(self.item(workspace).isVisible())
                self.assertTrue(self.item('primaryNavigation').isVisible())
                others = [name for _, name in pages if name != workspace]
                self.assertFalse(any(item.isVisible() for item in self.items() if item.objectName() in others))

    def test_pages_are_built_on_first_visit(self):
        names = [item.objectName() for item in self.items()]
        self.assertIn('homeDashboard', names)
        for name in ['visualsWorkspace', 'settingsWorkspace', 'coopWorkspace', 'dossierWorkspace']:
            self.assertNotIn(name, names, name + ' was built before it was opened')

    def test_task_editors_are_scoped_and_preferences_exclude_them(self):
        self.click('primary_Visuals')
        self.click('openGraphicsAdvanced')
        self.assertEqual(self.window.property('page'), 'VisualsAdvanced')
        editor = self.item('visualsAdvanced')
        self.assertEqual(editor.property('category'), 'Visuals')
        self.assertEqual(editor.property('categories').toVariant() if hasattr(editor.property('categories'), 'toVariant')
                         else editor.property('categories'), ['Visuals'])
        self.assertTrue(self.item('primaryNavigation').isVisible())
        self.click('settingsBack')
        self.assertEqual(self.window.property('page'), 'Visuals')
        self.click('primary_Mods')
        self.click('workshop_Gameplay_tweaks')
        self.assertEqual(self.window.property('page'), 'ModsAdvanced')
        self.assertEqual(self.item('modsAdvanced').property('category'), 'Mods & Patches')
        self.assertEqual(self.item('modsAdvanced').property('section'), 'Gameplay tweaks')
        self.click('primary_Settings')
        for section in ['section_Button_prompts', 'section_Save_backups', 'section_Logs']:
            self.assertTrue(self.within('preferencesPage', section).isVisible())
        pending, names = [self.item('preferencesPage')], []
        while pending:
            item = pending.pop()
            names.append(item.objectName())
            pending.extend(item.childItems())
        for section in ['section_Upscaling', 'section_Ray_tracing', 'section_Gameplay_tweaks']:
            self.assertNotIn(section, names)
        point = self.within('preferencesPage', 'section_Logs')
        center = point.mapToScene(point.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, center)
        self.fixture.app.processEvents()
        self.assertEqual(self.item('preferencesPage').property('selectedCategory'), 'System')

    def test_home_shortcuts_and_dossier_close_use_top_level_routes(self):
        self.click('mode_coop')
        self.click('launchHunt')
        self.assertEqual(self.window.property('page'), 'Coop')
        self.assertTrue(self.item('coopWorkspace').isVisible())
        self.click('primary_Home')
        self.click('openDossier')
        self.assertEqual(self.window.property('page'), 'Dossier')
        self.click('primary_Settings')
        self.assertTrue(self.item('preferencesPage').isVisible())

    def test_preferences_search_does_not_reintroduce_dedicated_tasks(self):
        self.click('primary_Settings')
        search = self.within('preferencesPage', 'settingsSearch')
        results = self.within('preferencesPage', 'preferenceSearchResults')
        search.setProperty('text', 'ray tracing')
        self.fixture.app.processEvents()
        hits = results.property('hits')
        hits = hits.toVariant() if hasattr(hits, 'toVariant') else hits
        self.assertEqual(hits, [])
        search.setProperty('text', 'mouse')
        self.fixture.app.processEvents()
        hits = results.property('hits')
        hits = hits.toVariant() if hasattr(hits, 'toVariant') else hits
        self.assertTrue(hits)
        self.assertTrue(all(hit['category'] == 'Controls' for hit in hits))

if __name__ == '__main__':
    unittest.main()
