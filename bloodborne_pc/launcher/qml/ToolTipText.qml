import QtQuick

// A small label to the right of a rail icon.
Rectangle {
    property alias text: label.text
    x: parent.width - 6; anchors.verticalCenter: parent.verticalCenter
    width: label.implicitWidth + 18; height: 26; radius: 4; z: 10
    color: "#f21a1e23"; border.color: Theme.lineStrong
    Text { id: label; anchors.centerIn: parent; color: Theme.text; font.family: Theme.sans; font.pixelSize: 12 }
}
