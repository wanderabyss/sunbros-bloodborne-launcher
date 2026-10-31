import QtQuick
import QtQuick.Controls
import QtQuick.Window

// The launcher window: pre-blurred art for the current page, its page, and the glass tab bar.
// A page is built the first time it is shown (Loader), not at start.
// Everything but the art sits on `stage`, laid out at the design size (1290 x 830) and magnified
// by Theme.zoom, so a 4K window shows the same launcher, sharp, at a comfortable size.
ApplicationWindow {
    id: window
    objectName: "launcherWindow"
    visible: true
    // A window, never full screen: opened (once, in Component.onCompleted) at the design size
    // scaled to about 40% x 45% of the desktop and centred, so a 4K screen shows the same
    // launcher larger and sharp rather than a small one in a corner.
    width: 1290; height: 830
    // Home fits at 800 px (the tab bar is 640); sidebar pages need room for sidebar and list.
    minimumWidth: page === "Home" ? 800 : 1040
    minimumHeight: 720
    // The design fills 80% of the window's height or width (the rest is art), times the A− / A+
    // step; never below 0.8, and never so large that sidebar pages get less than 1040 x 720.
    readonly property real fitZoom: Math.max(1, Math.min(width / 1290, height / 830) * 0.8)
    readonly property real roomZoom: Math.min(width / 1040, height / 720)
    readonly property real zoom: Math.max(0.8, Math.min(3, roomZoom, fitZoom * Theme.sizeStep))
    onZoomChanged: Theme.zoom = zoom
    function stepSize(delta) {
        Theme.uiScale = delta === 0 ? "auto" : Theme.sizeValue(Theme.sizeIndex(Theme.uiScale) + delta)
        launcher.setValue("ui_scale", Theme.uiScale)
    }
    // Popups and tooltips live in the window's overlay, outside `stage`, so each scales itself by
    // Theme.zoom (GlassComboBox, DossierWorkspace); this does it for the shared ToolTip.
    Binding { target: window.contentItem.ToolTip.toolTip; property: "scale"; value: window.zoom }
    Binding { target: window.contentItem.ToolTip.toolTip; property: "transformOrigin"; value: Popup.TopLeft }
    title: "Bloodborne - SunBro's Edition"
    color: Theme.base
    property string page: "Home"
    property var visited: ({"Home": true})
    // Each page's background in assets/ui/bg (blurred once at build time, not live).
    readonly property var backgrounds: ({
        "Home": "home", "Visuals": "visuals", "VisualsAdvanced": "visuals-advanced",
        "Online": "online", "Coop": "coop", "Dossier": "dossier", "Mods": "workshop",
        "ModsAdvanced": "workshop-advanced", "Settings": "settings", "Setup": "setup"
    })
    readonly property string backgroundName: backgrounds[page] || "home"
    readonly property string tabPage: page === "VisualsAdvanced" ? "Visuals" : page === "ModsAdvanced" ? "Mods" : page
    readonly property int pageBottom: page === "Setup" ? 0 : Theme.tabBarHeight + Theme.tabBarBottom + 12

    onPageChanged: {
        if (!visited[page]) {
            var next = Object.assign({}, visited)
            next[page] = true
            visited = next
        }
    }

    Component.onCompleted: {
        Theme.uiScale = String(launcher.value("ui_scale") || "auto")
        var startZoom = Math.max(1, Math.min(Screen.desktopAvailableWidth * 0.4 / 1290,
                                             Screen.desktopAvailableHeight * 0.45 / 830))
        width = Math.round(1290 * startZoom); height = Math.round(830 * startZoom)
        x = Screen.virtualX + Math.max(0, Math.round((Screen.desktopAvailableWidth - width) / 2))
        y = Screen.virtualY + Math.max(0, Math.round((Screen.desktopAvailableHeight - height) / 2))
        Theme.zoom = zoom
        // A downloaded update is offered with its notes; otherwise, after an update, what's new.
        if (launcher.startPage !== "Setup") {
            if (launcher.installOffer) releaseNotes.open("update")
            else if (launcher.whatsNew !== "") releaseNotes.open("whatsnew")
        }
        var initial = launcher.startPage || "Home"
        if (initial === "Setup") openSetupWizard(launcher.wizardStartStep || 0)
        else if (initial === "Game") openSettings("Game & Saves", "Game files", "")
        else if (initial === "Log") openSettings("System", "Logs", "")
    }

    // Calls fn with the page's item; the Loader builds it synchronously once the page is visited.
    function withPage(loader, fn) {
        if (loader.item) fn(loader.item)
        else Qt.callLater(function() { if (loader.item) fn(loader.item) })
    }
    function openSettings(category, section, key) {
        if (category === "Visuals") {
            if (section || key) {
                page = "VisualsAdvanced"
                withPage(visualsAdvanced, item => item.openAt("Visuals", section, key))
            } else {
                page = "Visuals"
            }
        } else if (category === "Online") {
            page = "Online"
            withPage(online, item => item.openAt(section, key))
        } else if (category === "Co-op") {
            page = "Coop"
            withPage(coop, item => item.openAt(section, key))
        } else if (category === "Mods & Patches") {
            if (section || key) {
                page = "ModsAdvanced"
                withPage(modsAdvanced, item => item.openAt("Mods & Patches", section, key))
            } else {
                page = "Mods"
            }
        } else {
            page = "Settings"
            withPage(preferences, item => item.openAt(category || "Controls", section, key))
        }
    }
    function navigate(destination) { page = destination }
    function openSetupWizard(step) {
        page = "Setup"
        withPage(setup, item => { item.startStep = step; item.step = step })
    }

    // Ctrl+1..7 switch tabs; Esc leaves a details page for its tab.
    readonly property var tabOrder: ["Home", "Visuals", "Online", "Coop", "Dossier", "Mods", "Settings"]
    Repeater {
        model: 7
        delegate: Item {
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                enabled: window.page !== "Setup"
                onActivated: window.navigate(window.tabOrder[index])
            }
        }
    }
    // Ctrl +, Ctrl − and Ctrl 0 step the interface size, as in a browser.
    Shortcut { sequences: [StandardKey.ZoomIn, "Ctrl+="]; onActivated: window.stepSize(1) }
    Shortcut { sequences: [StandardKey.ZoomOut]; onActivated: window.stepSize(-1) }
    Shortcut { sequence: "Ctrl+0"; onActivated: window.stepSize(0) }
    Connections {
        target: Theme
        function onShowReleaseNotes(mode) { releaseNotes.open(mode) }
    }
    Shortcut {
        sequence: "Esc"
        enabled: !releaseNotes.shown && (window.page === "VisualsAdvanced" || window.page === "ModsAdvanced")
        onActivated: window.page = window.tabPage
    }

    FontLoader { source: Qt.resolvedUrl("../assets/ui/bloodborne-font.ttf") }

    // --- Background: the page's art, crossfaded; only the shown one stays decoded ------------
    Repeater {
        model: ["home", "visuals", "visuals-advanced", "online", "coop", "dossier", "workshop", "workshop-advanced", "settings", "setup"]
        delegate: Image {
            required property string modelData
            readonly property bool current: window.backgroundName === modelData
            anchors.fill: parent
            source: current || opacity > 0 ? Qt.resolvedUrl("../assets/ui/bg/" + modelData + ".jpg") : ""
            sourceSize.width: 1920
            fillMode: Image.PreserveAspectCrop
            opacity: current ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.reducedMotion ? 0 : 260 } }
        }
    }
    // Home keeps its art sharp: a light shade where the text sits.
    Rectangle {
        anchors.fill: parent
        visible: window.page === "Home"
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#590a0c12" }
            GradientStop { position: 0.55; color: "#000a0c12" }
        }
    }
    Rectangle {
        anchors.fill: parent
        visible: window.page !== "Home"
        color: "#330a0c12"
    }

    // --- Pages --------------------------------------------------------------------------------
    Item {
        id: stage
        objectName: "launcherStage"
        width: window.width / window.zoom; height: window.height / window.zoom
        scale: window.zoom; transformOrigin: Item.TopLeft

    Item {
        id: pages
        anchors.fill: parent
        anchors.bottomMargin: window.pageBottom
        // The page that appears fades and rises in; the one it replaces hides at once, so
        // nothing can be clicked on a page that is leaving.
        property string shown: window.page
        onShownChanged: if (!Theme.reducedMotion) enter.restart()
        ParallelAnimation {
            id: enter
            NumberAnimation { target: pages; property: "opacity"; from: 0.0; to: 1.0; duration: Theme.motionPage; easing.type: Easing.OutCubic }
            NumberAnimation { target: pages; property: "y"; from: 10; to: 0; duration: Theme.motionPage; easing.type: Easing.OutCubic }
        }

        Loader {
            id: home; anchors.fill: parent
            active: !!window.visited["Home"]; visible: window.page === "Home"
            sourceComponent: HomePage {
                onPrimaryRequested: launcher.playSelected()
                onSettingsRequested: window.openSettings("Controls", "", "")
                onWorkspaceRequested: (category, section) => window.openSettings(category, section, "")
                onCharacterInfoRequested: window.page = "Dossier"
            }
        }
        Loader {
            id: visuals; anchors.fill: parent
            active: !!window.visited["Visuals"]; visible: window.page === "Visuals"
            sourceComponent: VisualsStudio {
                onAdvancedRequested: (section, key) => {
                    window.page = "VisualsAdvanced"
                    window.withPage(visualsAdvanced, item => item.openAt("Visuals", section, key))
                }
            }
        }
        Loader {
            id: visualsAdvanced; anchors.fill: parent
            active: !!window.visited["VisualsAdvanced"]; visible: window.page === "VisualsAdvanced"
            sourceComponent: SettingsWorkspace {
                objectName: "visualsAdvanced"
                categories: ["Visuals"]; category: "Visuals"
                backLabel: "Visuals"
                onBackRequested: window.page = "Visuals"
                onOpenSetup: (step) => window.openSetupWizard(step)
            }
        }
        Loader {
            id: online; anchors.fill: parent
            active: !!window.visited["Online"]; visible: window.page === "Online"
            sourceComponent: OnlineWorkspace { onCoopRequested: window.page = "Coop" }
        }
        Loader {
            id: coop; anchors.fill: parent
            active: !!window.visited["Coop"]; visible: window.page === "Coop"
            sourceComponent: CoopWorkspace { onReturnHome: window.page = "Home" }
        }
        Loader {
            id: dossier; anchors.fill: parent
            active: !!window.visited["Dossier"]; visible: window.page === "Dossier"
            sourceComponent: DossierWorkspace { onCloseRequested: window.page = "Home" }
        }
        Loader {
            id: mods; anchors.fill: parent
            active: !!window.visited["Mods"]; visible: window.page === "Mods"
            sourceComponent: WorkshopPage {
                onDetailsRequested: (section) => window.openSettings("Mods & Patches", section || "Installed mods", "")
            }
        }
        Loader {
            id: modsAdvanced; anchors.fill: parent
            active: !!window.visited["ModsAdvanced"]; visible: window.page === "ModsAdvanced"
            sourceComponent: SettingsWorkspace {
                objectName: "modsAdvanced"
                categories: ["Mods & Patches"]; category: "Mods & Patches"
                backLabel: "Workshop"
                onBackRequested: window.page = "Mods"
                onOpenSetup: (step) => window.openSetupWizard(step)
            }
        }
        Loader {
            id: preferences; anchors.fill: parent
            active: !!window.visited["Settings"]; visible: window.page === "Settings"
            sourceComponent: PreferencesPage { onOpenSetup: (step) => window.openSetupWizard(step) }
        }
        Loader {
            id: setup; anchors.fill: parent
            active: !!window.visited["Setup"]; visible: window.page === "Setup"
            sourceComponent: Item {
                property alias startStep: wizard.startStep
                property alias step: wizard.step
                GlassPanel {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 96, 820)
                    // Fits the current step, so a short step has no empty band above its buttons.
                    height: Math.min(parent.height - 64, wizard.neededHeight + 80)
                    Behavior on height { NumberAnimation { duration: Theme.motionPage; easing.type: Easing.OutCubic } }
                    radius: 32
                    SetupWizard {
                        id: wizard
                        anchors.fill: parent; anchors.margins: 40
                        onExitRequested: (target) => { window.page = target || "Home" }
                    }
                }
            }
        }
    }

    GlassTabBar {
        visible: window.page !== "Setup"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.tabBarBottom
        current: window.tabPage
        onNavigate: (destination) => window.navigate(destination)
    }

    UpdateSheet { id: releaseNotes; anchors.fill: parent }
    }
}
