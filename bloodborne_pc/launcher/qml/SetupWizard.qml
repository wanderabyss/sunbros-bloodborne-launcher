import QtQuick
import QtQuick.Controls

// First-time setup, four steps on the launcher's panel: welcome, game files, your data, finish.
Item {
    id: wizard
    objectName: "setupWizard"
    property int step: 0
    property int startStep: 0
    property var checks: launcher.readiness
    // A game folder with an older version is usable (amber); only a failed check blocks.
    property bool gameValid: checks[0].level !== "error"
    property bool savesValid: checks[2].level !== "error" && launcher.savesWritable
    readonly property int contentWidth: Math.min(wizard.width, 680)
    readonly property real neededHeight: 206 + [step0, step1, step2, step3][step].implicitHeight + 24 + 84
    signal exitRequested(string page)
    onVisibleChanged: if (visible) step = startStep

    function levelColor(level) {
        return level === "ready" ? Theme.good : level === "error" ? Theme.accent : Theme.warn
    }
    // Your data: red if a check failed, green only when every item is verified, amber otherwise.
    function dataLevel() {
        var levels = checks.slice(1).map(function(c) { return c.level })
        return levels.indexOf("error") >= 0 ? "error" : levels.every(function(l) { return l === "ready" }) ? "ready" : "warning"
    }
    function stepValid(index) { return index === 1 ? gameValid : index === 2 ? savesValid : true }
    function canReach(index) {
        for (var i = 0; i < index; i++)
            if (!stepValid(i)) return false
        return true
    }
    function skip() {
        if (!launcher.confirm("Skip setup?",
                "Any missing game files or unwritable saves will still block Play. You can finish setup later in Game & Saves.\n\nSkip setup anyway?"))
            return
        launcher.skipSetup()
        wizard.exitRequested("Home")
    }
    function finish(play) {
        if (!gameValid || !savesValid) {
            launcher.skipSetup()
            wizard.exitRequested("Home")
            return
        }
        launcher.completeSetup()
        wizard.exitRequested("Home")
        if (play) launcher.play()
    }

    // A status line: dot, label, detail.
    component Check: Row {
        property string level: "ready"
        property string label: ""
        property string detail: ""
        property string tag: ""
        width: parent ? parent.width : 400; spacing: 12
        Rectangle { width: 8; height: 8; radius: 4; y: 7; color: wizard.levelColor(level) }
        Column {
            width: parent.width - 20; spacing: 3
            Row {
                spacing: 10
                Text { text: label; color: Theme.text; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold }
                Text { visible: tag !== ""; text: tag; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
            }
            Text { width: parent.width; text: detail; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13; wrapMode: Text.WordWrap }
        }
    }
    component Body: Text {
        width: parent ? parent.width : 400; wrapMode: Text.WordWrap; lineHeight: 1.35
        color: Theme.text; font.family: Theme.sans; font.pixelSize: 15
    }

    // Breadcrumb and step count.
    Item {
        width: parent.width; height: 40
        Row {
            anchors.verticalCenter: parent.verticalCenter; spacing: 14
            Text { text: "SunBro's Edition"; color: Theme.gold; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { text: "/"; color: Theme.textFaint; font.pixelSize: 15 }
            Text { text: "First-time setup"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
        }
        Text {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: "Step " + (wizard.step + 1) + " of 4"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13
        }
    }
    Rectangle { y: 40; width: parent.width; height: 1; color: Theme.line }
    Text {
        y: 70; width: parent.width
        text: ["Welcome to Yharnam", "Add your game files", "Your data", "Ready to hunt"][wizard.step]
        color: Theme.text; font.family: Theme.sans; font.pixelSize: 34; font.weight: Font.Bold
    }

    // The steps: a bar each, crimson up to the current one, its name below.
    Row {
        y: 142; width: parent.width; spacing: 10
        Repeater {
            model: ["Welcome", "Game files", "Your data", "Finish"]
            delegate: Item {
                id: tab
                property bool current: index === wizard.step
                property bool reachable: index < wizard.step || wizard.canReach(index)
                property string level: index === 1 ? checks[0].level : index === 2 ? wizard.dataLevel() : ""
                width: (wizard.width - 30) / 4; height: 40
                opacity: reachable || current ? 1 : 0.45
                Rectangle { width: parent.width; height: 4; radius: 2; color: index <= wizard.step ? "#ffffff" : Theme.lineStrong }
                Row {
                    y: 14; spacing: 6
                    Text {
                        text: modelData; color: tab.current || (tabMouse.containsMouse && tab.reachable) ? Theme.text : Theme.textDim
                        font.family: Theme.sans; font.pixelSize: 13; font.weight: tab.current ? Font.DemiBold : Font.Normal
                    }
                    NavIcon {
                        visible: tab.level !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        width: 14; height: 14; stroke: 2.2
                        kind: tab.level === "ready" ? "check" : "alert"
                        strokeColor: wizard.levelColor(tab.level)
                    }
                }
                MouseArea {
                    id: tabMouse
                    anchors.fill: parent; hoverEnabled: true
                    enabled: tab.reachable && !tab.current
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: wizard.step = index
                }
            }
        }
    }

    Flickable {
        y: 206; width: parent.width; height: parent.height - y - 84
        clip: true; boundsBehavior: Flickable.StopAtBounds
        contentHeight: Math.max(step0.implicitHeight, step1.implicitHeight, step2.implicitHeight, step3.implicitHeight)

        Column {
            id: step0; width: wizard.contentWidth; spacing: 18; visible: wizard.step === 0
            Body { text: "This guide sets up your own copy of Bloodborne, checks the trophy pack and keeps your saves in the right place. It takes about two minutes." }
            Body { color: Theme.textDim; font.pixelSize: 14; text: "The game files and trophy key are not included in this download. You can skip setup and use the launcher straight away." }
            Rectangle {
                width: parent.width; height: hintText.implicitHeight + 32; radius: Theme.radius
                color: Theme.surface; border.color: Theme.line
                Text {
                    id: hintText; x: 18; y: 16; width: parent.width - 36; wrapMode: Text.WordWrap; lineHeight: 1.35
                    text: "Have cusa-03173.zip? The next step can unpack it and apply update 1.09. Already have a CUSA03173 folder? Point the launcher to the folder that contains eboot.bin."
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 13
                }
            }
        }

        Column {
            id: step1; width: wizard.contentWidth; spacing: 18; visible: wizard.step === 1
            Body { text: "Choose how to add Bloodborne 1.09. The installer creates a new game folder and never replaces an existing one." }
            Row {
                spacing: 12
                GlassButton {
                    text: launcher.setupRunning ? "Installing…" : "Install from ZIP / PKG"
                    width: 220; height: 42; highlighted: true
                    enabled: !launcher.setupRunning && !launcher.running
                    onClicked: launcher.installFromArchive()
                }
                GlassButton {
                    text: "Choose a game folder"; width: 190; height: 42
                    enabled: !launcher.setupRunning
                    onClicked: launcher.browse("game_dir")
                }
            }
            Body { color: Theme.textDim; font.pixelSize: 13; text: "For cusa-03173.zip, choose the ZIP and then where the game should go, such as C:\\Games\\Bloodborne. For an extracted game, choose the folder with eboot.bin directly inside it." }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            Check { level: checks[0].level; label: "Game files"; detail: checks[0].detail }
            GlassButton { text: "Check again"; width: 120; height: 36; onClicked: launcher.refreshReadiness() }
        }

        Column {
            id: step2; width: wizard.contentWidth; spacing: 16; visible: wizard.step === 2
            Body { text: "A writable saves folder is required to play. Trophy keys are optional and add trophy names. Saves stay in the launcher's own user folder unless you choose another." }
            Row {
                spacing: 12
                GlassButton { text: "Import trophy keys"; width: 180; height: 40; onClicked: launcher.importTrophyKeys() }
                GlassButton { text: "Choose a saves folder"; width: 190; height: 40; onClicked: launcher.browse("user_dir") }
            }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            Repeater {
                model: checks.slice(1)
                delegate: Check {
                    level: modelData.level; label: modelData.label; detail: modelData.detail
                    tag: modelData.label === "Trophies" ? "Optional" : "Required"
                }
            }
            GlassButton { text: "Check again"; width: 120; height: 36; onClicked: launcher.refreshReadiness() }
        }

        Column {
            id: step3; width: wizard.contentWidth; spacing: 16; visible: wizard.step === 3
            Body {
                text: gameValid && savesValid ? "Your game files and saves are ready. Choose a graphics preset, then start playing or open the launcher." :
                       "A required check needs attention. Go back to Game files or Your data to fix it."
            }
            Repeater {
                model: checks
                delegate: Check { level: modelData.level; label: modelData.label; detail: modelData.detail }
            }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            // Graphics preset; the suggestion (★, or ★ DLSS 4 / ★ DLSS 5 on an RTX 40 / 50 card with
            // 12 GB: core.preset_tags) comes from the detected card.
            // A Flow: five presets wrap to a second line in a narrow window.
            Flow {
                width: parent.width; spacing: 8
                Text { text: "Graphics"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 14; width: 82; height: 36; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: launcher.graphicsPresets
                    delegate: GlassButton {
                        width: modelData === "remastered" || modelData === "dlss5_ready" ? 176 : 96; height: 36
                        text: launcher.presetLabel(modelData) + (launcher.presetMarks[modelData] || "")
                        highlighted: launcher.graphicsPreset === modelData
                        onClicked: launcher.applyGraphicsPreset(modelData)
                    }
                }
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; lineHeight: 1.3; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12
                text: (launcher.firstStartSummary !== "" ? launcher.firstStartSummary + "  " : "") +
                      launcher.presetDescription(launcher.graphicsPreset) +
                      (launcher.presetSuggestion !== "" ? "  " + launcher.presetSuggestion : "")
            }
            Rectangle { width: parent.width; height: 1; color: Theme.line }
            GlassSwitch {
                text: "Start the game directly next time"
                checked: launcher.launchDirectly
                onToggled: launcher.setValue("launchDirectly", checked)
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12
                text: "Hold Shift while starting to open the launcher instead. In the game, Insert or L3+R3 opens the guide. Setup can be run again from Game & Saves."
            }
        }
    }

    Rectangle { y: parent.height - 70; width: parent.width; height: 1; color: Theme.line }
    Row {
        y: parent.height - 50; spacing: 10
        GlassButton { visible: wizard.step === 0; text: "Start setup"; width: 156; height: 42; highlighted: true; onClicked: wizard.step = 1 }
        GlassButton { visible: wizard.step === 0; text: "Skip for now"; width: 132; height: 42; onClicked: { launcher.skipSetup(); wizard.exitRequested("Home") } }
        GlassButton { visible: wizard.step > 0; text: "Back"; width: 96; height: 42; onClicked: wizard.step-- }
        GlassButton {
            visible: wizard.step === 1 || wizard.step === 2
            text: "Continue"; width: 150; height: 42; highlighted: true
            enabled: wizard.stepValid(wizard.step)
            onClicked: wizard.step++
        }
        GlassButton {
            visible: wizard.step === 3; text: "Play"; serif: true; width: 160; height: 42; highlighted: true
            enabled: gameValid && savesValid && !launcher.running && !launcher.setupRunning
            onClicked: wizard.finish(true)
        }
        GlassButton { visible: wizard.step === 3; text: "Open launcher"; width: 140; height: 42; onClicked: wizard.finish(false) }
    }
    Row {
        anchors.right: parent.right; y: parent.height - 50; height: 42; spacing: 14
        Text {
            visible: wizard.step === 1 && !gameValid; anchors.verticalCenter: parent.verticalCenter
            text: "Add valid game files to continue."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12
        }
        GlassButton { visible: wizard.step === 1 || wizard.step === 2; text: "Skip setup"; width: 116; height: 42; onClicked: wizard.skip() }
    }
}
