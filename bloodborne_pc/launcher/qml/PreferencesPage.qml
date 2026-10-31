import QtQuick

// Settings: controls, game files and saves, and the launcher itself, in one sidebar.
Item {
    id: preferences
    objectName: "preferencesPage"
    signal openSetup(int step)
    readonly property string selectedCategory: editor.category
    function openAt(category, section, key) { editor.openAt(category || "Controls", section || "", key || "") }
    SettingsWorkspace {
        id: editor
        anchors.fill: parent
        categories: ["Controls", "Game & Saves", "System"]
        category: "Controls"
        onOpenSetup: (step) => preferences.openSetup(step)
    }
}
