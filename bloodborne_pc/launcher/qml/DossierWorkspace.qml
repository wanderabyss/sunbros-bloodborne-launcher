import QtQuick
import QtQuick.Shapes
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

// Dossier: your hunter and the trophies you have earned, read from the save.
Item {
    id: dossier
    objectName: "dossierWorkspace"
    signal closeRequested()
    readonly property var profile: launcher.profileData || ({})
    readonly property var trophies: profile.trophies || (profile.earned_trophies || []).concat(profile.locked_trophies || [])
    property string categoryFilter: "All"
    property var selectedTrophy: ({})
    readonly property var filteredTrophies: trophies.filter(trophy =>
        (categoryFilter === "All" || trophy.category === categoryFilter) &&
        (stateFilter.currentIndex === 0 || (stateFilter.currentIndex === 1 ? trophy.unlocked : !trophy.unlocked)) &&
        ((trophy.name || "") + " " + (trophy.description || "")).toLowerCase().indexOf(search.text.toLowerCase()) !== -1)
    readonly property real earned: Number(profile.trophies_earned || 0)
    readonly property real total: Math.max(1, Number(profile.trophies_total || 40))
    function gradeColor(grade) { return grade === "P" ? "#bfe3ff" : grade === "G" ? "#ffd60a" : grade === "S" ? "#e5e5ea" : "#ffb340" }
    onVisibleChanged: { if (visible) launcher.refresh_profile_data() }

    ColumnLayout {
        id: heading
        x: 64; y: Theme.pageTop; width: parent.width - 128; spacing: 4
        Text { text: "Dossier"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 40; font.weight: Font.Bold }
        Text { text: "Your hunter and the trophies you've earned."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }
    }

    // --- Your hunter ---------------------------------------------------------------------------
    GlassPanel {
        id: hunterCard
        objectName: "hunterCard"
        x: 64; y: heading.y + heading.height + 24
        width: 340; height: parent.height - y
        ColumnLayout {
            x: 24; y: 24; width: parent.width - 48; spacing: 0
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 76; height: 76; radius: 38; color: "#4dffffff"
                Image {
                    id: avatar
                    anchors.fill: parent; anchors.margins: 3
                    visible: false
                    source: launcher.userAvatar || Qt.resolvedUrl("../assets/ui/sunbros-avatar.png")
                    sourceSize.width: 140; fillMode: Image.PreserveAspectCrop; cache: false; smooth: true; mipmap: true
                }
                // A round avatar: the image masked by a circle.
                Rectangle { id: avatarMask; anchors.fill: avatar; radius: width / 2; visible: false; layer.enabled: true }
                MultiEffect {
                    anchors.fill: avatar; source: avatar
                    maskEnabled: true; maskSource: avatarMask
                    maskThresholdMin: 0.5; maskSpreadAtMin: 1.0
                }
            }
            Text { Layout.topMargin: 10; Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: parent.width; elide: Text.ElideRight
                text: dossier.profile.valid ? (dossier.profile.name || "Hunter") : "No hunter yet"
                color: Theme.text; font.family: Theme.sans; font.pixelSize: 24; font.weight: Font.Bold }
            Text { Layout.topMargin: 2; Layout.alignment: Qt.AlignHCenter
                text: dossier.profile.valid ? "Level " + dossier.profile.level + "  ·  " + (dossier.profile.play_time || "--") : "Play to create a character."
                color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
            RowLayout {
                Layout.topMargin: 18; Layout.fillWidth: true
                Repeater {
                    model: [{label: "Echoes", value: dossier.profile.blood_echoes || 0}, {label: "Insight", value: dossier.profile.insight || 0}, {label: "Deaths", value: dossier.profile.deaths || 0}]
                    delegate: Column {
                        required property var modelData
                        Layout.fillWidth: true; spacing: 1
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: Number(modelData.value).toLocaleString(Qt.locale(), "f", 0); color: Theme.text; font.family: Theme.sans; font.pixelSize: 22; font.weight: Font.Bold }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12 }
                    }
                }
            }
            Rectangle {
                objectName: "attributes"
                Layout.topMargin: 20; Layout.fillWidth: true; Layout.preferredHeight: attrs.implicitHeight + 20
                radius: 18; color: Theme.well
                Column {
                    id: attrs
                    x: 16; y: 10; width: parent.width - 32
                    Repeater {
                        model: [{k: "Vitality", v: dossier.profile.vitality}, {k: "Endurance", v: dossier.profile.endurance}, {k: "Strength", v: dossier.profile.strength},
                                {k: "Skill", v: dossier.profile.skill}, {k: "Bloodtinge", v: dossier.profile.bloodtinge}, {k: "Arcane", v: dossier.profile.arcane}]
                        delegate: Item {
                            required property var modelData
                            width: attrs.width; height: 30
                            Text { width: 92; anchors.verticalCenter: parent.verticalCenter; text: modelData.k; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
                            Rectangle {
                                x: 100; width: parent.width - 136; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: "#26ffffff"
                                Rectangle { width: parent.width * Math.min(1, Number(modelData.v || 0) / 99); height: 6; radius: 3; color: "#ffffff" }
                            }
                            Text { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: modelData.v === undefined ? "–" : String(modelData.v); color: Theme.text; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold }
                        }
                    }
                }
            }
        }
    }

    // --- Trophies ------------------------------------------------------------------------------
    GlassPanel {
        id: trophyCard
        objectName: "trophyCard"
        x: hunterCard.x + hunterCard.width + 20; y: hunterCard.y
        width: parent.width - x - 64; height: parent.height - y
        ColumnLayout {
            id: trophyHead
            x: 24; y: 22; width: parent.width - 48; spacing: 14
            RowLayout {
                Layout.fillWidth: true; spacing: 16
                Shape {
                    id: ring
                    width: 56; height: 56
                    property real progress: Math.min(1, dossier.earned / dossier.total)
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: "#2effffff"; strokeWidth: 7; fillColor: "transparent"
                        PathAngleArc { centerX: 28; centerY: 28; radiusX: 23; radiusY: 23; startAngle: 0; sweepAngle: 360 }
                    }
                    ShapePath {
                        strokeColor: ring.progress > 0 ? "#ffd60a" : "transparent"; strokeWidth: 7; fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 28; centerY: 28; radiusX: 23; radiusY: 23; startAngle: -90; sweepAngle: 360 * ring.progress }
                    }
                    Accessible.name: Math.round(progress * 100) + "% of trophies earned"
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 1
                    Text { text: "Trophies"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 24; font.weight: Font.Bold }
                    Text { text: dossier.earned + " of " + dossier.total + " earned"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
                }
                Rectangle {
                    id: stateFilter
                    objectName: "trophyStateFilter"
                    property int currentIndex: 0
                    radius: 20; height: 40; width: stateRow.implicitWidth + 8; color: Theme.well
                    Row {
                        id: stateRow
                        x: 4; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                        Repeater {
                            model: ["All", "Earned", "Locked"]
                            delegate: Button {
                                id: stateButton
                                required property string modelData
                                required property int index
                                objectName: "trophyState_" + modelData
                                width: stateText.implicitWidth + 28; height: 32; hoverEnabled: true
                                onClicked: stateFilter.currentIndex = index
                                contentItem: Text { id: stateText; text: stateButton.modelData; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                background: Rectangle { radius: height / 2; color: stateFilter.currentIndex === stateButton.index ? "#42ffffff" : stateButton.hovered ? "#14ffffff" : "transparent" }
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                GlassTextField { id: search; objectName: "trophySearch"; Layout.fillWidth: true; Layout.preferredHeight: 36; placeholderText: "Search trophies" }
                Repeater {
                    model: ["All", "Boss", "Story", "Equipment", "Chalice"]
                    delegate: Button {
                        id: categoryButton
                        required property string modelData
                        objectName: "trophyCategory_" + modelData
                        Layout.preferredHeight: 34; Layout.preferredWidth: categoryText.implicitWidth + 26
                        hoverEnabled: true
                        onClicked: dossier.categoryFilter = modelData
                        contentItem: Text { id: categoryText; text: categoryButton.modelData; color: dossier.categoryFilter === categoryButton.modelData ? Theme.primaryText : Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { radius: height / 2; color: dossier.categoryFilter === categoryButton.modelData ? "#ffffff" : categoryButton.hovered ? Theme.surfaceHover : Theme.surface }
                    }
                }
            }
            Note { visible: dossier.filteredTrophies.length === 0; Layout.fillWidth: true; text: dossier.trophies.length === 0 ? "Trophy details appear once save and trophy data are available." : "No trophies match these filters." }
        }
        GridView {
            id: grid
            objectName: "trophyGrid"
            x: 24; y: trophyHead.y + trophyHead.height + 16
            width: parent.width - 34; height: parent.height - y - 18
            clip: true; boundsBehavior: Flickable.StopAtBounds
            readonly property int columns: Math.max(2, Math.floor(width / 230))
            cellWidth: width / columns; cellHeight: 92
            model: dossier.filteredTrophies
            ScrollBar.vertical: GlassScrollBar {}
            delegate: Button {
                id: trophyButton
                required property var modelData
                objectName: "trophy_" + modelData.id
                width: grid.cellWidth - 10; height: grid.cellHeight - 10
                hoverEnabled: true
                onClicked: { dossier.selectedTrophy = modelData; detail.open() }
                Accessible.name: modelData.name + (modelData.unlocked ? ", earned" : ", locked")
                background: Rectangle { radius: 18; color: trophyButton.hovered ? "#24ffffff" : Theme.well; border.color: trophyButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2 }
                contentItem: Item {
                    Image {
                        id: icon
                        x: 2; anchors.verticalCenter: parent.verticalCenter; width: 60; height: 60
                        source: Qt.resolvedUrl("../assets/trophies/" + trophyButton.modelData.icon)
                        sourceSize.width: 120; fillMode: Image.PreserveAspectCrop
                        opacity: trophyButton.modelData.unlocked ? 1 : 0.45
                    }
                    Column {
                        x: icon.width + 14; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x; spacing: 4
                        Text { width: parent.width; text: trophyButton.modelData.name; color: Theme.text; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight }
                        Row { spacing: 0
                            Text { text: trophyButton.modelData.grade_name || trophyButton.modelData.grade; color: dossier.gradeColor(trophyButton.modelData.grade); font.family: Theme.sans; font.pixelSize: 12 }
                            Text { text: "  ·  "; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12 }
                            Text { text: trophyButton.modelData.unlocked ? "Earned" : "Locked"; color: trophyButton.modelData.unlocked ? Theme.goodText : Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12 }
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: detail
        x: (dossier.width - width) / 2; y: 100; width: Math.min(480, dossier.width - 72); height: details.implicitHeight + 48
        focus: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        scale: Theme.zoom; transformOrigin: Popup.Top
        background: Rectangle { radius: 24; color: "#f22a2d34"; border.color: Theme.lineStrong }
        Column { id: details; anchors.fill: parent; anchors.margins: 12; spacing: 12
            Text { text: dossier.selectedTrophy.name || ""; width: parent.width; color: Theme.text; font.family: Theme.sans; font.pixelSize: 22; font.weight: Font.Bold; wrapMode: Text.Wrap }
            Text { text: dossier.selectedTrophy.description || ""; width: parent.width; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14; wrapMode: Text.Wrap }
            Text { text: dossier.selectedTrophy.unlocked ? (dossier.selectedTrophy.unlocked_at || "Earned") : "Locked"; color: dossier.selectedTrophy.unlocked ? Theme.goodText : Theme.textFaint; font.family: Theme.sans; font.pixelSize: 13 }
            GlassButton { text: "Close"; width: 100; height: 36; onClicked: detail.close() }
        }
    }
}
