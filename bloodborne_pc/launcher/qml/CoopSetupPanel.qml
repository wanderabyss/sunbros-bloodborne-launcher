import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Column {
    id: setup
    objectName: "coopSetupPanel"
    spacing: 20
    signal returnHome()
    property bool showIntro: true
    property int step: 0
    // The Co-op page shows Download BBSC, Play co-op and Return home in its side column
    // (CoopWorkspace); Settings > Co-op keeps them here.
    property bool actionsBeside: false
    function play() { launcher.setPlayMode("coop"); launcher.coopPlay() }
    function goHome() { launcher.setPlayMode("coop"); setup.returnHome() }
    property string privateRole: "join"
    Component.onCompleted: { if (launcher.coopHosting) privateRole = "host" }
    readonly property bool accountReady: nameInput.text.trim().length > 0 && passwordInput.text.length > 0
    readonly property bool publicServer: serverInput.currentIndex === 1
    readonly property bool connectionReady: publicServer || (privateRole === "host" ? launcher.coopHosting : !launcher.coopHosting && inviteInput.text.trim().length > 0)
    readonly property bool ready: accountReady && connectionReady
    readonly property bool editable: !launcher.coopBusy && !launcher.running
    readonly property string nextNeed: !accountReady ? "Add your account" : publicServer ? ""
        : privateRole === "host" ? (launcher.coopHosting ? "" : "Start hosting")
        : launcher.coopHosting ? "Stop your host" : inviteInput.text.trim().length > 0 ? "" : "Invite code needed"
    function stepDone(index) { return index === 0 ? accountReady : index === 1 ? ready : false }

    function revealSetting(key) {
        if (key === "coop_name" || key === "coop_password") {
            step = 0
            return key === "coop_name" ? nameInput : passwordInput
        }
        if (key === "coop_server" || key === "coop_invite") {
            step = 1
            return key === "coop_server" ? serverInput : inviteInput
        }
        return null
    }
    function fpsIndex() { var fps = String(launcher.value("coop_fps")); return fps === "120" ? 2 : fps === "90" ? 1 : 0 }
    function sync() {
        if (!nameInput.activeFocus) nameInput.text = String(launcher.value("coop_name") || "")
        if (!passwordInput.activeFocus) passwordInput.text = String(launcher.value("coop_password") || "")
        if (!serverInput.activeFocus) serverInput.currentIndex = String(launcher.value("coop_server")) === "public" ? 1 : 0
        if (!inviteInput.activeFocus) inviteInput.text = String(launcher.value("coop_invite") || "")
        if (!fpsInput.popup.visible) fpsInput.currentIndex = setup.fpsIndex()
    }
    Connections { target: launcher; function onChanged() { setup.sync() } }

    Text { visible: setup.showIntro; width: parent.width; text: "Prepare your shared hunt"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 24; font.weight: Font.Bold; wrapMode: Text.Wrap }
    Note { visible: setup.showIntro; font.pixelSize: 12; width: parent.width; text: "Set up your identity, then choose where to play and launch. Your choices save automatically." }
    Rectangle {
        id: stepTrack
        objectName: "coopStepTrack"
        width: parent.width; height: 44; radius: height / 2
        color: Theme.well; border.color: Theme.line
        Row {
            x: 4; y: 4; spacing: 2
            Repeater {
                model: ["Account", "Connection"]
                delegate: Button {
                    id: stepButton
                    required property int index
                    required property string modelData
                    readonly property bool current: setup.step === index
                    width: (stepTrack.width - 8 - 2) / 2; height: 36
                    readonly property bool done: setup.stepDone(index) && !current
                    text: (index + 1) + "   " + modelData
                    enabled: !launcher.coopBusy && (index === 0 || setup.accountReady)
                    hoverEnabled: true
                    onClicked: setup.step = index
                    Accessible.name: modelData + (current ? ", current step" : setup.stepDone(index) ? ", done" : "")
                    // A done step shows a check in place of its number.
                    contentItem: Item { Row {
                        anchors.centerIn: parent; spacing: 7
                        NavIcon { visible: stepButton.done; anchors.verticalCenter: parent.verticalCenter; width: 14; height: 14; stroke: 2.4; kind: "check"; strokeColor: Theme.good }
                        Text {
                            text: stepButton.done ? stepButton.modelData : stepButton.text
                            color: stepButton.current ? Theme.primaryText : !stepButton.enabled ? Theme.textMuted : Theme.text
                            font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                        }
                    } }
                    background: Rectangle { radius: height / 2; color: stepButton.current ? "#ffffff" : stepButton.hovered && stepButton.enabled ? Theme.surfaceHover : "transparent"; border.color: stepButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2
                        Behavior on color { ColorAnimation { duration: Theme.motionFast } } }
                }
            }
        }
    }

    Column {
        visible: setup.step === 0; width: parent.width; spacing: 14
        Text { text: "1. Your co-op account"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 18; font.weight: Font.DemiBold }
        Note { font.pixelSize: 12; width: parent.width; text: "Use a name and password for this server. The account is created or checked on launch. Choose a password unique to co-op." }
        Text { text: "Co-op name"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
        GlassTextField { id: nameInput; objectName: "coopNameEditor"; property string settingKey: "coop_name"; width: parent.width; height: 44; enabled: setup.editable; placeholderText: "Your co-op name"; text: String(launcher.value("coop_name") || ""); onTextEdited: launcher.setValue("coop_name", text) }
        Text { text: "Password"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
        RowLayout {
            width: parent.width; spacing: 10
            GlassTextField { id: passwordInput; objectName: "coopPasswordEditor"; property string settingKey: "coop_password"; Layout.fillWidth: true; Layout.preferredHeight: 44; enabled: setup.editable; placeholderText: "Use a password you use nowhere else"; echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password; text: String(launcher.value("coop_password") || ""); onTextEdited: launcher.setValue("coop_password", text) }
            GlassButton { id: showPassword; text: checked ? "Hide" : "Show"; checkable: true; Layout.preferredWidth: 72; Layout.preferredHeight: 44; enabled: setup.editable }
        }
        Note { font.pixelSize: 12; width: parent.width; text: setup.accountReady ? "Account details saved. Continue to choose your connection." : "Enter both a name and password to continue."; color: setup.accountReady ? Theme.textDim : Theme.warn }
        GlassButton { objectName: "coopAccountNext"; text: "Continue to connection  >"; width: 240; height: 44; enabled: setup.accountReady && setup.editable; onClicked: setup.step = 1 }
    }

    Column {
        visible: setup.step === 1; width: parent.width; spacing: 14
        Text { text: "2. Where do you want to play?"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 18; font.weight: Font.DemiBold }
        Text { text: "Network"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
        GlassComboBox { id: serverInput; objectName: "coopServerEditor"; property string settingKey: "coop_server"; width: parent.width; height: 44; enabled: setup.editable; model: ["Private session (Tailscale / local network)", "BBSC public (play.seamlesshunt.com)"]; currentIndex: String(launcher.value("coop_server")) === "public" ? 1 : 0; onActivated: launcher.setValue("coop_server", currentIndex === 1 ? "public" : "tailscale") }
        Note { font.pixelSize: 12; width: parent.width; text: setup.publicServer ? "Public server: no Tailscale or invite code needed. Your account will be checked when you launch." : "Private session: host and guests need Tailscale or a reachable local network. Choose your role below." }
        RowLayout {
            visible: !setup.publicServer; width: parent.width; spacing: 12
            GlassButton { text: "Host a session"; Layout.fillWidth: true; Layout.preferredHeight: 42; enabled: setup.editable; onClicked: setup.privateRole = "host"; background: Rectangle { radius: height / 2; color: setup.privateRole === "host" ? Theme.selection : Theme.surface; border.color: parent.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2 } }
            GlassButton { text: "Join a friend"; Layout.fillWidth: true; Layout.preferredHeight: 42; enabled: setup.editable; onClicked: setup.privateRole = "join"; background: Rectangle { radius: height / 2; color: setup.privateRole === "join" ? Theme.selection : Theme.surface; border.color: parent.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2 } }
        }
        Column {
            visible: !setup.publicServer && setup.privateRole === "join"; width: parent.width; spacing: 10
            Text { text: "Host invite code"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
            GlassTextField { id: inviteInput; objectName: "coopInviteEditor"; property string settingKey: "coop_invite"; width: parent.width; height: 44; enabled: setup.editable; placeholderText: "Paste the invite from your host"; text: String(launcher.value("coop_invite") || ""); onTextEdited: launcher.setValue("coop_invite", text) }
            GlassButton { visible: launcher.coopHosting; text: "Stop your host before joining"; width: 260; height: 42; enabled: setup.editable; onClicked: launcher.coopStopHosting() }
            Note { font.pixelSize: 12; width: parent.width; text: "Your host must keep their launcher and session open. The invite is validated when you launch." }
        }
        Column {
            visible: !setup.publicServer && setup.privateRole === "host"; width: parent.width; spacing: 10
            Note { font.pixelSize: 12; width: parent.width; text: launcher.coopHosting ? "Hosting is active. Copy your invite and share it privately with your hunters." : "Start hosting to prepare your private server and create an invite. Keep the launcher open while you play." }
            Flow {
                width: parent.width; spacing: 10
                GlassButton { objectName: "coopStartHosting"; text: launcher.coopHosting ? "Restart hosting" : "Start hosting"; width: 160; height: 42; enabled: setup.accountReady && setup.editable; onClicked: launcher.coopStartHosting() }
                GlassButton { text: "Copy invite"; width: 130; height: 42; enabled: launcher.coopInvite !== "" && !launcher.coopBusy; onClicked: launcher.coopCopyInvite() }
                GlassButton { text: "Stop hosting"; width: 130; height: 42; enabled: launcher.coopHosting && setup.editable; onClicked: launcher.coopStopHosting() }
            }
        }
        Text { text: "Session frame rate"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
        GlassComboBox {
            id: fpsInput
            objectName: "coopFrameRate"
            width: parent.width; height: 44; enabled: setup.editable
            model: ["60 FPS (BBSC default)", "90 FPS", "120 FPS"]
            currentIndex: setup.fpsIndex()
            onActivated: { var fps = currentIndex === 2 ? "120" : currentIndex === 1 ? "90" : "60"; launcher.setValue("coop_fps", fps); launcher.setValue("coop_frame_rate", fps) }
        }
        Note { font.pixelSize: 12; width: parent.width; text: "Everyone in the party uses the same rate. Higher rates need every PC to hold them." }
        Note { font.pixelSize: 12; width: parent.width; visible: !setup.connectionReady; text: setup.privateRole === "host" ? "Start hosting before you play." : launcher.coopHosting ? "Stop your own host before joining a friend." : "Paste your host's invite code before you play."; color: Theme.warn }
        // Launch is here: the separate summary step only repeated these choices.
        Note { font.pixelSize: 12; width: parent.width; text: "Play backs up your saves, signs you in to the co-op server, then starts the game." }
        // One row: connection details and the way back on the left; Play and Return home on the
        // right (or in the Co-op page's side column, actionsBeside).
        RowLayout {
            width: parent.width; spacing: 10
            GlassButton {
                id: detailsToggle
                objectName: "coopDetailsToggle"
                property bool open: false
                text: open ? "Hide connection details" : "Show connection details"
                Layout.preferredWidth: 230; Layout.preferredHeight: 44
                onClicked: { open = !open; if (open) launcher.refreshCoopEvents() }
            }
            GlassButton { objectName: "coopBackToAccount"; text: "<  Account"; Layout.preferredWidth: 120; Layout.preferredHeight: 44; enabled: setup.editable; onClicked: setup.step = 0 }
            Item { Layout.fillWidth: true }
            GlassButton { objectName: "coopGuidedPlay"; visible: !setup.actionsBeside; text: launcher.coopBusy ? "Preparing..." : "Play co-op"; Layout.preferredWidth: 170; Layout.preferredHeight: 44; highlighted: true; enabled: setup.ready && setup.editable; onClicked: setup.play() }
            GlassButton { objectName: "coopReturnHome"; visible: !setup.actionsBeside; text: "Return home"; Layout.preferredWidth: 130; Layout.preferredHeight: 44; enabled: setup.ready && setup.editable; onClicked: setup.goHome() }
        }
        Column {
            objectName: "coopConnectionDetails"
            visible: detailsToggle.open; width: parent.width; spacing: 10
            Row {
                spacing: 12
                GlassButton { objectName: "coopCheckConnection"; text: launcher.coopChecking ? "Checking…" : "Check connection"; width: 170; height: 38
                    enabled: !launcher.coopChecking; onClicked: launcher.checkCoopConnection(setup.privateRole) }
                // The firewall rules co-op makes, with one administrator prompt; highlighted when the
                // check found them missing, and rerunning it repairs them.
                GlassButton { objectName: "coopOpenPorts"; text: "Open ports (admin)"; width: 180; height: 38
                    highlighted: launcher.coopFirewallMissing
                    enabled: !launcher.coopChecking && !launcher.coopBusy; onClicked: launcher.openCoopPorts(setup.privateRole) }
                BusyIndicator { running: launcher.coopChecking || launcher.coopPortsResult.state === "working"; visible: running; width: 24; height: 24; anchors.verticalCenter: parent.verticalCenter }
            }
            // Open ports' result, right under its button (the status line is below the fold).
            Rectangle {
                objectName: "coopPortsResult"
                readonly property string state_: launcher.coopPortsResult.state || ""
                visible: state_ !== ""
                width: parent.width; height: portsRow.implicitHeight + 16; radius: 12
                color: state_ === "ok" ? Qt.rgba(Theme.good.r, Theme.good.g, Theme.good.b, 0.14)
                     : state_ === "failed" ? Qt.rgba(Theme.warn.r, Theme.warn.g, Theme.warn.b, 0.14) : Theme.well
                border.width: 1
                border.color: state_ === "ok" ? Theme.good : state_ === "failed" ? Theme.warn : "transparent"
                Row {
                    id: portsRow
                    x: 14; y: 8; width: parent.width - 28; spacing: 10
                    Text { text: parent.parent.state_ === "ok" ? "✓" : parent.parent.state_ === "failed" ? "!" : "…"
                        color: parent.parent.state_ === "ok" ? Theme.good : parent.parent.state_ === "failed" ? Theme.warn : Theme.textDim
                        font.family: "Segoe UI Symbol"; font.pixelSize: 16; font.weight: Font.Bold }
                    Text { objectName: "coopPortsResultText"; width: parent.width - 30; wrapMode: Text.Wrap
                        text: launcher.coopPortsResult.text || ""; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13 }
                }
            }
            Rectangle {
                visible: launcher.coopChecks.length > 0
                width: parent.width; height: checkRows.implicitHeight + 12; radius: 14; color: Theme.well
                Column {
                    id: checkRows
                    x: 14; y: 6; width: parent.width - 28; spacing: 2
                    Repeater {
                        model: launcher.coopChecks
                        delegate: Row {
                            required property var modelData
                            width: checkRows.width; spacing: 10; height: 26
                            Item { width: 18; height: 18; anchors.verticalCenter: parent.verticalCenter
                                // A text glyph, not NavIcon: a Shape inside the folded details still drew
                                // in the software renderer (offscreen tests).
                                Text { anchors.centerIn: parent; text: modelData.ok ? "✓" : "!"; color: modelData.ok ? Theme.good : Theme.warn
                                    font.family: modelData.ok ? "Segoe UI Symbol" : Theme.sans; font.pixelSize: 15; font.weight: Font.Bold } }
                            Text { width: parent.width * 0.42; anchors.verticalCenter: parent.verticalCenter; text: modelData.label; color: Theme.text; font.family: Theme.sans; font.pixelSize: 13; elide: Text.ElideRight }
                            Text { width: parent.width * 0.58 - 38; anchors.verticalCenter: parent.verticalCenter; text: modelData.detail; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12; elide: Text.ElideRight }
                        }
                    }
                }
            }
            Text { text: "Co-op events (BBSC's newest session)"; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12 }
            Rectangle {
                width: parent.width; height: eventLines.implicitHeight + 16; radius: 14; color: Theme.well
                Column {
                    id: eventLines
                    objectName: "coopEventLines"
                    x: 14; y: 8; width: parent.width - 28; spacing: 3
                    Text { visible: launcher.coopEvents.length === 0; width: parent.width; wrapMode: Text.Wrap; text: "No co-op session yet: relay, sign, join and session events appear here once the game runs with BBSC."; color: Theme.textMuted; font.family: Theme.sans; font.pixelSize: 12 }
                    Repeater {
                        model: launcher.coopEvents
                        delegate: Text { required property string modelData; width: eventLines.width; wrapMode: Text.WrapAnywhere; text: modelData; color: Theme.textDim; font.family: "Consolas"; font.pixelSize: 12 }
                    }
                }
            }
            // While open, newest events every 3 s (a short file read; BBSC writes as it goes).
            Timer { interval: 3000; repeat: true; running: detailsToggle.open && setup.step === 1 && setup.visible; onTriggered: launcher.refreshCoopEvents() }
        }
    }

    Row {
        width: parent.width; spacing: 12; visible: launcher.coopBusy || launcher.coopStatus !== ""
        BusyIndicator { running: launcher.coopBusy; visible: running; width: 24; height: 24 }
        Note { font.pixelSize: 12; width: parent.width - (launcher.coopBusy ? 36 : 0); text: launcher.coopStatus; color: Theme.textDim }
    }
    // BBSC's download (launcher.coopSetup), on the Account step only: up front when it is missing, or
    // again over a broken or older copy. Play co-op and Start hosting also fetch a missing one.
    Row {
        visible: setup.step === 0 && !setup.actionsBeside; width: parent.width; spacing: 12
        GlassButton {
            objectName: "coopDownload"
            text: launcher.coopInstalled ? "Download BBSC " + launcher.coopVersion + " again" : "Download BBSC " + launcher.coopVersion
            width: 230; height: 40
            highlighted: !launcher.coopInstalled
            enabled: !launcher.coopBusy && !launcher.running
            onClicked: launcher.coopSetup()
        }
        Note { anchors.verticalCenter: parent.verticalCenter; width: parent.width - 242; font.pixelSize: 12; color: Theme.textDim
            text: launcher.coopInstalled ? "BBSC " + launcher.coopVersion + " is installed." : "" }
    }
}
