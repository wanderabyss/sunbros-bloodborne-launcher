import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Seamless co-op: the guided account → connection flow, with the session and the way to play beside it.
Item {
    id: coop
    objectName: "coopWorkspace"
    signal returnHome()
    readonly property int sideWidth: width >= 1200 ? 380 : 320
    function openAt(section, key) {
        if (key) {
            var editor = setup.revealSetting(key)
            if (editor) Qt.callLater(() => editor.forceActiveFocus(Qt.OtherFocusReason))
        }
    }

    ColumnLayout {
        id: heading
        x: 64; y: Theme.pageTop; width: parent.width - 128; spacing: 4
        Text { text: "Seamless co-op"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 40; font.weight: Font.Bold }
        Text { text: "Play the whole game with friends. Each hunter needs their own account."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }
    }

    GlassPanel {
        id: flowCard
        objectName: "coopFlowCard"
        x: 64; y: heading.y + heading.height + 24
        width: parent.width - 128 - coop.sideWidth - 20
        height: Math.min(parent.height - y, setup.implicitHeight + 48 + 8)
        Behavior on height { NumberAnimation { duration: Theme.motionPage; easing.type: Easing.OutCubic } }
        Flickable {
            id: scroll
            anchors.fill: parent; anchors.margins: 24
            clip: true; boundsBehavior: Flickable.StopAtBounds
            contentHeight: setup.implicitHeight + 8
            ScrollBar.vertical: GlassScrollBar {}
            CoopSetupPanel { id: setup; width: scroll.width - 14; showIntro: false; actionsBeside: true; onReturnHome: coop.returnHome() }
        }
    }

    ColumnLayout {
        x: flowCard.x + flowCard.width + 20; y: flowCard.y; width: coop.sideWidth; spacing: 20
        GlassPanel {
            objectName: "coopAccountCard"
            Layout.fillWidth: true; Layout.preferredHeight: accountColumn.implicitHeight + 40
            ColumnLayout {
                id: accountColumn
                x: 20; y: 20; width: parent.width - 40; spacing: 12
                Text { text: "Your co-op account"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.Bold }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 101; radius: 18; color: Theme.well
                    Column {
                        width: parent.width
                        Item { width: parent.width; height: 50
                            Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: "Co-op name"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15 }
                            Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: String(launcher.value("coop_name") || "Not set"); color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }
                            Rectangle { x: 16; anchors.bottom: parent.bottom; width: parent.width - 16; height: 1; color: Theme.line }
                        }
                        Item { width: parent.width; height: 50
                            Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: "Status"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15 }
                            Row { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter; color: launcher.coopHosting ? Theme.good : setup.ready ? Theme.good : Theme.warn }
                                Text { objectName: "coopAccountStatus"; text: launcher.coopHosting ? "Hosting" : launcher.coopBusy ? "Preparing" : setup.ready ? "Ready" : (setup.nextNeed || "Setup needed"); color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }
                            }
                        }
                    }
                }
            }
        }
        GlassPanel {
            Layout.fillWidth: true; Layout.preferredHeight: tips.implicitHeight + 40
            ColumnLayout {
                id: tips
                x: 20; y: 20; width: parent.width - 40; spacing: 10
                Text { text: "Before you play"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 15; font.weight: Font.Bold }
                Note { Layout.fillWidth: true; text: "Each hunter needs their own account." }
                Note { Layout.fillWidth: true; text: "Everyone in the party uses the same session frame rate." }
                Note { Layout.fillWidth: true; text: "Hosting a private session? Keep the launcher open while you play." }
                // Account step: BBSC's download (launcher.coopSetup), up front or again over a
                // broken copy. Play co-op and Start hosting also fetch a missing one.
                GlassButton {
                    objectName: "coopSideDownload"
                    visible: setup.step === 0
                    Layout.fillWidth: true; Layout.preferredHeight: 42; Layout.topMargin: 6
                    text: launcher.coopInstalled ? "Download BBSC " + launcher.coopVersion + " again" : "Download BBSC " + launcher.coopVersion
                    highlighted: !launcher.coopInstalled
                    enabled: !launcher.coopBusy && !launcher.running
                    onClicked: launcher.coopSetup()
                }
                Note { visible: setup.step === 0 && launcher.coopInstalled; Layout.fillWidth: true; font.pixelSize: 12; color: Theme.textDim
                    text: "BBSC " + launcher.coopVersion + " is installed." }
                // Connection step: the way into the game.
                GlassButton {
                    objectName: "coopSidePlay"
                    visible: setup.step === 1
                    Layout.fillWidth: true; Layout.preferredHeight: 46; Layout.topMargin: 6
                    text: launcher.coopBusy ? "Preparing..." : "Play co-op"; highlighted: true
                    enabled: setup.ready && setup.editable
                    onClicked: setup.play()
                }
                GlassButton {
                    objectName: "coopSideReturnHome"
                    visible: setup.step === 1
                    Layout.fillWidth: true; Layout.preferredHeight: 42
                    text: "Return home"
                    enabled: setup.ready && setup.editable
                    onClicked: setup.goHome()
                }
            }
        }
    }
}
