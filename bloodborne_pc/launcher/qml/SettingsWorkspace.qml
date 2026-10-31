import QtQuick
import QtQuick.Controls

// Settings for one or more categories: a glass sidebar of their sections (and search), the chosen
// section's settings in a glass list, then the actions that section calls for. Changes save as
// they are made.
Item {
    id: workspace
    objectName: "settingsWorkspace"
    signal backToLauncher()
    signal backRequested()
    signal openSetup(int step)
    // The categories in the sidebar, each with its sections (Settings shows three).
    property var categories: ["Visuals"]
    // When set, the sidebar starts with "‹ backLabel" (Advanced visuals, Workshop details).
    property string backLabel: ""
    property string category: categories.length > 0 ? categories[0] : "Visuals"
    property string section: ""
    property string targetKey: ""
    property string query: ""
    // Save backups: the one row asking to confirm, "restore:<name>" or "delete:<name>" (empty: none).
    property string backupConfirm: ""

    // Neural rendering (DLSS 5): the rows marked advanced stay folded until "More NR options".
    property bool nrAdvancedOpen: false
    function visibleSectionFields(cat, sec) {
        var rows = launcher.sectionFields(cat, sec)
        if (!workspace.nrAdvancedOpen) rows = rows.filter(row => !row.advanced)
        return rows
    }
    function visibleSections(cat) { return launcher.categorySections(cat) }
    // Sidebar icon and colour for a section (macOS System Settings style).
    function sectionIcon(sec) {
        var s = sec.toLowerCase()
        if (s === "hdr") return "hdr"
        if (s.indexOf("display") >= 0) return "visuals"
        if (s === "frame rate") return "fps"
        if (s === "resolution") return "upscale"
        if (s === "window") return "visuals"
        if (s === "sharpening") return "sparkle"
        if (s === "detail") return "texture"
        if (s === "post-processing") return "layers"
        if (s === "cheats") return "bolt"
        if (s === "gameplay tweaks") return "controls"
        if (s.indexOf("upscal") >= 0) return "upscale"
        if (s.indexOf("neural") >= 0) return "neural"
        if (s.indexOf("frame gen") >= 0) return "framegen"
        if (s.indexOf("ray") >= 0) return "star"
        if (s.indexOf("effect") >= 0) return "sparkle"
        if (s.indexOf("texture") >= 0) return "texture"
        if (s.indexOf("memory") >= 0) return "layers"
        if (s.indexOf("overlay") >= 0) return "fps"
        if (s.indexOf("prompt") >= 0 || s.indexOf("mouse") >= 0 || s.indexOf("keyboard") >= 0 || s.indexOf("control") >= 0) return "controls"
        if (s.indexOf("backup") >= 0) return "saves"
        if (s.indexOf("data") >= 0 || s.indexOf("game files") >= 0) return "folder"
        if (s.indexOf("language") >= 0) return "language"
        if (s.indexOf("launch") >= 0 || s.indexOf("startup") >= 0) return "power"
        if (s.indexOf("update") >= 0) return "update"
        if (s.indexOf("log") >= 0) return "log"
        if (s.indexOf("mods") >= 0) return "puzzle"
        if (s.indexOf("enhance") >= 0) return "star"
        if (s.indexOf("atlas") >= 0 || s.indexOf("map") >= 0) return "map"
        if (s.indexOf("external") >= 0) return "patch"
        if (s.indexOf("gameplay") >= 0) return "controls"
        return "settings"
    }
    readonly property var sectionColors: ["#0a84ff", "#30a46c", "#ff9f0a", "#ff375f", "#5e5ce6", "#bf5af2", "#64d2ff", "#ac8e68", "#ff6b62", "#8e8e93"]

    Component.onCompleted: {
        var secs = visibleSections(category)
        if (!section || section === "" || secs.indexOf(section) === -1) {
            section = secs.length > 0 ? secs[0] : ""
        }
    }
    onVisibleChanged: {
        if (visible) {
            var secs = visibleSections(category)
            if (!section || section === "" || secs.indexOf(section) === -1) {
                section = secs.length > 0 ? secs[0] : ""
            }
        }
    }

    function openAt(nextCategory, nextSection, nextKey) {
        category = nextCategory || category || "Visuals"
        var secs = visibleSections(category)
        section = (nextSection && secs.indexOf(nextSection) !== -1) ? nextSection : (secs[0] || "")
        targetKey = nextKey || ""
        search.text = ""
        detailScroll.contentY = 0
        if (targetKey !== "") Qt.callLater(focusTarget)
    }
    function focusTarget() {
        // Guided controls own these settings instead of the generic repeater.
        if (is("Co-op", "Seamless co-op")) {
            var editor = coopSetup.revealSetting(targetKey)
            if (editor) {
                detailScroll.contentY = 0
                Qt.callLater(() => editor.forceActiveFocus(Qt.OtherFocusReason))
                return
            }
        }
        for (var i = 0; i < fieldRepeater.count; i++) {
            var row = fieldRepeater.itemAt(i)
            if (row && row.settingKey === targetKey) {
                detailScroll.contentY = Math.max(0, row.y - 20)
                break
            }
        }
    }
    function is(cat, sec) { return workspace.category === cat && workspace.section === sec }

    // --- Sidebar: back, search, the categories' sections -----------------------------------------
    GlassPanel {
        id: sidebar
        objectName: "settingsSidebar"
        x: 16; y: 16; width: workspace.width < 1200 ? 260 : 290; height: parent.height - 16
        radius: 26
        Flickable {
            anchors.fill: parent; anchors.margins: 12
            clip: true; boundsBehavior: Flickable.StopAtBounds
            contentHeight: sideColumn.implicitHeight
            Column {
                id: sideColumn
                width: parent.width; spacing: 0
                Button {
                    objectName: "settingsBack"
                    visible: workspace.backLabel !== ""
                    height: visible ? 34 : 0; width: backRow.implicitWidth + 16
                    hoverEnabled: true
                    onClicked: workspace.backRequested()
                    contentItem: Item { Row { id: backRow; x: 4; anchors.verticalCenter: parent.verticalCenter; spacing: 4
                        NavIcon { kind: "back"; width: 15; height: 15; stroke: 2.2; strokeColor: Theme.link; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: workspace.backLabel; color: Theme.link; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                    } }
                    background: Rectangle { radius: 8; color: parent.hovered ? "#14ffffff" : "transparent" }
                }
                Item { width: 1; height: workspace.backLabel !== "" ? 10 : 4 }
                GlassTextField {
                    id: search; objectName: "settingsSearch"
                    width: parent.width; height: 36; leftPadding: 38
                    placeholderText: "Search"
                    onTextChanged: workspace.query = text
                    NavIcon { x: 13; anchors.verticalCenter: parent.verticalCenter; width: 15; height: 15; kind: "search"; stroke: 2; strokeColor: Theme.textFaint }
                }
                Repeater {
                    model: workspace.categories
                    delegate: Column {
                        id: group
                        required property string modelData
                        required property int index
                        width: sideColumn.width
                        topPadding: 14
                        Text {
                            visible: workspace.categories.length > 1
                            leftPadding: 10; bottomPadding: 6
                            text: group.modelData; color: Theme.textFaint
                            font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
                        }
                        Repeater {
                            model: workspace.visibleSections(group.modelData)
                            delegate: Button {
                                id: sectionButton
                                required property string modelData
                                required property int index
                                readonly property bool active: workspace.query === "" && workspace.category === group.modelData && workspace.section === modelData
                                objectName: "section_" + modelData.replace(/[^a-zA-Z0-9]/g, "_")
                                width: group.width; height: 40
                                hoverEnabled: true
                                onClicked: { search.text = ""; workspace.openAt(group.modelData, modelData, "") }
                                Accessible.name: modelData + (active ? ", selected" : "")
                                contentItem: Item { Row {
                                    x: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                                    Rectangle {
                                        width: 30; height: 30; radius: 9; anchors.verticalCenter: parent.verticalCenter
                                        color: workspace.sectionColors[(group.index * 4 + sectionButton.index) % workspace.sectionColors.length]
                                        NavIcon { anchors.centerIn: parent; width: 18; height: 18; stroke: 1.9; strokeColor: "#ffffff"; kind: workspace.sectionIcon(sectionButton.modelData) }
                                    }
                                    Text {
                                        width: group.width - 58; elide: Text.ElideRight
                                        text: sectionButton.modelData; color: Theme.text
                                        font.family: Theme.sans; font.pixelSize: 14; font.weight: sectionButton.active ? Font.DemiBold : Font.Normal
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                } }
                                background: Rectangle {
                                    radius: height / 2
                                    color: sectionButton.active ? "#38ffffff" : sectionButton.hovered ? "#14ffffff" : "transparent"
                                    border.color: sectionButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2
                                }
                            }
                        }
                    }
                }
                Text {
                    width: parent.width; topPadding: 16; leftPadding: 10; rightPadding: 10
                    text: "Changes save as you make them. Some apply the next time the game starts."
                    color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12; wrapMode: Text.WordWrap
                }
            }
        }
    }

    // --- The chosen section ----------------------------------------------------------------------
    Item {
        id: content
        readonly property real columnWidth: Math.min(700, parent.width - sidebar.x - sidebar.width - 80)
        x: sidebar.x + sidebar.width + (parent.width - sidebar.x - sidebar.width - columnWidth) / 2
        y: 0; width: columnWidth; height: parent.height

        // Search results replace the section while there is a query.
        Column {
            id: results
            objectName: "preferenceSearchResults"
            // Only this page's categories: Visuals, Online, Co-op and the Workshop have their own pages.
            property var hits: workspace.query !== "" ? launcher.searchSettings(workspace.query).filter(hit => workspace.categories.indexOf(hit.category) !== -1) : []
            visible: workspace.query !== ""
            y: 36; width: parent.width; spacing: 8
            Text { text: "Results"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 28; font.weight: Font.Bold }
            Text {
                visible: results.hits.length === 0; text: "Nothing here matches “" + workspace.query + "”."
                color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14
            }
            Item { width: 1; height: 6 }
            Repeater {
                model: results.hits
                delegate: MenuRow {
                    width: content.width; label: modelData.label; value: modelData.category + "  ›  " + modelData.section
                    onClicked: { var hit = modelData; search.text = ""; workspace.openAt(hit.category, hit.section, hit.key) }
                }
            }
        }

        Column {
            id: header
            visible: workspace.query === ""
            y: 36; width: parent.width; spacing: 4
            Text { width: parent.width; text: workspace.section; color: Theme.text; font.family: Theme.sans; font.pixelSize: 28; font.weight: Font.Bold; elide: Text.ElideRight }
            Text { text: workspace.category; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 14 }
        }

        Flickable {
            id: detailScroll
            visible: workspace.query === ""
            y: header.y + header.height + 18; width: parent.width + 14; height: parent.height - y
            clip: true; boundsBehavior: Flickable.StopAtBounds
            contentHeight: detailColumn.implicitHeight + 28
            ScrollBar.vertical: GlassScrollBar {}
            Column {
                id: detailColumn
                width: detailScroll.width - 14; spacing: 0

                GlassPanel {
                    objectName: "fieldList"
                    visible: fieldRepeater.count > 0
                    width: parent.width; height: fieldCol.implicitHeight
                    radius: 22
                    Column {
                        id: fieldCol
                        width: parent.width
                        Repeater {
                            id: fieldRepeater
                            // settingsRevision: rebuilt after a preset rewrites several rows.
                            model: launcher.settingsRevision < 0 ? [] : workspace.visibleSectionFields(workspace.category, workspace.section)
                            delegate: FieldRow { width: fieldCol.width; field: modelData }
                        }
                    }
                }

                // Actions beside the task that calls for them, in their own glass card.
                Item { width: parent.width; height: fieldRepeater.count > 0 && sectionActionsCol.implicitHeight > 1 ? 16 : 0 }
                GlassPanel {
                    objectName: "sectionActions"
                    opacity: sectionActionsCol.implicitHeight > 1 ? 1 : 0
                    width: parent.width; height: sectionActionsCol.implicitHeight > 1 ? sectionActionsCol.implicitHeight + 44 : 0
                    radius: 22
                Column {
                    id: sectionActionsCol
                    x: 22; y: 22; width: parent.width - 44; spacing: 16
                    Row { visible: is("Controls", "Button prompts"); spacing: 10
                        Repeater {
                            model: ["PlayStation", "Xbox", "Keyboard"]
                            delegate: GlassButton { text: modelData; width: 124; height: 38; highlighted: launcher.promptChoice === modelData; onClicked: launcher.setPrompt(modelData) }
                        }
                    }
                    Note { visible: is("Controls", "Button prompts"); text: "Which buttons the game shows, from the next start. Xbox (by Dommo) and Keyboard (PCBButtons by JinkiJinn) are mods from Nexus Mods, not part of the launcher: the first time you choose one, its Nexus page opens and you pick the file you downloaded (.zip, .7z or .rar). Keyboard also binds the keys its images show: E interact, Left Shift dodge, R blood vial, Q item, F transform, mouse buttons to attack." }
                    Row { visible: is("Mods & Patches", "Hunter's Atlas (map)"); spacing: 12
                        GlassButton { text: "Prepare maps"; width: 160; height: 38; onClicked: launcher.prepareAtlas() }
                        Note { text: launcher.atlasStatus; anchors.verticalCenter: parent.verticalCenter; width: 420 }
                    }
                    Note { visible: is("Mods & Patches", "Hunter's Atlas (map)"); text: "Hunter's Atlas: Full-screen map (your position, floors, lamps, NPCs). Auto-prepares on first game start (5-15 min). In-game: quick menu → Map, or click it." }
                    // HD Texture Pack: downloaded from Nexus Mods and built on this PC (the release
                    // never carries it).
                    Row { visible: is("Visuals", "High-resolution textures"); spacing: 10
                        Rectangle { width: 12; height: 12; radius: 6; anchors.verticalCenter: parent.verticalCenter
                            color: launcher.hdPackState === "on" ? Theme.good : launcher.hdPackState === "missing" ? Theme.warn :
                                   launcher.hdPackState === "busy" ? Theme.accent : Theme.textFaint }
                        Text { color: Theme.text; font.family: Theme.sans; font.pixelSize: 17; font.weight: Font.DemiBold
                            text: launcher.hdPackState === "busy" ? "Installing… " + Math.round(launcher.hdPackProgress * 100) + "%" :
                                  launcher.hdPackState === "on" ? "Installed and on" :
                                  launcher.hdPackState === "off" ? "Installed, switched off" : "Not installed" }
                    }
                    Note { visible: is("Visuals", "High-resolution textures"); text: "Sharper world, sky and moon, and effects: BB Reborne (Serotoniner), Upscaled Skybox and Clouds (johnnycoax) and SFX Texture Overhaul (WorldDstroyer) from Nexus Mods. Download their 6 files below (about 20 GB, a free Nexus Mods account is enough), then Build the HD Texture Pack merges them into one pack. 4x Upscaled Armors is left out: with it, travel between areas stalled. Picture files only: maps, enemies, items, events and co-op are unchanged. Needs about 45 GB free on the game's drive while it installs, 20 GB after, and a card with 10 GB of video memory or more." }
                    ToggleRow {
                        visible: is("Visuals", "High-resolution textures")
                        label: "High-resolution textures"
                        hint: launcher.hdPackInstalled ? "Applies the next time the game starts." : "Not installed yet."
                        checked: launcher.hdPackEnabled
                        enabled: launcher.hdPackInstalled && !launcher.hdPackBusy
                        opacity: enabled ? 1 : 0.5
                        onToggled: (on) => launcher.setHdPack(on)
                    }
                    Column { visible: is("Visuals", "High-resolution textures"); width: parent.width; spacing: 8
                        Rectangle {
                            visible: launcher.hdPackBusy
                            width: parent.width; height: 10; radius: 5; color: "#1a1e23"; border.color: Theme.line
                            Rectangle { width: Math.max(10, parent.width * launcher.hdPackProgress); height: parent.height; radius: 5; color: Theme.accent
                                Behavior on width { NumberAnimation { duration: 300 } } }
                        }
                        Note { text: launcher.hdPackStatus; color: Theme.text; font.pixelSize: 13; width: parent.width }
                    }
                    // The pack's Nexus files: each opens on Nexus, where the player presses Manual
                    // Download; the launcher moves the finished zip from Downloads into its folder.
                    Column { visible: is("Visuals", "High-resolution textures") && !launcher.hdPackInstalled; width: parent.width; spacing: 8
                        Repeater {
                            model: launcher.hdPackFiles
                            delegate: Row {
                                spacing: 10
                                Rectangle { width: 10; height: 10; radius: 5; anchors.verticalCenter: parent.verticalCenter
                                    color: modelData.found ? Theme.good : Theme.warn }
                                Column { width: sectionActionsCol.width - 230; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                                    Text { width: parent.width; text: modelData.title + "  ·  " + modelData.size; color: Theme.text
                                        font.family: Theme.sans; font.pixelSize: 14; elide: Text.ElideRight }
                                    Text { width: parent.width; text: (modelData.found ? "Downloaded: " : "File: ") + modelData.file + (modelData.author ? "  ·  by " + modelData.author : "")
                                        color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12; elide: Text.ElideRight }
                                }
                                GlassButton { width: 190; height: 34; text: modelData.found ? "Downloaded" : "Open on Nexus"
                                    highlighted: !modelData.found; enabled: !modelData.found
                                    onClicked: launcher.hdPackOpenFile(modelData.id) }
                            }
                        }
                    }
                    Row { visible: is("Visuals", "High-resolution textures"); spacing: 10
                        GlassButton { highlighted: launcher.hdPackReady && !launcher.hdPackInstalled; text: launcher.hdPackBusy ? "Building…" : (launcher.hdPackInstalled ? "Rebuild" : "Build the HD Texture Pack"); width: 230; height: 38; enabled: !launcher.hdPackBusy && launcher.hdPackReady; onClicked: launcher.hdPackInstall() }
                        GlassButton { visible: launcher.hdPackBusy; text: "Cancel"; width: 110; height: 38; onClicked: launcher.hdPackCancel() }
                        GlassButton { text: "Open downloads folder"; width: 190; height: 38; onClicked: launcher.openFolder("hd_pack_downloads") }
                    }
                    // DLSS 5 (community route): the player's own nvngx_dlssnr.dll, never fetched by us.
                    Row { visible: is("Visuals", "Neural rendering (DLSS 5)"); spacing: 10
                        Rectangle { objectName: "neuralRuntimeDot"; width: 12; height: 12; radius: 6; anchors.verticalCenter: parent.verticalCenter
                            color: launcher.neuralRuntimeInstalled ? Theme.good : Theme.warn }
                        Text { objectName: "neuralRuntimeStatus"; width: sectionActionsCol.width - 30; wrapMode: Text.WordWrap
                            text: launcher.neuralRuntimeStatus; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13 }
                    }
                    Row { visible: is("Visuals", "Neural rendering (DLSS 5)"); spacing: 10
                        GlassButton { objectName: "nrAdvancedToggle"; width: 190; height: 38
                            text: workspace.nrAdvancedOpen ? "Fewer NR options" : "More NR options"
                            onClicked: workspace.nrAdvancedOpen = !workspace.nrAdvancedOpen }
                        GlassButton { objectName: "nrReset"; text: "Reset to add-on defaults"; width: 210; height: 38
                            onClicked: launcher.resetNeuralRendering() }
                    }
                    Note { visible: is("Visuals", "Neural rendering (DLSS 5)"); text: "Add-on default writes nothing for that row, so renodx-dlss5 uses its own value. NR passes, input height and white point are not settings of the add-on this port uses, so they are not here." }
                    Note { objectName: "upscalingDlss5Note"; visible: is("Visuals", "Upscaling"); text: "DLSS 5 neural rendering is switched on and off, and tuned, under Neural rendering (DLSS 5)." }
                    Row { visible: is("Visuals", "Upscaling"); spacing: 12
                        GlassButton { text: "Download FSR 4 assets"; width: 190; height: 38; onClicked: launcher.downloadFsr4() }
                        Note { text: launcher.fsrStatus; anchors.verticalCenter: parent.verticalCenter; width: 380 }
                    }
                    Row { visible: is("Visuals", "Upscaling"); spacing: 12
                        GlassButton { objectName: "fsr4vkDownload"; text: "Download FSR 4.1.1"; width: 190; height: 38; onClicked: launcher.downloadFsr4Vk() }
                        Note { text: launcher.fsr4vkStatus; anchors.verticalCenter: parent.verticalCenter; width: 380 }
                    }
                    Repeater {
                        model: is("Game & Saves", "Game files") ? launcher.readiness.slice(0, 1) :
                               is("Game & Saves", "Your data") ? launcher.readiness.slice(1) : []
                        delegate: Row {
                            spacing: 10
                            Rectangle { width: 8; height: 8; radius: 4; y: 5; color: modelData.level === "error" ? Theme.accent : modelData.level === "warning" ? Theme.warn : Theme.good }
                            Text { width: sectionActionsCol.width - 20; text: modelData.label + ":  " + modelData.detail; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; wrapMode: Text.WordWrap }
                        }
                    }
                    Row { visible: is("Game & Saves", "Game files"); spacing: 10
                        GlassButton { text: launcher.setupRunning ? "Installing…" : "Install from ZIP / PKG"; width: 196; height: 38; enabled: !launcher.setupRunning && !launcher.running; onClicked: launcher.installFromArchive() }
                        GlassButton { text: "Check again"; width: 120; height: 38; onClicked: launcher.refreshReadiness() }
                        GlassButton { text: "Setup wizard"; width: 128; height: 38; onClicked: workspace.openSetup(0) }
                    }
                    Row { visible: is("Game & Saves", "Your data"); spacing: 10
                        GlassButton { text: "Import trophy keys"; width: 168; height: 38; onClicked: launcher.importTrophyKeys() }
                        GlassButton { text: "Open saves folder"; width: 160; height: 38; onClicked: launcher.action("openSaves") }
                        GlassButton { text: "Check again"; width: 120; height: 38; onClicked: launcher.refreshReadiness() }
                    }
                    Row {
                        visible: is("Game & Saves", "Your data")
                        spacing: 16
                        Rectangle {
                            width: 48; height: 48; radius: 6
                            color: Theme.surface; border.color: Theme.lineStrong
                            clip: true
                            anchors.verticalCenter: parent.verticalCenter
                            Image {
                                anchors.fill: parent
                                anchors.margins: 2
                                source: launcher.userAvatar || Qt.resolvedUrl("../assets/ui/sunbros-avatar.png")
                                cache: false
                                fillMode: Image.PreserveAspectCrop
                                smooth: true; mipmap: true
                            }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            Row {
                                spacing: 10
                                GlassButton {
                                    text: "Choose Avatar…"
                                    width: 150; height: 36
                                    onClicked: launcher.chooseCustomAvatar()
                                }
                                GlassButton {
                                    visible: launcher.value("custom_avatar_path") !== ""
                                    text: "Reset to Default"
                                    width: 140; height: 36
                                    onClicked: launcher.resetCustomAvatar()
                                }
                            }
                            Text {
                                text: launcher.value("custom_avatar_path") !== "" ? "Custom avatar active: " + launcher.value("custom_avatar_path") : "Using default SunBro's emblem"
                                color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12
                            }
                        }
                    }
                    // Save backups (bbport_save_backups): zips of savedata in <saves folder>\save-backups.
                    // Restore and Delete ask in the row itself, not in a dialog.
                    Column {
                        id: saveBackupsSection
                        objectName: "saveBackupsSection"
                        visible: is("Game & Saves", "Save backups")
                        width: parent.width; spacing: 12
                        onVisibleChanged: { workspace.backupConfirm = ""; if (visible) launcher.refreshSaveBackups() }
                        Component.onCompleted: if (visible) launcher.refreshSaveBackups()
                        Note { text: "A backup is a zip of your savedata folder in " + launcher.saveBackupsFolder + ". Restoring one first backs up your current saves (\"before restore\"), so a restore can always be undone." }
                        Note {
                            objectName: "saveBackupsRunningNotice"
                            visible: launcher.running
                            text: "The game is running and has its saves open: close it to back up or restore."
                            color: Theme.warn; opacity: 1
                        }
                        Flow { width: parent.width; spacing: 10
                            GlassTextField { id: backupLabel; objectName: "saveBackupLabel"; width: 240; height: 38; placeholderText: "Label (optional)"; maximumLength: 60 }
                            GlassButton { objectName: "saveBackupNow"; text: launcher.saveBackupBusy ? "Working…" : "Back up now"; width: 140; height: 38; highlighted: true
                                enabled: !launcher.running && !launcher.saveBackupBusy
                                onClicked: { launcher.backupSavesNow(backupLabel.text); backupLabel.text = "" } }
                            GlassButton { objectName: "saveBackupOpenFolder"; text: "Open backups folder"; width: 180; height: 38; onClicked: launcher.openSaveBackups() }
                            GlassButton { objectName: "saveBackupRefresh"; text: "Refresh"; width: 100; height: 38; onClicked: launcher.refreshSaveBackups() }
                        }
                        Note { objectName: "saveBackupStatus"; visible: launcher.saveBackupStatus !== ""; text: launcher.saveBackupStatus; color: Theme.text; opacity: 1; font.pixelSize: 13 }
                        Note { visible: launcher.saveBackups.length === 0; text: "No backups yet." }
                        Repeater {
                            model: saveBackupsSection.visible ? launcher.saveBackups : []
                            delegate: Item {
                                id: backupRow
                                required property var modelData
                                required property int index
                                objectName: "saveBackupRow_" + index
                                property bool confirmRestore: workspace.backupConfirm === "restore:" + modelData.name
                                property bool confirmDelete: workspace.backupConfirm === "delete:" + modelData.name
                                width: saveBackupsSection.width; height: 58
                                Column {
                                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - actions.width - 16; spacing: 3
                                    Text { width: parent.width; elide: Text.ElideRight; color: Theme.text; font.family: Theme.sans; font.pixelSize: 14
                                        text: backupRow.modelData.date + (backupRow.modelData.label ? "  ·  " + backupRow.modelData.label : "") }
                                    Text { width: parent.width; elide: Text.ElideRight; color: backupRow.modelData.valid ? Theme.textDim : Theme.warn; font.family: Theme.sans; font.pixelSize: 12
                                        text: !backupRow.modelData.valid ? "Unreadable backup  ·  " + backupRow.modelData.size :
                                              ({manual: "Manual", auto: "Automatic", safety: "Before restore"}[backupRow.modelData.kind] || backupRow.modelData.kind) +
                                              "  ·  " + backupRow.modelData.size + "  ·  " + backupRow.modelData.files + " files" +
                                              (backupRow.modelData.summary ? "  ·  " + backupRow.modelData.summary : "") }
                                }
                                Row {
                                    id: actions
                                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                                    Text { visible: backupRow.confirmRestore || backupRow.confirmDelete; anchors.verticalCenter: parent.verticalCenter
                                        text: backupRow.confirmRestore ? "Replace your saves? They are backed up first." : "Delete this backup?"
                                        color: Theme.warn; font.family: Theme.sans; font.pixelSize: 12 }
                                    GlassButton { objectName: "saveBackupConfirm_" + backupRow.index; visible: backupRow.confirmRestore || backupRow.confirmDelete
                                        text: backupRow.confirmRestore ? "Restore" : "Delete"; width: 96; height: 34; highlighted: true
                                        enabled: !launcher.saveBackupBusy && (backupRow.confirmDelete || !launcher.running)
                                        onClicked: { var name = backupRow.modelData.name; var restore = backupRow.confirmRestore; workspace.backupConfirm = ""
                                            if (restore) launcher.restoreSaveBackup(name); else launcher.deleteSaveBackup(name) } }
                                    GlassButton { objectName: "saveBackupCancel_" + backupRow.index; visible: backupRow.confirmRestore || backupRow.confirmDelete
                                        text: "Cancel"; width: 84; height: 34; onClicked: workspace.backupConfirm = "" }
                                    GlassButton { objectName: "saveBackupRestore_" + backupRow.index; visible: !backupRow.confirmRestore && !backupRow.confirmDelete
                                        text: "Restore…"; width: 96; height: 34
                                        enabled: backupRow.modelData.valid && !launcher.running && !launcher.saveBackupBusy
                                        onClicked: workspace.backupConfirm = "restore:" + backupRow.modelData.name }
                                    GlassButton { objectName: "saveBackupDelete_" + backupRow.index; visible: !backupRow.confirmRestore && !backupRow.confirmDelete
                                        text: "Delete…"; width: 90; height: 34; enabled: !launcher.saveBackupBusy
                                        onClicked: workspace.backupConfirm = "delete:" + backupRow.modelData.name }
                                }
                                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
                            }
                        }
                    }
                    // The Hunter's Dream (hidden with BB_HUNTERS_DREAM=0): Discord sign-in by a code approved on its website.
                    Note { visible: is("Online", "The Hunter's Dream"); text: "The Hunter's Dream (thehuntersdream.com) is the public online server: messages, bloodstains, summons and invasions with players on bbhost and the other Bloodborne ports. Sign in once with Discord: press the button, sign in with Discord on the page that opens, and approve the code. Then choose \"Online · The Hunter's Dream\" under Play on the Home page. Seamless co-op with your friends is separate: Multiplayer > Seamless Co-op." }
                    Note { visible: is("Online", "The Hunter's Dream"); text: launcher.thdStatus; color: Theme.text; font.pixelSize: 13 }
                    Row { visible: is("Online", "The Hunter's Dream") && launcher.thdCode !== ""; spacing: 14
                        Text { text: launcher.thdCode; color: Theme.text; font.family: Theme.sans; font.pixelSize: 30; font.letterSpacing: 4; anchors.verticalCenter: parent.verticalCenter }
                        GlassButton { text: "Copy code"; width: 120; height: 38; anchors.verticalCenter: parent.verticalCenter; onClicked: launcher.thdCopyCode() }
                    }
                    Row { visible: is("Online", "The Hunter's Dream"); spacing: 10
                        GlassButton { text: launcher.thdBusy ? "Waiting for Discord…" : (launcher.thdSignedIn ? "Sign in again" : "Sign in with Discord"); width: 200; height: 38; enabled: !launcher.thdBusy; onClicked: launcher.thdSignIn() }
                        GlassButton { visible: launcher.thdBusy; text: "Cancel"; width: 110; height: 38; onClicked: launcher.thdCancel() }
                        GlassButton { visible: !launcher.thdBusy && launcher.thdSignedIn; text: "Sign out"; width: 110; height: 38; onClicked: launcher.thdSignOut() }
                        GlassButton { text: "Test connection"; width: 148; height: 38; onClicked: launcher.testConnection() }
                    }
                    Note { visible: is("Online", "The Hunter's Dream"); text: "The connection to The Hunter's Dream is Awaken's port of bbhost's network code (GPL-3.0), as Supermedo's port took it in; bbhost and The Hunter's Dream are by droogie and its team. Seamless co-op (the Co-op page) does not use it." }
                    CoopSetupPanel {
                        id: coopSetup
                        visible: is("Co-op", "Seamless co-op")
                        width: parent.width
                        onReturnHome: workspace.backToLauncher()
                    }
                    Note { visible: is("Co-op", "Host a session"); text: "Starts BBSC's two servers on this PC (the first time, Windows asks once to open the firewall for Tailscale and your home network only). Keep this launcher open while you play; closing it stops the servers." }
                    Row { visible: is("Co-op", "Host a session"); spacing: 10
                        GlassButton { text: launcher.coopHosting ? "Restart hosting" : "Start hosting"; width: 160; height: 38; enabled: !launcher.coopBusy; onClicked: launcher.coopStartHosting() }
                        GlassButton { text: "Copy invite code"; width: 160; height: 38; enabled: launcher.coopInvite !== ""; onClicked: launcher.coopCopyInvite() }
                        GlassButton { text: "Stop hosting"; width: 140; height: 38; enabled: launcher.coopHosting; onClicked: launcher.coopStopHosting() }
                    }
                    Note { visible: is("Co-op", "Join a host"); text: "Paste the invite code from your host, then Play co-op. The host rings the Hunt Bell; you ring the Kin Bell." }
                    Note { visible: is("Co-op", "BBSC public server"); text: "Join the public BBSC server (play.seamlesshunt.com). No Tailscale needed; your saves are backed up before every session." }
                    Note { visible: is("Co-op", "BBSC public server") && launcher.coopStatus !== ""; text: launcher.coopStatus; color: Theme.info }
                    Row { visible: is("Co-op", "BBSC public server"); spacing: 10
                        GlassButton { text: "Play co-op"; width: 160; height: 44; highlighted: true; enabled: !launcher.coopBusy && !launcher.running; onClicked: { launcher.setValue("coop_server", "public"); launcher.coopPlay(); } }
                    }
                    Note { visible: is("Mods & Patches", "Gameplay tweaks") || is("Mods & Patches", "Cheats"); text: "Optional gameplay changes. All are off by default and apply the next time the game starts." }
                    Repeater {
                        model: is("Mods & Patches", "Installed mods") ? launcher.contentMods : []
                        delegate: Item {
                            width: sectionActionsCol.width; height: 52
                            GlassSwitch { anchors.verticalCenter: parent.verticalCenter; text: modelData.name; checked: modelData.enabled; onToggled: launcher.setMod(modelData.name, checked) }
                            Row { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                GlassButton { text: "↑"; width: 36; height: 32; onClicked: launcher.moveMod(modelData.name, -1) }
                                GlassButton { text: "↓"; width: 36; height: 32; onClicked: launcher.moveMod(modelData.name, 1) }
                            }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
                        }
                    }
                    Note { visible: is("Mods & Patches", "Installed mods") && launcher.contentMods.length === 0; text: "No mods in the mods folder yet. Put each mod in its own folder there, then refresh." }
                    Row { visible: is("Mods & Patches", "Installed mods"); spacing: 10
                        GlassButton { text: "Refresh"; width: 110; height: 38; onClicked: launcher.refresh_addons() }
                        GlassButton { text: "Open mods folder"; width: 160; height: 38; onClicked: launcher.action("openMods") }
                    }
                    Repeater { model: is("Mods & Patches", "External patches") ? launcher.patches : []
                        delegate: GlassSwitch { text: modelData.name; checked: modelData.enabled; onToggled: launcher.setPatch(modelData.name, checked) }
                    }
                    Column { visible: is("System", "Launch"); width: parent.width; spacing: 14
                        Column {
                            width: parent.width
                            ToggleRow { label: "Start the game directly"; hint: "Opening Bloodborne starts the game; hold Shift or Ctrl to open the launcher instead."; checked: launcher.launchDirectly; onToggled: (on) => launcher.setValue("launchDirectly", on) }
                            ToggleRow { label: "Close the launcher after Play"; checked: launcher.closeOnPlay; onToggled: (on) => launcher.setValue("close_on_play", on) }
                        }
                        GlassSwitch {
                            objectName: "motionToggle"
                            readonly property bool motionActive: !Theme.reducedMotion
                            text: "Reduce motion in the launcher"
                            checked: Theme.reducedMotion
                            onToggled: Theme.reducedMotion = checked
                        }
                        Item {
                            objectName: "uiScaleRow"
                            width: parent.width; height: 52
                            Column {
                                x: 0; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 220; spacing: 2
                                Text { text: "Interface size"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15 }
                                Text { width: parent.width; text: "The launcher scales with its window; A− and A+ make it smaller or larger (Ctrl − / Ctrl +)."; color: Theme.textFaint; font.family: Theme.sans; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            }
                            TextSizeControl {
                                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        Row { spacing: 10
                            GlassButton { text: "Desktop shortcut"; width: 156; height: 38; onClicked: launcher.createShortcut() }
                            GlassButton { text: "Add to Steam"; width: 132; height: 38; onClicked: launcher.addToSteam() }
                        }
                    }
                    Column { visible: is("System", "Updates"); width: parent.width; spacing: 14
                        ToggleRow { label: "Check for updates"; hint: "Also checks quietly when the game starts directly, and shows the result here and on Play."; checked: launcher.checked("check_updates"); onToggled: (on) => launcher.setValue("check_updates", on) }
                        ToggleRow { label: "Download updates in the background"; hint: "Automatically download available updates while the launcher is open. Installation always waits for you. Turning this off applies to future downloads."; checked: launcher.checked("download_updates"); onToggled: (on) => launcher.setValue("download_updates", on) }
                        Note { visible: launcher.updateStatus.length > 0; text: launcher.updateStatus }
                        Flow { width: parent.width; spacing: 10
                            GlassButton { visible: launcher.hasUpdate && !launcher.updateReady; enabled: !launcher.updateBusy; text: launcher.updateBusy ? "Downloading…" : "Download update"; width: 210; height: 38; onClicked: launcher.downloadUpdate() }
                            GlassButton { visible: launcher.hasUpdate; enabled: launcher.updateReady && !launcher.updateBusy && !launcher.running; highlighted: enabled; text: "Install the new version"; width: 210; height: 38; onClicked: launcher.installUpdate() }
                            GlassButton { text: "Check now"; width: 116; height: 38; onClicked: launcher.checkForUpdates(true) }
                            GlassButton { objectName: "updateNotesButton"; visible: launcher.hasUpdate; text: "What's new in " + launcher.updateVersion; width: 190; height: 38; onClicked: Theme.showReleaseNotes("update") }
                            GlassButton { objectName: "currentNotesButton"; text: "This version's notes"; width: 170; height: 38; onClicked: Theme.showReleaseNotes("whatsnew") }
                            GlassButton { text: "Releases ↗"; width: 116; height: 38; onClicked: launcher.action("releases") }
                        }
                    }
                    Flow { visible: is("System", "Maintenance"); width: parent.width; spacing: 10
                        GlassButton {
                            id: saveSettingsBtn
                            objectName: "saveSettingsBtn"
                            property bool saved: false
                            text: saved ? "Saved" : "Save settings now"; width: 160; height: 38
                            onClicked: { launcher.saveSettings(); saved = true; savedTimer.restart() }
                            Timer { id: savedTimer; interval: 2500; onTriggered: saveSettingsBtn.saved = false }
                        }
                        GlassButton { text: "Open port folder"; width: 140; height: 38; onClicked: launcher.action("openPort") }
                        GlassButton { text: "Open bbport.ini"; width: 130; height: 38; onClicked: launcher.action("openConfig") }
                        GlassButton { text: "Restore saved settings"; width: 175; height: 38; onClicked: launcher.restoreSavedSettings() }
                        GlassButton { text: "Clear shader cache"; width: 150; height: 38; onClicked: launcher.action("clearCache") }
                        GlassButton { text: "Setup wizard"; width: 120; height: 38; onClicked: workspace.openSetup(0) }
                    }
                    Row { visible: is("System", "Logs"); spacing: 10
                        GlassButton { text: "Copy log"; width: 110; height: 38; onClicked: launcher.action("copyLog") }
                        GlassButton { text: "Clear log"; width: 110; height: 38; onClicked: launcher.action("clearLog") }
                    }
                    ScrollView {
                        visible: is("System", "Logs")
                        width: sectionActionsCol.width
                        height: visible ? 520 : 0
                        clip: true
                        ScrollBar.vertical: GlassScrollBar {}
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }

                        TextArea {
                            readOnly: true
                            wrapMode: TextEdit.NoWrap
                            text: launcher.log
                            color: Theme.text
                            selectByMouse: true
                            font.family: "Cascadia Mono"
                            font.pixelSize: 12
                            padding: 10
                            background: Rectangle {
                                color: Theme.well
                                radius: Theme.radius
                                border.color: Theme.line
                            }
                        }
                    }
                }
                }
            }
        }
    }
}
