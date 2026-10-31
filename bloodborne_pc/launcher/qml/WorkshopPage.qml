import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Workshop: mods, built-in enhancements, the map and patches at a glance. Each row opens its
// section in Workshop details (SettingsWorkspace on Mods & Patches).
Item {
    id: workshop
    objectName: "modsWorkspace"
    signal detailsRequested(string section)
    function openAt(section, key) { detailsRequested(section || "Installed mods") }
    function onCount(section) {
        if (launcher.settingsRevision < 0) return 0
        return launcher.sectionFields("Mods & Patches", section).filter(row => row.kind === "toggle" && launcher.checked(row.key)).length
    }
    function sectionValue(section) {
        if (section === "Installed mods") return launcher.contentMods.length === 0 ? "None" : launcher.contentMods.length + " installed"
        if (section === "Hunter's Atlas (map)") return launcher.checked("atlas_enabled") ? "On" : "Off"
        if (section === "External patches") return launcher.patches.length === 0 ? "None" : launcher.patches.length + " found"
        return onCount(section) + " on"
    }
    property int tick: 0
    Connections { target: launcher; function onChanged() { workshop.tick++ } }

    Flickable {
        id: scroll
        anchors.fill: parent
        clip: true; boundsBehavior: Flickable.StopAtBounds
        contentHeight: column.implicitHeight + Theme.pageTop + 16
        ScrollBar.vertical: GlassScrollBar {}
        ColumnLayout {
            id: column
            width: Math.min(Theme.columnWidth, scroll.width - 48)
            x: (scroll.width - width) / 2; y: Theme.pageTop
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 4
                    Text { text: "Workshop"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 40; font.weight: Font.Bold }
                    Text { text: "Add-ons for your game. Changes apply the next time you play."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }
                }
                Item { Layout.fillWidth: true }
                GlassButton { objectName: "openModsFolder"; text: "Open mods folder"; Layout.preferredWidth: 170; Layout.preferredHeight: 44; Layout.alignment: Qt.AlignBottom; onClicked: launcher.action("openMods") }
            }

            GlassPanel {
                Layout.topMargin: 22; Layout.fillWidth: true
                Layout.preferredHeight: card.implicitHeight + 40
                ColumnLayout {
                    id: card
                    x: 20; y: 20; width: parent.width - 40; spacing: 0
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: rows.implicitHeight
                        radius: 18; color: Theme.well
                        Column {
                            id: rows
                            width: parent.width
                            ToggleRow {
                                objectName: "modsEnabledRow"
                                label: "Load mods"; hint: "Off starts the game with none, whatever is in the folder."
                                checked: workshop.tick >= 0 && launcher.checked("mods_enabled")
                                onToggled: (on) => launcher.setValue("mods_enabled", on)
                            }
                            Repeater {
                                model: [
                                    {section: "Installed mods", icon: "puzzle"},
                                    {section: "Built-in enhancements", icon: "star"},
                                    {section: "Hunter's Atlas (map)", icon: "map"},
                                    {section: "External patches", icon: "patch"},
                                    {section: "Gameplay tweaks", icon: "controls"},
                                    {section: "Cheats", icon: "bolt"}
                                ]
                                delegate: Button {
                                    id: sectionRow
                                    required property var modelData
                                    required property int index
                                    objectName: "workshop_" + modelData.section.replace(/[^a-zA-Z0-9]/g, "_")
                                    width: rows.width; height: 52
                                    hoverEnabled: true
                                    onClicked: workshop.detailsRequested(modelData.section)
                                    contentItem: Item {
                                        NavIcon { x: 16; anchors.verticalCenter: parent.verticalCenter; width: 19; height: 19; stroke: 1.9; kind: sectionRow.modelData.icon; strokeColor: Theme.text }
                                        Text { x: 50; anchors.verticalCenter: parent.verticalCenter; text: sectionRow.modelData.section; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15 }
                                        Text { anchors.right: chevron.left; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                                            text: workshop.tick >= 0 ? workshop.sectionValue(sectionRow.modelData.section) : ""; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
                                        NavIcon { id: chevron; anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; width: 13; height: 13; stroke: 2.2; kind: "chevron"; strokeColor: Theme.textFaint }
                                    }
                                    background: Rectangle {
                                        color: sectionRow.hovered ? "#14ffffff" : "transparent"
                                        Rectangle { visible: sectionRow.index < 5; x: 16; anchors.bottom: parent.bottom; width: parent.width - 16; height: 1; color: Theme.line }
                                        Rectangle { visible: sectionRow.index === 0; x: 16; anchors.top: parent.top; width: parent.width - 16; height: 1; color: Theme.line }
                                    }
                                }
                            }
                        }
                    }
                    Rectangle {
                        objectName: "modsDropArea"
                        Layout.topMargin: 14; Layout.fillWidth: true; Layout.preferredHeight: 88
                        radius: 18; color: "#1a000000"
                        border.color: "#4dffffff"; border.width: 1
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 20; spacing: 16
                            Rectangle {
                                Layout.preferredWidth: 48; Layout.preferredHeight: 48; radius: 14; color: Theme.surface
                                NavIcon { anchors.centerIn: parent; width: 22; height: 22; stroke: 1.9; kind: "download"; strokeColor: Theme.text }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 2
                                Text { text: launcher.contentMods.length === 0 ? "No mods yet" : launcher.contentMods.length + " mods in the folder"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold }
                                Text { Layout.fillWidth: true; text: "Put each mod in its own folder in the mods folder, then refresh."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13; elide: Text.ElideRight }
                            }
                            GlassButton { objectName: "refreshMods"; text: "Refresh"; Layout.preferredWidth: 100; Layout.preferredHeight: 36; onClicked: launcher.refresh_addons() }
                        }
                    }
                }
            }
        }
    }
}
