import QtQuick
import QtQuick.Controls

// A− / A+: steps the interface size through Theme.sizeSteps (80%–130%); the percentage resets
// it to 100%. Saved as ui_scale.
GlassPanel {
    id: control
    objectName: "textSizeControl"
    smoked: true
    height: 40; radius: height / 2
    width: sizeRow.implicitWidth + 10
    readonly property int index: Theme.sizeIndex(Theme.uiScale)
    function step(delta) {
        Theme.uiScale = delta === 0 ? "auto" : Theme.sizeValue(index + delta)
        launcher.setValue("ui_scale", Theme.uiScale)
    }

    component SizeButton: Button {
        id: sizeButton
        property int glyph: 13
        width: 32; height: 32
        hoverEnabled: true
        contentItem: Text {
            text: "A"; color: sizeButton.enabled ? Theme.text : Theme.textMuted
            font.family: Theme.sans; font.pixelSize: sizeButton.glyph; font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: height / 2
            color: sizeButton.down ? Theme.surfaceActive : sizeButton.hovered ? Theme.surfaceHover : "transparent"
            border.color: sizeButton.visualFocus ? Theme.lineFocus : "transparent"; border.width: 2
        }
    }

    Row {
        id: sizeRow
        x: 5; anchors.verticalCenter: parent.verticalCenter; spacing: 2
        SizeButton {
            objectName: "textSmaller"; glyph: 12
            enabled: control.index > 0
            Accessible.name: "Smaller interface"
            onClicked: control.step(-1)
        }
        Button {
            id: reset
            objectName: "textSizeReset"
            width: 46; height: 32
            hoverEnabled: true
            Accessible.name: "Interface size " + text + ", reset"
            text: Math.round(Theme.sizeSteps[control.index] * 100) + "%"
            onClicked: control.step(0)
            contentItem: Text {
                text: reset.text; color: reset.hovered ? Theme.text : Theme.textDim
                font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            background: Item {}
        }
        SizeButton {
            objectName: "textLarger"; glyph: 17
            enabled: control.index < Theme.sizeSteps.length - 1
            Accessible.name: "Larger interface"
            onClicked: control.step(1)
        }
    }
}
