import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Online: The Hunter's Dream (messages, bloodstains, summons). Seamless co-op has its own page.
Item {
    id: online
    objectName: "onlineWorkspace"
    signal coopRequested()
    function openAt(section, key) { scroll.contentY = 0 }

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
            Text { text: "Online"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 40; font.weight: Font.Bold }
            Text { Layout.topMargin: 4; text: "Messages, bloodstains, summons and invasions with other hunters."; color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 15 }

            GlassPanel {
                objectName: "huntersDreamCard"
                Layout.topMargin: 22; Layout.fillWidth: true
                Layout.preferredHeight: card.implicitHeight + 48
                ColumnLayout {
                    id: card
                    x: 24; y: 24; width: parent.width - 48; spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "The Hunter's Dream"; color: Theme.text; font.family: Theme.sans; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
                        Rectangle {
                            objectName: "thdBadge"
                            radius: 14; height: 28; width: badgeRow.implicitWidth + 24
                            color: launcher.thdSignedIn ? "#4030d158" : "#26ffffff"
                            Row { id: badgeRow; anchors.centerIn: parent; spacing: 6
                                Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: launcher.thdSignedIn ? Theme.good : Theme.textFaint }
                                Text { text: launcher.thdBusy ? "Waiting for Discord" : launcher.thdSignedIn ? "Signed in" : "Not signed in"; color: launcher.thdSignedIn ? Theme.goodText : Theme.text; font.family: Theme.sans; font.pixelSize: 13; font.weight: Font.DemiBold }
                            }
                        }
                    }
                    Note { Layout.topMargin: 8; Layout.fillWidth: true; text: launcher.thdStatus; color: Theme.text }
                    RowLayout {
                        visible: launcher.thdCode !== ""
                        Layout.topMargin: 14; spacing: 14
                        Text { text: launcher.thdCode; color: Theme.text; font.family: Theme.sans; font.pixelSize: 30; font.weight: Font.Bold; font.letterSpacing: 4 }
                        GlassButton { text: "Copy code"; Layout.preferredWidth: 120; Layout.preferredHeight: 38; onClicked: launcher.thdCopyCode() }
                    }
                    Rectangle {
                        Layout.topMargin: 18; Layout.fillWidth: true
                        Layout.preferredHeight: rows.implicitHeight
                        visible: rowRepeater.count > 0
                        radius: 18; color: Theme.well
                        Column {
                            id: rows
                            width: parent.width
                            Repeater {
                                id: rowRepeater
                                model: launcher.settingsRevision < 0 ? [] : launcher.sectionFields("Online", "The Hunter's Dream")
                                delegate: FieldRow { required property var modelData; width: rows.width; field: modelData }
                            }
                        }
                    }
                    Flow {
                        Layout.topMargin: 18; Layout.fillWidth: true; spacing: 10
                        GlassButton { objectName: "thdSignIn"; text: launcher.thdBusy ? "Waiting for Discord…" : (launcher.thdSignedIn ? "Sign in again" : "Sign in with Discord"); width: 200; height: 40; highlighted: !launcher.thdSignedIn && !launcher.thdBusy; enabled: !launcher.thdBusy; onClicked: launcher.thdSignIn() }
                        GlassButton { visible: launcher.thdBusy; text: "Cancel"; width: 110; height: 40; onClicked: launcher.thdCancel() }
                        GlassButton { text: "Test connection"; width: 150; height: 40; onClicked: launcher.testConnection() }
                        Button {
                            visible: !launcher.thdBusy && launcher.thdSignedIn
                            width: 100; height: 40; hoverEnabled: true
                            onClicked: launcher.thdSignOut()
                            contentItem: Text { text: "Sign out"; color: Theme.error; font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            background: Rectangle { radius: 20; color: parent.hovered ? "#14ffffff" : "transparent" }
                        }
                    }
                    Note {
                        Layout.topMargin: 16; Layout.fillWidth: true; font.pixelSize: 12; color: Theme.textFaint
                        text: "Sign in once with Discord: press the button, sign in on the page that opens and approve the code. Then choose Online under Play on Home. The connection is Awaken's port of bbhost's network code (GPL-3.0); bbhost and The Hunter's Dream are by droogie and its team."
                    }
                }
            }

            MenuRow {
                objectName: "openCoopFromOnline"
                Layout.topMargin: 16; Layout.fillWidth: true
                height: 60
                icon: "coop"; label: "Playing with friends?"
                value: "Seamless co-op has its own tab"
                onClicked: online.coopRequested()
            }
        }
    }
}
