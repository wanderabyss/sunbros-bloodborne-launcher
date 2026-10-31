import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Home: the art, a glass hero card (SunBro's Edition, Play, how to play) and a side column of
// quick settings and your hunt (trophies, HD textures, mods).
Item {
    id: home
    objectName: "homeDashboard"
    signal primaryRequested()
    signal settingsRequested()
    signal characterInfoRequested()
    signal workspaceRequested(string category, string section)
    property bool startingGame: false
    property string launchError: ""
    property int settingsTick: 0
    function liveVal(key) { return home.settingsTick >= 0 ? launcher.value(key) : "" }
    // bbport.ini switches come back as "0"/"1" strings; "0" must read as off.
    function isOn(value) { return value === true || value === 1 || value === "1" || value === "true" || value === "on" }
    function quickSettingActive(idKey) {
        if (idKey === "fullscreen") return home.isOn(home.liveVal("fullscreen"))
        if (idKey === "hdr") return home.isOn(home.liveVal("hdr"))
        if (idKey === "fps_mode") return true
        if (idKey === "frame_gen") return String(home.liveVal("frame_gen") || "off") !== "off"
        if (idKey === "ray_tracing") return String(home.liveVal("ray_tracing") || "off") !== "off"
        if (idKey === "show_fps") return String(home.liveVal("show_fps")) === "1"
        return false
    }
    function quickSettingText(idKey) {
        if (idKey === "fullscreen") return home.isOn(home.liveVal("fullscreen")) ? "Fullscreen" : "Windowed"
        if (idKey === "hdr") return home.isOn(home.liveVal("hdr")) ? "HDR10 On" : "SDR (Off)"
        if (idKey === "fps_mode") {
            var fps = String(launcher.effectiveFrameRate || home.liveVal("fps_mode") || "120")
            var overridden = fps !== String(home.liveVal("fps_mode"))
            var base = Number(fps)
            if (!isFinite(base) || base <= 0) return overridden ? "Unlocked (override)" : "Unlocked base FPS"
            var provider = String(home.liveVal("frame_gen") || "off")
            if (overridden) return fps + " base FPS (override)"
            if (provider === "off") return fps + " FPS (no FG)"
            return fps + " base → " + (base * home.frameMultiplier()) + " FPS"
        }
        if (idKey === "frame_gen") {
            var fg = String(home.liveVal("frame_gen") || "off")
            return fg === "dlss" ? "DLSS " + home.frameMultiplier() + "×" : fg === "fsr3" ? "FSR 3.1 (2×)" : "Off"
        }
        if (idKey === "ray_tracing") {
            var rt = String(home.liveVal("ray_tracing") || "off")
            return rt === "off" ? "Off" : rt.charAt(0).toUpperCase() + rt.slice(1)
        }
        if (idKey === "show_fps") return String(home.liveVal("show_fps")) === "1" ? "Shown in-game" : "Hidden"
        return ""
    }
    function frameMultiplier() {
        if (String(home.liveVal("frame_gen")) === "fsr3") return 2
        return Math.max(2, Math.min(4, Number(home.liveVal("frame_gen_multiplier")) || 2))
    }
    function triggerQuickSetting(idKey) {
        if (idKey === "fullscreen") {
            launcher.setValue("fullscreen", !home.isOn(launcher.value("fullscreen")))
        } else if (idKey === "hdr") {
            launcher.setValue("hdr", !home.isOn(launcher.value("hdr")))
        } else if (idKey === "fps_mode") {
            var curFps = String(launcher.value("fps_mode") || "120")
            launcher.setValue("fps_mode", curFps === "60" ? "120" : curFps === "120" ? "uncap" : "60")
        } else if (idKey === "frame_gen") {
            var curFg = String(launcher.value("frame_gen") || "off")
            launcher.setValue("frame_gen", curFg === "off" ? "dlss" : curFg === "dlss" ? "fsr3" : "off")
        } else if (idKey === "ray_tracing") {
            var curRt = String(launcher.value("ray_tracing") || "off")
            var nextRt = curRt === "off" ? "medium" : curRt === "medium" ? "high" : curRt === "high" ? "ultra" : "off"
            launcher.setValue("ray_tracing", nextRt)
        } else if (idKey === "show_fps") {
            launcher.setValue("show_fps", String(launcher.value("show_fps")) === "1" ? "0" : "1")
        }
        home.settingsTick++
    }
    readonly property var profile: launcher.profileData || ({})
    readonly property bool hasHunter: !!profile.valid
    readonly property bool compact: width < 1120
    readonly property bool setupBlocked: launcher.playModeBlocked && !launcher.running && !startingGame && !launcher.coopBusy
    readonly property string statusText: launcher.running ? "Game running" : startingGame ? "Starting game..." : launcher.coopBusy ? "Preparing co-op..." : launchError ? "Launch needs attention" : setupBlocked ? (launcher.playMode === "coop" ? "Co-op setup required" : "Online sign-in required") : "Ready for the hunt"
    readonly property string statusDetail: launcher.running ? "Your game is running. Return here when the hunt is over." : startingGame ? "Preparing Bloodborne with your selected settings." : launcher.coopBusy ? "Please wait while the session is prepared." : launchError ? launchError : setupBlocked ? (launcher.playMode === "coop" ? "Add your co-op account and choose a server in Co-op." : "Sign in to The Hunter's Dream to play online.") : launcher.playMode === "coop" ? "Your co-op settings are ready. Play to join the hunt." : launcher.playMode === "huntersdream" ? "Messages, bloodstains and summons through The Hunter's Dream." : "Your own Yharnam with your current graphics settings."
    readonly property real trophyTotal: Math.max(1, Number(profile.trophies_total || 40))
    readonly property real trophyEarned: Math.max(0, Number(profile.trophies_earned || 0))

    function launch() {
        if (launcher.running || startingGame || launcher.coopBusy) return
        launchError = ""
        if (launcher.playModeBlocked) {
            workspaceRequested(launcher.playMode === "coop" ? "Co-op" : "Online", "")
            return
        }
        startingGame = true
        primaryRequested()
    }

    Connections {
        target: launcher
        function onNoticeChanged() {
            if (home.startingGame && !launcher.running && !launcher.coopBusy) {
                home.launchError = launcher.notice
                home.startingGame = false
            }
        }
        function onGameStarted() { home.startingGame = false; home.launchError = "" }
        function onGameFinished() { home.startingGame = false }
        function onRunningChanged() { if (!launcher.running) home.startingGame = false }
        function onCoopChanged() { if (!launcher.coopBusy && !launcher.running) home.startingGame = false }
        function onChanged() { home.settingsTick++ }
        function onPresetApplied() { home.settingsTick++ }
    }

    component Pill: GlassPanel {
        smoked: true
        radius: height / 2
        height: 40
    }

    // --- Top: SunBro's Edition, then readiness / update -----------------------------------------
    Pill {
        id: badge
        x: 28; y: 22
        width: badgeRow.implicitWidth + 24
        Row {
            id: badgeRow
            x: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Rectangle {
                objectName: "badgeMark"
                width: 30; height: 30; radius: 15; color: "#33000000"; border.color: Theme.line
                NavIcon { anchors.centerIn: parent; width: 20; height: 20; kind: "huntersmark"; stroke: 1.6; strokeColor: Theme.gold }
            }
            Text { text: "SunBro's Edition"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            Text { text: launcher.version; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    // --- Top centre: this PC (launcher.rig, bbport_rig.py) -------------------------------------
    // One line between the badge and the controls on the right; segments drop from the right
    // (display first) when the window is too narrow. Hover or click shows the details.
    Item {
        id: rigPill
        objectName: "rigPill"
        readonly property var rig: launcher.rig
        readonly property bool hdr: home.isOn(home.liveVal("hdr"))
        readonly property var segments: {
            const s = []
            if (rig.gpu) s.push({ icon: "gpu", text: rig.gpu, gold: true })
            if (rig.cpu) s.push({ icon: "cpu", text: rig.cpu })
            if (rig.memoryGb) s.push({ icon: "memory", text: rig.memoryGb + " GB" })
            if (rig.resolution) s.push({ icon: "display", text: rig.resolution + (rig.hz ? " · " + rig.hz + " Hz" : "") + (hdr ? " · HDR" : "") })
            return s
        }
        readonly property real startX: badge.x + badge.width + 16
        readonly property real room: topRight.x - 16 - startX
        // How many segments fit: their widths plus a separator (21) between two, plus padding (28).
        readonly property int shown: {
            let used = 28, n = 0
            for (let i = 0; i < measures.count; i++) {
                const w = measures.itemAt(i) ? measures.itemAt(i).implicitWidth : 0
                if (used + w + (i ? 21 : 0) > room) break
                used += w + (i ? 21 : 0); n++
            }
            return n
        }
        property bool pinned: false
        visible: !!rig.gpu && shown > 0
        x: startX + Math.max(0, (room - width) / 2); y: 22
        width: rigRow.implicitWidth + 28; height: 40
        Repeater { id: measures; model: rigPill.segments
            delegate: Row { visible: false; spacing: 7
                Item { width: 16; height: 16 }
                Text { text: modelData.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold } } }
        Pill { anchors.fill: parent }
        Row {
            id: rigRow
            x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Repeater {
                model: rigPill.segments.slice(0, rigPill.shown)
                delegate: Row {
                    spacing: 10
                    Rectangle { visible: index > 0; width: 1; height: 16; color: Theme.line; anchors.verticalCenter: parent.verticalCenter }
                    Row { spacing: 7; anchors.verticalCenter: parent.verticalCenter
                        NavIcon { width: 16; height: 16; kind: modelData.icon; stroke: 1.5
                            strokeColor: modelData.gold ? Theme.gold : Theme.textFaint; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: modelData.text; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13
                            font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter } }
                }
            }
        }
        HoverHandler { id: rigHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: rigPill.pinned = !rigPill.pinned }
    }
    GlassPanel {
        id: rigCard
        objectName: "rigCard"
        smoked: true; radius: 18; z: 20
        visible: rigPill.visible && (rigHover.hovered || rigPill.pinned)
        width: 340; height: rigDetails.implicitHeight + 24
        x: Math.min(Math.max(16, rigPill.x + (rigPill.width - width) / 2), home.width - width - 16)
        y: rigPill.y + rigPill.height + 8
        Column {
            id: rigDetails
            x: 18; y: 12; width: parent.width - 36
            Repeater {
                model: {
                    const r = rigPill.rig, rows = []
                    if (r.gpuFull) rows.push(["Graphics card", r.gpu + (r.vramGb ? " · " + r.vramGb + " GB" : "")])
                    if (r.driver) rows.push(["Driver", r.driver])
                    if (r.gpuFull) rows.push(["DLSS 5", launcher.dlss5Offered ? "Ready on this card" : "Not offered on this card"])
                    if (r.cpuFull) rows.push(["Processor", r.cpuFull + (r.cores ? " · " + r.cores + "C / " + r.threads + "T" : "")])
                    if (r.memoryGb) rows.push(["Memory", r.memoryGb + " GB"])
                    if (r.width) rows.push(["Display", r.width + " × " + r.height + (r.hz ? " · " + r.hz + " Hz" : "") + (rigPill.hdr ? " · HDR" : "")])
                    return rows
                }
                delegate: Item {
                    width: rigDetails.width; height: 30
                    Rectangle { visible: index > 0; width: parent.width; height: 1; color: Theme.line }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: modelData[0]; color: Theme.textFaint
                        font.family: Theme.sans; font.pixelSize: 12 }
                    Text { anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right; text: modelData[1]
                        color: modelData[0] === "DLSS 5" && launcher.dlss5Offered ? Theme.gold : Theme.text
                        font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold }
                }
            }
        }
    }
    Row {
        id: topRight
        anchors.right: parent.right; anchors.rightMargin: 28; y: 22; spacing: 10
        TextSizeControl {}
        Pill {
            objectName: "updateNotificationBanner"
            visible: launcher.hasUpdate
            width: updateRow.implicitWidth + 28
            Row {
                id: updateRow
                x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter
                    color: launcher.updateReady ? Theme.good : launcher.updateBusy ? Theme.info : Theme.gold }
                Text {
                    objectName: "updateBannerText"
                    anchors.verticalCenter: parent.verticalCenter
                    text: launcher.updateReady ? ("Update " + launcher.updateVersion + " is ready to install") :
                          launcher.updateBusy ? (launcher.updateStatus.length > 0 ? launcher.updateStatus : ("Downloading " + launcher.updateVersion + "…")) :
                          ("New release available: " + launcher.updateVersion)
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold
                }
                GlassButton {
                    objectName: "updateBannerAction"
                    visible: !launcher.updateBusy
                    enabled: launcher.updateReady ? !launcher.running : true
                    highlighted: launcher.updateReady
                    height: 28; width: launcher.updateReady ? 104 : 92
                    font.pixelSize: 12
                    text: launcher.updateReady ? "Install now" : "Download"
                    onClicked: {
                        if (launcher.updateReady) launcher.installUpdate()
                        else launcher.downloadUpdate()
                    }
                }
                GlassButton {
                    objectName: "updateBannerDetails"
                    height: 28; width: 100; font.pixelSize: 12
                    text: "What's new"
                    onClicked: Theme.showReleaseNotes("update")
                }
            }
        }
        Pill {
            objectName: "readinessPill"
            visible: !launcher.hasUpdate
            width: readyRow.implicitWidth + 28
            Row {
                id: readyRow
                x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter
                    color: home.launchError ? Theme.error : home.setupBlocked || !launcher.savesWritable ? Theme.warn : Theme.good }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: home.launchError ? "Needs attention" : !launcher.savesWritable ? "Check setup" : home.setupBlocked ? "Setup needed" : launcher.running ? "Game running" : "Ready to play"
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold
                }
            }
        }
    }

    // --- Layout: the hero and a side column (quick settings, your hunt) -------------------------
    // Laid out at the design size; Main.qml magnifies it for large and 4K windows. A compact
    // window stacks the side column under the hero and scrolls; Play stays at the top.
    readonly property real margin: compact ? 28 : 48
    readonly property real heroWidth: compact ? Math.min(720, width - 2 * margin) : 600
    readonly property real columnGap: 40
    readonly property real sideWidth: compact ? heroWidth : Math.min(460, width - 2 * margin - 600 - columnGap)
    readonly property real groupWidth: compact ? heroWidth : heroWidth + columnGap + sideWidth

    Flickable {
        id: scroller
        objectName: "homeScroller"
        anchors.fill: parent; anchors.topMargin: 76
        contentWidth: width
        contentHeight: Math.max(height, content.y + content.height + 16)
        interactive: contentHeight > height
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: GlassScrollBar {}

        Item {
            id: content
            x: Math.max(home.margin, (scroller.width - home.groupWidth) / 2) // centred, stacked or side by side
            y: Math.max(4, (scroller.height - height) / 2 - 24)
            width: home.groupWidth
            height: home.compact ? side.y + side.height : Math.max(hero.height, side.height)

            GlassPanel {
                id: hero
                objectName: "homeHero"
                width: home.heroWidth
                // Side by side, the hero matches the side column's height and centres its content.
                height: home.compact ? heroColumn.implicitHeight + 64 : Math.max(heroColumn.implicitHeight + 64, side.height)
                radius: 32
                ColumnLayout {
                    id: heroColumn
                    x: 36; y: Math.max(32, (parent.height - implicitHeight) / 2); width: parent.width - 72; spacing: 0
                    Row {
                        spacing: 8
                        NavIcon { kind: "sun"; width: 16; height: 16; stroke: 2; strokeColor: Theme.gold; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "SUNBRO'S EDITION"; color: Theme.gold; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; font.letterSpacing: 3 }
                    }
                    Text {
                        Layout.topMargin: 6
                        text: "Bloodborne"; color: Theme.text
                        font.family: Theme.serif; font.pixelSize: home.compact ? 60 : 72
                    }
                    RowLayout {
                        Layout.topMargin: 10; Layout.fillWidth: true; spacing: 2
                        // The mark's ink is the middle of its square: pulled left so the stem lines up with the title.
                        NavIcon {
                            objectName: "heroMark"
                            Layout.preferredWidth: 44; Layout.preferredHeight: 44; Layout.leftMargin: -14; Layout.alignment: Qt.AlignVCenter
                            width: 44; height: 44; kind: "huntersmark"; stroke: 2; strokeColor: Theme.gold
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 4
                            RowLayout {
                                Layout.fillWidth: true; spacing: 0
                                Text { text: home.hasHunter ? "Welcome back, " : ""; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 17 }
                                Text {
                                    objectName: "hunterName"
                                    text: home.hasHunter ? (home.profile.name || "Hunter") : "A new hunt awaits"
                                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 17; font.weight: Font.DemiBold
                                    Layout.fillWidth: true; elide: Text.ElideRight
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: home.hasHunter ? ("Level " + (home.profile.level || "–") + "  ·  " + (home.profile.play_time || "playtime unknown") + "  ·  " + home.trophyEarned + " of " + home.trophyTotal + " trophies")
                                                     : "Create your character in game to begin."
                                color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 13; elide: Text.ElideRight
                            }
                        }
                    }

                    RowLayout {
                        Layout.topMargin: 26; Layout.fillWidth: true; spacing: 12
                        Button {
                            id: launchButton
                            objectName: "launchHunt"
                            Layout.preferredHeight: 54
                            Layout.preferredWidth: Math.max(150, playText.implicitWidth + 70)
                            text: launcher.running ? "Game running" : home.startingGame ? "Starting…" : launcher.playModeBlocked ? (launcher.playMode === "coop" ? "Set up co-op" : "Sign in to play") : launcher.playMode === "coop" ? "Play co-op" : launcher.playMode === "huntersdream" ? "Play online" : "Play"
                            enabled: !launcher.running && !home.startingGame && !launcher.coopBusy
                            hoverEnabled: true
                            onClicked: home.launch()
                            contentItem: Item {
                                Row {
                                    anchors.centerIn: parent; spacing: 10
                                    NavIcon { visible: !launcher.playModeBlocked; kind: "play"; width: 16; height: 16; stroke: 2.4; strokeColor: Theme.primaryText; anchors.verticalCenter: parent.verticalCenter }
                                    Text { id: playText; text: launchButton.text; color: launchButton.enabled ? Theme.primaryText : "#8c000000"; font.family: Theme.sans; font.pixelSize: 18; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                                }
                            }
                            background: Rectangle {
                                radius: height / 2
                                color: !launchButton.enabled ? "#b3ffffff" : launchButton.down ? "#e3e3e3" : launchButton.hovered ? "#f4f4f4" : "#ffffff"
                                border.color: launchButton.visualFocus ? Theme.gold : "transparent"; border.width: 2
                            }
                            scale: Theme.reducedMotion ? 1 : launchButton.down ? 0.97 : 1
                            Behavior on scale { NumberAnimation { duration: 80 } }
                        }
                        GlassPanel {
                            Layout.preferredHeight: 54
                            Layout.preferredWidth: modeRow.implicitWidth + 10
                            radius: 27
                            Row {
                                id: modeRow
                                x: 5; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                                Repeater {
                                    model: [{key: "offline", title: "Solo"}, {key: "huntersdream", title: "Online"}, {key: "coop", title: "Co-op"}]
                                    delegate: Button {
                                        id: modeButton
                                        required property var modelData
                                        objectName: "mode_" + modelData.key
                                        readonly property bool selected: launcher.playMode === modelData.key
                                        width: modeText.implicitWidth + 40; height: 44
                                        enabled: !launcher.running && !home.startingGame && !launcher.coopBusy
                                        hoverEnabled: true
                                        onClicked: { home.launchError = ""; launcher.setPlayMode(modelData.key) }
                                        Accessible.name: modelData.title + (selected ? ", selected" : "")
                                        contentItem: Text { id: modeText; text: modeButton.modelData.title; color: modeButton.selected || modeButton.hovered ? Theme.text : Theme.textDim; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                        background: Rectangle { radius: height / 2; color: modeButton.selected ? "#42ffffff" : "transparent"; border.color: modeButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2 }
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.topMargin: 16; Layout.fillWidth: true; spacing: 10
                        Rectangle {
                            width: 8; height: 8; radius: 4; Layout.alignment: Qt.AlignTop; Layout.topMargin: 6
                            color: home.launchError ? Theme.error : home.setupBlocked ? Theme.warn : launcher.running ? Theme.info : Theme.good
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 2
                            Text { objectName: "launchStatus"; text: home.statusText; color: home.launchError ? Theme.error : home.setupBlocked ? Theme.warn : Theme.text; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold }
                            Text { objectName: "launchGuidance"; text: home.statusDetail; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        }
                    }
                    Text {
                        objectName: "launcherNotice"
                        Layout.topMargin: 6; Layout.fillWidth: true
                        visible: text !== ""
                        text: launcher.notice === "Ready to hunt." ? "" : launcher.notice
                        color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }
            }
            Column {
                id: side
                x: home.compact ? 0 : hero.width + home.columnGap
                y: home.compact ? hero.height + 16 : 0
                width: home.sideWidth
                spacing: 16

                // Quick settings: the main graphics switches; a tap steps a tile to its next value.
                GlassPanel {
                    id: quickCard
                    objectName: "homeQuickSettingsCard"
                    smoked: true
                    width: parent.width
                    height: quickGrid.y + quickGrid.height + 14
                    radius: 28
                    Item {
                        id: quickHead
                        x: 22; y: 18; width: parent.width - 44; height: 24
                        Text { text: "Quick settings"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 16; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            objectName: "homeAllVisuals"
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            text: "All visuals  ›"; color: visualsHit.containsMouse ? Theme.gold : Theme.text
                            font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold
                            MouseArea { id: visualsHit; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: home.workspaceRequested("Visuals", "") }
                        }
                    }
                    Grid {
                        id: quickGrid
                        x: 14; y: quickHead.y + quickHead.height + 14
                        width: parent.width - 28
                        columns: home.compact && width >= 520 ? 3 : 2
                        spacing: 8
                        Repeater {
                            model: [
                                {idKey: "fps_mode", icon: "fps", title: "Frame rate"},
                                {idKey: "frame_gen", icon: "framegen", title: "Frame generation"},
                                {idKey: "ray_tracing", icon: "star", title: "Ray tracing"},
                                {idKey: "hdr", icon: "hdr", title: "HDR"},
                                {idKey: "fullscreen", icon: "visuals", title: "Display"},
                                {idKey: "show_fps", icon: "sliders", title: "FPS counter"}
                            ]
                            delegate: Rectangle {
                                id: quickTile
                                required property var modelData
                                readonly property bool activeState: home.quickSettingActive(modelData.idKey)
                                readonly property string currentText: home.quickSettingText(modelData.idKey)
                                objectName: "quickToggle_" + modelData.idKey
                                width: (quickGrid.width - (quickGrid.columns - 1) * quickGrid.spacing) / quickGrid.columns
                                height: 66; radius: height / 2
                                color: quickHit.pressed ? Theme.surfaceActive : quickHit.containsMouse ? Theme.surfaceHover : Theme.well
                                border.color: activeState ? Theme.lineStrong : "transparent"
                                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                                scale: quickHit.pressed && !Theme.reducedMotion ? 0.97 : 1
                                Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.title + ": " + currentText
                                ToolTip.visible: quickHit.containsMouse && modelData.idKey === "fps_mode"
                                ToolTip.delay: 400
                                ToolTip.text: "Base is the game's rendered FPS. Output includes generated frames. These are configured targets, not measured FPS."
                                Rectangle {
                                    x: 16; anchors.verticalCenter: parent.verticalCenter
                                    width: 36; height: 36; radius: height / 2
                                    color: quickTile.activeState ? "#2effffff" : "#14ffffff"
                                    NavIcon { anchors.centerIn: parent; kind: quickTile.modelData.icon; width: 17; height: 17; stroke: 1.9; strokeColor: quickTile.activeState ? Theme.text : Theme.textFaint }
                                }
                                Column {
                                    x: 62; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x - 20; spacing: 2
                                    Text { width: parent.width; text: quickTile.modelData.title; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12; elide: Text.ElideRight }
                                    Text {
                                        width: parent.width; text: quickTile.currentText
                                        color: quickTile.activeState ? Theme.text : Theme.textDim
                                        font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight
                                    }
                                }
                                MouseArea {
                                    id: quickHit
                                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: home.triggerQuickSetting(quickTile.modelData.idKey)
                                }
                            }
                        }
                    }
                }

                // Your hunt: trophy progress, the HD texture pack and mods, each opening its page.
                GlassPanel {
                    id: huntCard
                    objectName: "homeHuntCard"
                    smoked: true
                    width: parent.width
                    height: huntColumn.implicitHeight + 28
                    radius: 28
                    readonly property int modsOn: launcher.contentMods.filter(m => m.enabled).length
                    Column {
                        id: huntColumn
                        x: 14; y: 14; width: parent.width - 28; spacing: 8
                        Rectangle {
                            objectName: "openDossier"
                            width: parent.width; height: 62; radius: height / 2
                            color: dossierHit.containsMouse ? Theme.surfaceHover : "transparent"
                            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                            NavIcon { x: 20; y: 12; kind: "trophy"; width: 18; height: 18; stroke: 1.9; strokeColor: Theme.gold }
                            Text { x: 48; y: 11; text: "Trophies"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold }
                            Text {
                                anchors.right: parent.right; anchors.rightMargin: 22; y: 12
                                text: home.trophyEarned + " / " + home.trophyTotal + "   ›"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13
                            }
                            Rectangle {
                                x: 20; y: 42; width: parent.width - 40; height: 6; radius: 3; color: "#24ffffff"
                                Rectangle {
                                    width: Math.max(height, parent.width * Math.min(1, home.trophyEarned / home.trophyTotal)); height: parent.height; radius: 3
                                    color: Theme.gold
                                    Behavior on width { NumberAnimation { duration: Theme.motionPage; easing.type: Easing.OutCubic } }
                                }
                            }
                            MouseArea { id: dossierHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: home.characterInfoRequested() }
                        }
                        Row {
                            width: parent.width; spacing: 8
                            Rectangle {
                                objectName: "hdPackBadge"
                                visible: launcher.hdPackState !== "missing"
                                width: (parent.width - 8) / 2; height: 46; radius: height / 2
                                color: hdHit.containsMouse ? Theme.surfaceHover : Theme.well
                                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                                Row {
                                    x: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 9
                                    Rectangle { width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter
                                        color: launcher.hdPackState === "on" ? Theme.good : launcher.hdPackState === "busy" ? Theme.accent : Theme.textFaint }
                                    Text {
                                        objectName: "hdPackBadgeText"
                                        text: launcher.hdPackState === "busy" ? "HD textures " + Math.round(launcher.hdPackProgress * 100) + "%" :
                                              launcher.hdPackState === "on" ? "HD textures" : "HD textures off"
                                        color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea { id: hdHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: home.workspaceRequested("Visuals", "High-resolution textures") }
                            }
                            Rectangle {
                                objectName: "homeModsTile"
                                width: launcher.hdPackState !== "missing" ? (parent.width - 8) / 2 : parent.width; height: 46; radius: height / 2
                                color: modsHit.containsMouse ? Theme.surfaceHover : Theme.well
                                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                                Row {
                                    x: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 9
                                    NavIcon { kind: "wrench"; width: 15; height: 15; stroke: 1.9; strokeColor: huntCard.modsOn > 0 ? Theme.text : Theme.textFaint; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: huntCard.modsOn > 0 ? huntCard.modsOn + (huntCard.modsOn === 1 ? " mod on" : " mods on") : "No mods on"
                                        color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                MouseArea { id: modsHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: home.workspaceRequested("Mods & Patches", "") }
                            }
                        }
                    }
                }
            }
        }
    }
}
