import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Visuals: pick a preset, change the few settings most players touch; the rest is one tap away
// in Advanced settings (SettingsWorkspace on the Visuals category).
Item {
    id: studio
    objectName: "visualsWorkspace"
    signal advancedRequested(string section, string key)
    readonly property var summaryKeys: ["upscaler", "preset", "fps_mode", "frame_gen", "ray_tracing"]
    function openAt(section, key) { advancedRequested(section || "", key || "") }
    // The tuned presets, on one line of their own after the card they were tuned for
    // ("RTX 4090 | 4080   Remastered DLSS 4 | DLSS 5"; measured on an RTX 4090, core.PRESET_TAGS).
    readonly property var featuredPresets: ["remastered", "dlss5_ready"]
    // The paragraph under the rows: the chosen everyday preset (a tuned one has its own "?").
    // The ★ line only where no tuned preset is suggested (e.g. Ultra on an RTX 3090).
    readonly property bool featuredChosen: featuredPresets.indexOf(launcher.graphicsPreset) >= 0
    readonly property string presetInfoText: (launcher.graphicsPreset === "custom" ? "Custom: your own changes, not saved yet. Save settings (top right) keeps them; they load every time the launcher starts." : launcher.presetDescription(launcher.graphicsPreset)) +
        (launcher.presetSuggestion !== "" && !featuredPresets.some(n => launcher.presetMarks[n] !== undefined) ? "  " + launcher.presetSuggestion : "")
    readonly property var featuredTitles: ({ "remastered": "Remastered  DLSS 4", "dlss5_ready": "DLSS 5" })

    // One preset pill: the name and, under it, the ★ suggestion mark. A tuned preset is one line,
    // its title with the mark in front ("★ Remastered  DLSS 4").
    component PresetButton: Button {
        id: presetButton
        property string name
        readonly property bool selected: name === "custom" ? ["custom", "mine"].indexOf(launcher.graphicsPreset) >= 0
                                                           : launcher.graphicsPreset === name
        readonly property bool suggested: launcher.presetMarks[name] !== undefined
        readonly property string title: studio.featuredTitles[name] ? (suggested ? "★ " : "") + studio.featuredTitles[name] : launcher.presetLabel(name)
        readonly property string sub: !studio.featuredTitles[name] && suggested ? "★" : ""
        objectName: "studioPreset_" + name
        hoverEnabled: true
        leftPadding: 6; rightPadding: studio.featuredTitles[name] ? 32 : 6  // room for the "?"
        text: title + (sub ? " " + sub : "")
        onClicked: name !== "custom" ? launcher.applyGraphicsPreset(name)
                 : launcher.hasMySettings && launcher.graphicsPreset !== "custom" ? launcher.applyGraphicsPreset("mine")
                 : studio.openAt("", "")
        contentItem: Column {
            spacing: 1
            Text { width: parent.width; text: presetButton.title; color: presetButton.selected ? Theme.primaryText : Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                // Without the ★ line, the name sits in the middle of the pill.
                topPadding: presetButton.sub ? 0 : Math.max(0, (presetButton.availableHeight - contentHeight) / 2) }
            Text { width: parent.width; visible: presetButton.sub !== ""; text: presetButton.sub; color: presetButton.selected ? Theme.primaryText : Theme.textDim; font.family: Theme.sans; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
        }
        background: Rectangle { radius: height / 2; color: presetButton.selected ? "#ffffff" : presetButton.hovered ? Theme.surfaceHover : "transparent"; border.color: presetButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2
            Behavior on color { ColorAnimation { duration: Theme.motionFast } } }
        // A tuned preset's own "?": its description and why it is suggested, on hover.
        Rectangle {
            id: infoMark
            objectName: "presetInfo_" + presetButton.name
            visible: !!studio.featuredTitles[presetButton.name]
            readonly property bool open: infoHover.hovered
            // presetMarks: a slot call alone would not follow the GPU check
            readonly property string tip: (launcher.presetMarks, launcher.presetInfo(presetButton.name))
            width: 22; height: 22; radius: 11
            anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter
            color: "transparent"; border.width: 1
            border.color: presetButton.selected ? Theme.primaryText : open ? Theme.lineFocus : Theme.textFaint
            Text { anchors.centerIn: parent; text: "?"; color: presetButton.selected ? Theme.primaryText : Theme.textDim; font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.Bold }
            HoverHandler { id: infoHover }
            ToolTip {
                objectName: "presetInfoTip_" + presetButton.name
                visible: parent.open
                x: parent.width - width; y: parent.height + 10
                width: 480
                padding: 14
                contentItem: Text { text: infoMark.tip; wrapMode: Text.WordWrap; lineHeight: 1.3
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 13 }
                background: Rectangle { radius: 14; color: Theme.base; border.color: Theme.lineStrong }
            }
        }
    }
    function quickFields(keys) {
        var rows = []
        for (var section of launcher.categorySections("Visuals")) rows = rows.concat(launcher.sectionFields("Visuals", section))
        return keys.map(key => rows.find(row => row.key === key)).filter(row => !!row).map(row => Object.assign({}, row, {hint: ""}))
    }

    Flickable {
        id: scroll
        anchors.fill: parent
        clip: true; boundsBehavior: Flickable.StopAtBounds
        contentHeight: column.implicitHeight + Theme.pageTop + 16
        ScrollBar.vertical: GlassScrollBar {}
        ColumnLayout {
            id: column
            // Wide windows: the shortcuts (HD textures, DLSS 5 neural, Advanced settings) in a
            // column on the right, as the Co-op page's side card; narrow ones keep them below.
            readonly property int sideWidth: 340
            readonly property bool wide: scroll.width - 48 >= Theme.columnWidth + 20 + sideWidth
            width: wide ? Theme.columnWidth + 20 + sideWidth : Math.min(Theme.columnWidth, scroll.width - 48)
            x: (scroll.width - width) / 2; y: Theme.pageTop
            spacing: 0
            Text { text: "Visuals"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 40; font.weight: Font.Bold }
            Text { Layout.topMargin: 4; text: "Pick a look. Fine-tune only if you want to."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }

            GridLayout {
            Layout.topMargin: 22; Layout.fillWidth: true
            columns: column.wide ? 2 : 1; columnSpacing: 20; rowSpacing: 12
            GlassPanel {
                Layout.fillWidth: true; Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: card.implicitHeight + 40
                ColumnLayout {
                    id: card
                    x: 20; y: 20; width: parent.width - 40; spacing: 0
                    // Two rows: the everyday presets, then the two tuned ones with what they were
                    // tuned on (RTX 4090 measurements, core.PRESET_TAGS); each row is a pill track.
                    Rectangle {
                        id: presetTrack
                        // "Custom" last, one pill for your own settings: the saved set ('mine') and
                        // changes not saved yet ('custom'). It loads the saved set, or opens Advanced
                        // settings when there is none or you are already changing things.
                        readonly property var names: launcher.graphicsPresets.filter(n => studio.featuredPresets.indexOf(n) < 0 && n !== "mine").concat(["custom"])
                        // Taller with a suggestion mark (★ on its own line, e.g. Ultra on an RTX 3090).
                        readonly property bool marked: names.some(n => launcher.presetMarks[n] !== undefined)
                        function weight(name) { return 1 }
                        readonly property real totalWeight: names.reduce((sum, name) => sum + weight(name), 0)
                        Layout.fillWidth: true; Layout.preferredHeight: marked ? 56 : 44
                        radius: height / 2
                        color: Theme.well
                        border.color: Theme.line
                        Row {
                            x: 4; y: 4; spacing: 2
                            Repeater {
                                model: presetTrack.names
                                delegate: PresetButton {
                                    required property string modelData
                                    name: modelData
                                    width: (presetTrack.width - 8 - 2 * (presetTrack.names.length - 1)) * presetTrack.weight(modelData) / presetTrack.totalWeight
                                    height: presetTrack.height - 8
                                }
                            }
                        }
                    }
                    RowLayout {
                        objectName: "featuredPresets"
                        visible: featuredTrack.names.length > 0
                        Layout.topMargin: 10; Layout.fillWidth: true; spacing: 16
                        // First the card, then the preset. Only RTX 4090 settings exist (measured
                        // there): RTX 4080 is greyed out until it has its own.
                        Rectangle {
                            objectName: "featuredPresetsCard"
                            Layout.preferredWidth: 220; Layout.preferredHeight: 44
                            radius: height / 2
                            color: Theme.well
                            border.color: Theme.line
                            Row {
                                x: 4; y: 4; spacing: 2
                                Repeater {
                                    model: [{ card: "4090", ready: true }, { card: "4080", ready: false }]
                                    delegate: Button {
                                        id: cardButton
                                        required property var modelData
                                        objectName: "tunedCard_" + modelData.card
                                        width: (220 - 10) / 2; height: 36
                                        enabled: modelData.ready
                                        hoverEnabled: true
                                        text: "RTX " + modelData.card
                                        ToolTip.visible: hovered && !modelData.ready
                                        ToolTip.text: "No RTX 4080 settings yet"
                                        contentItem: Text { text: cardButton.text; color: cardButton.enabled ? Theme.primaryText : Theme.textMuted
                                            font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold
                                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                        background: Rectangle { radius: height / 2; color: cardButton.enabled ? "#ffffff" : "transparent"; opacity: cardButton.enabled ? 1 : 0.5 }
                                    }
                                }
                            }
                        }
                        Rectangle {
                            id: featuredTrack
                            readonly property var names: launcher.graphicsPresets.filter(n => studio.featuredPresets.indexOf(n) >= 0)
                            Layout.fillWidth: true; Layout.preferredHeight: 44
                            radius: height / 2
                            color: Theme.well
                            border.color: Theme.line
                            Row {
                                x: 4; y: 4; spacing: 2
                                Repeater {
                                    model: featuredTrack.names
                                    delegate: PresetButton {
                                        required property string modelData
                                        name: modelData
                                        width: (featuredTrack.width - 8 - 2 * (featuredTrack.names.length - 1)) / featuredTrack.names.length
                                        height: featuredTrack.height - 8
                                    }
                                }
                            }
                        }
                    }
                    Text {
                        objectName: "presetDescription"
                        visible: !studio.featuredChosen
                        Layout.topMargin: 12; Layout.fillWidth: true; Layout.leftMargin: 4
                        wrapMode: Text.WordWrap; lineHeight: 1.3
                        color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13
                        text: studio.presetInfoText
                    }
                    Rectangle {
                        Layout.topMargin: 16; Layout.fillWidth: true
                        Layout.preferredHeight: summary.implicitHeight
                        radius: 18; color: Theme.well
                        Column {
                            id: summary
                            width: parent.width
                            Repeater {
                                model: launcher.settingsRevision < 0 ? [] : studio.quickFields(studio.summaryKeys)
                                delegate: FieldRow { required property var modelData; width: summary.width; field: modelData; controlWidth: Math.min(340, width * 0.5) }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                objectName: "visualsShortcuts"
                Layout.preferredWidth: column.wide ? column.sideWidth : -1
                Layout.fillWidth: !column.wide; Layout.alignment: Qt.AlignTop
                spacing: 10
                // Save settings: what this page shows, loaded at every launcher start (a preset
                // stays that preset, e.g. Ultra; anything else is the Custom pill).
                // core.MY_SETTINGS_INI / MY_SETTINGS_APP.
                GlassButton {
                    id: saveMine
                    objectName: "saveMySettings"
                    property bool saved: false
                    Layout.fillWidth: true; Layout.preferredHeight: 44
                    highlighted: launcher.graphicsPreset === "custom"
                    text: saved ? "Saved ✓" : "Save settings"
                    onClicked: { launcher.saveMySettings(); saved = true; savedTimer.restart() }
                    Timer { id: savedTimer; interval: 2500; onTriggered: saveMine.saved = false }
                }
                Rectangle {
                    Layout.topMargin: 6
                    Layout.fillWidth: true; Layout.preferredHeight: sideFields.implicitHeight
                    radius: 18; color: Theme.well
                    Column {
                        id: sideFields
                        width: parent.width
                        Repeater {
                            model: launcher.settingsRevision < 0 ? [] : studio.quickFields(["hdr"])
                            delegate: FieldRow { required property var modelData; width: sideFields.width; field: modelData; controlWidth: Math.min(160, width * 0.4) }
                        }
                    }
                }
                Text { visible: column.wide; Layout.topMargin: 6; Layout.leftMargin: 6; text: "More visuals"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold }
                MenuRow {
                    objectName: "openHdTextures"
                    Layout.fillWidth: true
                    icon: "texture"; label: "HD textures"
                    value: launcher.hdPackState === "busy" ? "Building " + Math.round(launcher.hdPackProgress * 100) + "%" :
                           launcher.hdPackState === "on" ? "On" : launcher.hdPackState === "off" ? "Off" : "Set up"
                    onClicked: studio.openAt("High-resolution textures", "")
                }
                MenuRow {
                    objectName: "openNeuralRendering"
                    Layout.fillWidth: true
                    icon: "neural"; label: "DLSS 5 neural"
                    value: !launcher.neuralRuntimeInstalled ? "No runtime" : launcher.dlss5On ? "On" : "Off"
                    onClicked: studio.openAt("Neural rendering (DLSS 5)", "")
                }
                MenuRow {
                    objectName: "openGraphicsAdvanced"
                    Layout.fillWidth: true
                    icon: "sliders"; label: "Advanced settings"
                    value: "Every option"
                    onClicked: studio.openAt("", "")
                }
            }
            }
        }
    }
}
