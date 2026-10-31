import QtQuick

// A row that opens something: optional icon, label, an optional current value, chevron.
Rectangle {
    id: row
    property string icon: ""
    property string label: ""
    property string value: ""
    property color valueColor: Theme.textDim
    property bool selected: false
    property bool chevron: true
    signal clicked()
    height: 52; radius: height / 2
    color: hit.containsMouse || selected ? Theme.surfaceHover : Theme.well
    border.color: selected ? Theme.lineStrong : "transparent"
    Behavior on color { ColorAnimation { duration: 100 } }

    NavIcon {
        id: glyph; visible: row.icon !== ""
        x: 16; anchors.verticalCenter: parent.verticalCenter; width: 20; height: 20
        kind: row.icon; strokeColor: Theme.text
    }
    Text {
        x: row.icon !== "" ? 50 : 16; anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - valueText.width - 56
        text: row.label; color: Theme.text; elide: Text.ElideRight
        font.family: Theme.sans; font.pixelSize: 15
    }
    Text {
        id: valueText
        anchors.right: parent.right; anchors.rightMargin: row.chevron ? 40 : 16; anchors.verticalCenter: parent.verticalCenter
        width: Math.min(implicitWidth, row.width * 0.42)
        text: row.value; color: row.valueColor; elide: Text.ElideRight
        font.family: Theme.sans; font.pixelSize: 14
    }
    NavIcon {
        visible: row.chevron
        anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
        width: 14; height: 14; kind: "chevron"; strokeColor: Theme.textFaint; stroke: 2
    }
    MouseArea { id: hit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: row.clicked() }
}
