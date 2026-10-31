import QtQuick
import QtQuick.Controls

// An iOS-style switch: green when on, translucent when off.
Switch {
    id: control
    spacing: text !== "" ? 12 : 0 // no label: no gap, so the switch is exactly its indicator
    padding: 0 // flush, so a row's switch ends where its dropdowns and buttons end
    hoverEnabled: true
    contentItem: Text {
        text: control.text
        color: Theme.text
        font.family: Theme.sans
        font.pixelSize: 15
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
    }
    indicator: Rectangle {
        implicitWidth: 51
        implicitHeight: 31
        x: control.leftPadding
        y: (control.height - height) / 2
        radius: height / 2
        color: control.checked ? Theme.good : (control.hovered ? "#47ffffff" : "#38ffffff")
        border.color: control.visualFocus ? Theme.lineFocus : "transparent"
        border.width: control.visualFocus ? 2 : 0
        Rectangle {
            width: 27; height: 27; radius: 13.5
            x: control.checked ? parent.width - width - 2 : 2
            y: 2
            color: "#ffffff"
            Behavior on x { NumberAnimation { duration: Theme.reducedMotion ? 0 : 140; easing.type: Easing.OutCubic } }
        }
        Behavior on color { ColorAnimation { duration: 140 } }
    }
}
