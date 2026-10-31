import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

// A menu control: the current value and ↕ on translucent glass; the list opens as dark glass.
ComboBox {
    id: control
    font.family: Theme.sans
    font.pixelSize: 14
    hoverEnabled: true

    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.windowText: Theme.text
    palette.highlightedText: Theme.primaryText
    palette.highlight: Theme.primary
    palette.base: "#2a2d34"
    palette.window: "#2a2d34"

    background: Rectangle {
        radius: height / 2
        color: control.pressed || control.popup.visible ? Theme.surfaceActive : control.hovered ? Theme.surfaceHover : Theme.surface
        border.color: control.visualFocus ? Theme.lineFocus : Theme.line
        border.width: control.visualFocus ? 2 : 1
    }

    contentItem: Text {
        text: {
            if (control.displayText) return control.displayText
            if (control.currentText) return control.currentText
            if (control.model && control.currentIndex >= 0 && control.currentIndex < control.model.length) {
                var item = control.model[control.currentIndex]
                if (typeof item === "string") return item
                if (item && item.text) return item.text
                if (item && item.label) return item.label
            }
            return ""
        }
        color: Theme.text
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        leftPadding: 16
        rightPadding: 34
    }

    // ↕ like a macOS pop-up button.
    indicator: Shape {
        width: 9
        height: 14
        x: control.width - width - 16
        y: (control.height - height) / 2
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "#d9ffffff"; strokeWidth: 1.6; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            PathSvg { path: "M1 5 L4.5 1.5 L8 5 M1 9 L4.5 12.5 L8 9" }
        }
    }

    delegate: ItemDelegate {
        id: itemDelegate
        width: control.width - 8
        height: 36
        highlighted: control.highlightedIndex === index
        hoverEnabled: true

        palette.text: Theme.text
        palette.buttonText: Theme.text
        palette.windowText: Theme.text

        property string itemText: {
            if (control.textRole && modelData && modelData[control.textRole] !== undefined) return String(modelData[control.textRole])
            if (typeof modelData === "string") return modelData
            if (modelData && modelData.text !== undefined) return String(modelData.text)
            if (modelData && modelData.label !== undefined) return String(modelData.label)
            return control.textAt(index) || ""
        }

        text: itemText

        contentItem: Text {
            text: (index === control.currentIndex ? "✓  " : "    ") + itemDelegate.itemText
            leftPadding: 10
            verticalAlignment: Text.AlignVCenter
            color: Theme.text
            font.family: Theme.sans
            font.pixelSize: 14
            elide: Text.ElideRight
        }

        background: Rectangle {
            radius: 8
            color: itemDelegate.hovered || itemDelegate.highlighted ? "#3dffffff" : "transparent"
        }
    }

    popup: Popup {
        y: control.height + 6
        width: control.width
        // The overlay is not magnified with the page (Main.qml), so the list scales itself.
        scale: Theme.zoom; transformOrigin: Popup.TopLeft
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        padding: 4

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollBar.vertical: GlassScrollBar {}
        }

        background: Rectangle {
            color: "#f22a2d34"
            radius: 14
            border.width: 1
            border.color: Theme.lineStrong
        }
    }
}
