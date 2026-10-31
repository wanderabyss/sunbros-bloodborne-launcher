import QtQuick
import QtQuick.Window

// Shown instead of the launcher during a direct launch. It never takes focus from the game.
Window {
    id: splash
    objectName: "launchSplash"
    signal openLauncher()
    // Seconds before the game starts (set by bbport_launcher_qml.py); 0 once it is starting.
    property int countdown: 0
    visible: true
    width: 480; height: 128
    x: Screen.virtualX + (Screen.desktopAvailableWidth - width) / 2
    y: Screen.virtualY + (Screen.desktopAvailableHeight - height) / 2
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    title: "Bloodborne"

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: "#e60b1017"
        border.color: "#65e0e8ee"
        Rectangle { x: 1; y: 1; width: parent.width - 2; height: 1; color: "#43ffffff" }
        Rectangle { x: 16; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 62; radius: 2; color: "#bf475b" }
        Image {
            x: 34; anchors.verticalCenter: parent.verticalCenter
            width: 60; height: 60
            source: Qt.resolvedUrl("../assets/hunter-icon.png")
            fillMode: Image.PreserveAspectCrop
            smooth: true; mipmap: true
        }
        Column {
            x: 112; anchors.verticalCenter: parent.verticalCenter; spacing: 8
            Text {
                text: splash.countdown > 0 ? "Bloodborne starts in " + splash.countdown + "…" : "Launching Bloodborne…"
                color: "#f3f1ee"; font.family: "Georgia"; font.pixelSize: 22
            }
            Text { text: "Hold Shift or click here for the launcher"; color: "#d6dbe0"; font.pixelSize: 15; font.letterSpacing: 0.3 }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: splash.openLauncher() }
    }
}
