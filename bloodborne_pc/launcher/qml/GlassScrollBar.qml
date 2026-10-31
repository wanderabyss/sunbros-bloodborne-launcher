import QtQuick
import QtQuick.Controls

ScrollBar {
    id: bar
    orientation: Qt.Vertical
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    policy: ScrollBar.AsNeeded
    visible: size < 1.0 && policy !== ScrollBar.AlwaysOff
    implicitWidth: 10
    implicitHeight: 10
    padding: 2
    minimumSize: 0.08
    contentItem: Rectangle {
        implicitWidth: 5
        implicitHeight: 5
        radius: 2.5
        color: bar.pressed ? "#b3ffffff" : bar.active ? "#80ffffff" : "#4dffffff"
    }
    background: Rectangle { color: "transparent" }
}
