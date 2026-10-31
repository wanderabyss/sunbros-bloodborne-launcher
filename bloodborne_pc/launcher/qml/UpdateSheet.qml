import QtQuick
import QtQuick.Controls

// Release notes as a sheet over the page, like a desktop app's update window. "update": a newer
// release, its notes from GitHub, and Download / Install now / Later. "whatsnew": this version's
// notes, shown once after an update (and from Settings > System > Updates).
Item {
    id: sheet
    objectName: "updateSheet"
    property string mode: ""
    readonly property bool shown: mode !== ""
    readonly property bool offer: mode === "update"
    readonly property string notes: offer ? launcher.updateNotes : launcher.whatsNew || launcher.currentReleaseNotes()
    visible: shown || fade.running
    z: 100

    function open(kind) { mode = kind }
    function close() {
        if (mode === "whatsnew") launcher.dismissWhatsNew()
        if (mode === "update") launcher.dismissInstallOffer()
        mode = ""
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: sheet.shown ? 0.55 : 0
        Behavior on opacity { NumberAnimation { id: fade; duration: Theme.motionPage } }
        MouseArea { anchors.fill: parent; enabled: sheet.shown; onClicked: sheet.close() }
    }

    GlassPanel {
        id: card
        objectName: "updateSheetCard"
        smoked: true
        radius: 28
        width: Math.min(640, sheet.width - 96)
        height: Math.min(sheet.height - 96, head.height + notesBox.contentHeight + 172)
        anchors.horizontalCenter: parent.horizontalCenter
        y: (sheet.height - height) / 2 + (sheet.shown ? 0 : 16)
        opacity: sheet.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionPage } }
        Behavior on y { NumberAnimation { duration: Theme.motionPage; easing.type: Easing.OutCubic } }
        MouseArea { anchors.fill: parent } // clicks on the card don't close it
        Rectangle { anchors.fill: parent; radius: parent.radius; color: "#eb17191f"; border.color: Theme.lineStrong }

        Row {
            id: head
            x: 28; y: 26; width: parent.width - 56; spacing: 16
            Rectangle {
                width: 56; height: 56; radius: 16; color: "#26ffffff"; border.color: Theme.line
                NavIcon { anchors.centerIn: parent; width: 36; height: 36; kind: "huntersmark"; stroke: 2.2; strokeColor: Theme.gold }
            }
            Column {
                width: parent.width - 72; spacing: 4
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    objectName: "updateSheetTitle"
                    width: parent.width; wrapMode: Text.WordWrap
                    text: sheet.offer ? "A new version of Bloodborne PC is available"
                                      : "What's new in Bloodborne PC " + launcher.currentVersion
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: 20; font.weight: Font.Bold
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: sheet.offer ? ("Version " + launcher.updateVersion + (launcher.updateDate ? " · released " + launcher.updateDate : "")
                                         + " · you have " + launcher.currentVersion)
                                      : "Here's what changed in this version."
                    color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 13
                }
            }
        }

        Rectangle {
            x: 28; y: head.y + head.height + 18; width: parent.width - 56
            height: parent.height - y - 84
            radius: 18; color: Theme.well
            Flickable {
                id: notesBox
                anchors.fill: parent; anchors.margins: 18
                clip: true; boundsBehavior: Flickable.StopAtBounds
                contentHeight: notesText.implicitHeight
                ScrollBar.vertical: GlassScrollBar {}
                Text {
                    id: notesText
                    objectName: "updateSheetNotes"
                    width: notesBox.width - 12
                    textFormat: Text.RichText
                    wrapMode: Text.WordWrap
                    // The short changelog, then a link to the full notes on the release page.
                    text: launcher.releaseNotesHtml((sheet.notes !== "" ? sheet.notes : "Release notes aren't available here.")
                                                    + "\n\n[Full release notes on GitHub ↗](release:" + (sheet.offer ? "update" : "current") + ")")
                    color: Theme.text; linkColor: Theme.link
                    font.family: Theme.sans; font.pixelSize: 13; lineHeight: 1.25
                    onLinkActivated: (link) => launcher.openReleaseLink(link)
                    HoverHandler { cursorShape: notesText.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
                }
            }
        }

        Text {
            objectName: "updateSheetStatus"
            x: 28; anchors.bottom: parent.bottom; anchors.bottomMargin: 34
            width: parent.width - 56 - buttons.width - 16
            visible: sheet.offer
            text: launcher.updateStatus !== "" ? launcher.updateStatus
                  : launcher.updateReady ? "Downloaded and ready to install." : ""
            color: Theme.textDim; font.family: Theme.sans; font.pixelSize: 12; elide: Text.ElideRight
        }

        Row {
            id: buttons
            anchors.right: parent.right; anchors.rightMargin: 28
            anchors.bottom: parent.bottom; anchors.bottomMargin: 24
            spacing: 10
            GlassButton {
                objectName: "updateSheetLater"
                visible: sheet.offer
                text: "Later"; width: 96; height: 40
                onClicked: sheet.close()
            }
            GlassButton {
                objectName: "updateSheetAction"
                visible: sheet.offer
                highlighted: true; height: 40
                width: Math.max(140, implicitContentWidth + 48)
                enabled: launcher.updateReady ? !launcher.running && !launcher.updateBusy : !launcher.updateBusy
                text: launcher.updateReady ? "Install now" : launcher.updateBusy ? "Downloading…" : "Download"
                onClicked: {
                    if (launcher.updateReady) launcher.installUpdate(true)
                    else launcher.downloadUpdate()
                }
            }
            GlassButton {
                objectName: "updateSheetDone"
                visible: !sheet.offer
                highlighted: true; text: "Continue"; width: 120; height: 40
                onClicked: sheet.close()
            }
        }
    }

    Shortcut { sequence: "Esc"; enabled: sheet.shown; onActivated: sheet.close() }
}
