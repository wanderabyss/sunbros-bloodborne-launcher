import QtQuick
import QtQuick.Controls

// Pill buttons: `highlighted` is the one primary action on a surface (white, dark label);
// the rest are translucent glass. `serif` sets the label in the display face.
Button {
    id: button
    property bool primary: highlighted
    property bool serif: false
    font.family: serif ? Theme.serif : Theme.sans
    font.pixelSize: serif ? 20 : 14
    font.weight: Font.DemiBold
    hoverEnabled: true
    contentItem: Text {
        text: button.text
        font: button.font
        color: button.primary ? (button.enabled ? Theme.primaryText : "#80000000") : (button.enabled ? Theme.text : Theme.textMuted)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: height / 2
        color: button.primary ? (!button.enabled ? "#99ffffff" : button.down ? "#e0e0e0" : button.hovered ? "#f2f2f2" : Theme.primary)
                              : (button.down ? Theme.surfaceActive : button.hovered ? Theme.surfaceHover : Theme.surface)
        border.color: button.visualFocus ? Theme.lineFocus : button.primary ? "transparent" : Theme.line
        border.width: button.visualFocus ? 2 : 1
        Behavior on color { ColorAnimation { duration: 110 } }
    }
    scale: Theme.reducedMotion ? 1 : button.down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.reducedMotion ? 0 : 80 } }
}
