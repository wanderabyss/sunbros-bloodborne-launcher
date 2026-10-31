import QtQuick
import QtQuick.Controls

TextField {
    id: control
    color: Theme.text
    placeholderTextColor: Theme.textFaint
    selectedTextColor: Theme.primaryText
    selectionColor: Theme.primary
    font.family: Theme.sans
    font.pixelSize: 14
    leftPadding: 14
    rightPadding: 14
    hoverEnabled: true
    background: Rectangle {
        radius: height / 2
        color: Theme.well
        border.color: control.activeFocus ? Theme.lineFocus : control.hovered ? Theme.lineStrong : Theme.line
        border.width: 1
    }
}
